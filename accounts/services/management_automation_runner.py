"""Management Automation Runtime — Runner، Audience، Revalidation، Dedup."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from accounts.models import (
    ManagementAutomationExecution,
    ManagementAutomationRecipient,
    ManagementAutomationRule,
)
from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from accounts.services.automation_message_templates import (
    enrich_candidate_context,
    get_effective_template,
    render_template,
    rule_template_is_valid,
)
from accounts.services.admin_windows_app import WINDOWS_ACTIVATION_Q
from accounts.services.growth_suppression import (
    PURPOSE_LICENSE_RENEWAL,
    PURPOSE_MARKETING,
    PURPOSE_RECOVERY,
    is_send_allowed,
)
from accounts.services.notifications import notify_marketing
from accounts.services.pending_orders import PENDING_ORDER_STATUSES, pending_orders_queryset
from accounts.services.sms import get_sms_balance_snapshot
from licenses.models import ClientAppEvent, License, LicenseActivation
from shop.models import DownloadLog, Order
from accounts.services.discount_engine import RULE_DISCOUNT_POLICIES, enrich_context_with_discount
from shop.services.order_id_utils import parse_order_id
from workspace.models import Customer, CustomerActivity, Dataset, Ticket

User = get_user_model()
logger = logging.getLogger(__name__)

TERMINAL_RECIPIENT_STATUSES = (
    ManagementAutomationRecipient.Status.SENT,
    ManagementAutomationRecipient.Status.ALERT,
)

RETRYABLE_RECIPIENT_STATUSES = (
    ManagementAutomationRecipient.Status.SKIPPED,
    ManagementAutomationRecipient.Status.FAILED,
    ManagementAutomationRecipient.Status.DRY_RUN,
    ManagementAutomationRecipient.Status.PENDING,
)

DEFAULT_QUIET_START = 23
DEFAULT_QUIET_END = 8

SKIP_REASON_LABELS: Dict[str, str] = {
    'deduped': 'اخیراً پیام گرفته',
    'cooldown': 'Cooldown فعال',
    'renewed': 'خرید/تمدید جدید',
    'license_not_active': 'لایسنس غیرفعال',
    'already_expired': 'لایسنس منقضی شده',
    'missing_license': 'لایسنس یافت نشد',
    'order_paid_or_gone': 'سفارش پرداخت شده',
    'user_has_paid_order': 'خرید جدید انجام شده',
    'user_has_paid_order_after': 'پس از این سفارش پرداخت موفق ثبت شده',
    'has_valid_access': 'دسترسی فعال دارد',
    'order_not_failed': 'پرداخت دیگر ناموفق نیست',
    'later_paid': 'پرداخت بعدی موفق بود',
    'has_license': 'لایسنس فعال دارد',
    'activated': 'فعال‌سازی انجام شده',
    'launched': 'برنامه اجرا شده',
    'crm_started': 'CRM شروع شده',
    'suppressed': 'مسدود شده (suppression)',
    'global_cooldown': 'محدودیت سراسری ۷۲ ساعته',
    'missing_order': 'سفارش یافت نشد',
}


@dataclass
class AutomationCandidate:
    trigger_key: str
    user: Any = None
    phone: str = ''
    context: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


def _crm_user_engaged(user_id: int, *, since) -> bool:
    if CustomerActivity.objects.filter(customer__user_id=user_id, created_at__gte=since).exists():
        return True
    return Customer.objects.filter(user_id=user_id, updated_at__gte=since).exists()


def _persist_recipient(
    *,
    rule: ManagementAutomationRule,
    execution: ManagementAutomationExecution,
    candidate: AutomationCandidate,
    status: str,
    skipped_reason: str = '',
    sent_at=None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[ManagementAutomationRecipient], bool]:
    """
    upsert گیرنده — dedup فقط برای SENT/ALERT.
    Returns (recipient, deduped).
    """
    if _trigger_already_handled(rule, candidate.trigger_key):
        return None, True
    payload_meta = _safe_metadata(metadata if metadata is not None else candidate.metadata)
    recipient, _created = ManagementAutomationRecipient.objects.update_or_create(
        rule=rule,
        trigger_key=candidate.trigger_key,
        defaults={
            'execution': execution,
            'user': candidate.user,
            'status': status,
            'skipped_reason': (skipped_reason or '')[:200],
            'sent_at': sent_at,
            'metadata': payload_meta,
        },
    )
    return recipient, False


def _filter_eligible_candidates(
    rule: ManagementAutomationRule,
    candidates: List[AutomationCandidate],
    *,
    dry_run: bool = False,
) -> List[AutomationCandidate]:
    """حذف dedup/revalidate/cooldown قبل از سقف batch — رفع starvation."""
    from accounts.services.automation_contact_policy import check_global_contact_policy

    eligible: List[AutomationCandidate] = []
    for candidate in candidates:
        if _trigger_already_handled(rule, candidate.trigger_key):
            continue
        ok, _reason = revalidate_candidate(rule, candidate)
        if not ok:
            continue
        user_id = getattr(candidate.user, 'pk', None) or candidate.metadata.get('user_id')
        if user_id and _user_cooldown_active(rule, user_id):
            continue
        if rule.action_type == ManagementAutomationRule.ActionType.SEND_SMS and user_id:
            allowed, _policy_reason = check_global_contact_policy(
                rule, user_id=int(user_id), dry_run=dry_run,
            )
            if not allowed:
                continue
        eligible.append(candidate)
    return eligible


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, 'hex'):
        return str(value)
    return value


def _safe_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    return _json_safe(meta or {})


def _local_now(now=None):
    now = now or timezone.now()
    return timezone.localtime(now) if timezone.is_aware(now) else now


def _site_link() -> str:
    return (getattr(settings, 'SITE_URL', '') or 'https://divarfiling.ir').rstrip('/') + '/'


def _renewal_link() -> str:
    from accounts.services.growth_links import renewal_or_buy_landing_url

    return renewal_or_buy_landing_url()


def _format_expiry_date(dt) -> str:
    if not dt:
        return ''
    try:
        import jdatetime
        local = timezone.localtime(dt)
        j = jdatetime.date.fromgregorian(date=local.date())
        from workspace.services.jalali_input import to_persian_digits
        return to_persian_digits(j.strftime('%Y/%m/%d'))
    except Exception:
        return timezone.localtime(dt).strftime('%Y-%m-%d')


def _plan_name(lic_or_order) -> str:
    plan = getattr(lic_or_order, 'plan', None)
    if plan and getattr(plan, 'name', None):
        return plan.name
    product = getattr(getattr(lic_or_order, 'order', None), 'product', None) or getattr(lic_or_order, 'product', None)
    return getattr(product, 'title', '') or 'فایلینگ دیوار'


def _name_part(user) -> str:
    name = (getattr(user, 'first_name', '') or '').strip()
    return f' {name}' if name else ''


def _phone_ok(raw: str) -> str:
    phone = normalize_phone(raw or '')
    if not is_valid_iran_mobile(phone):
        return ''
    return phone


def rule_is_due(rule: ManagementAutomationRule, *, now=None, force: bool = False) -> bool:
    if force:
        return True
    if not rule.last_run_at:
        return True
    local = _local_now(now)
    last = _local_now(rule.last_run_at)
    if rule.cadence == ManagementAutomationRule.Cadence.HOURLY:
        return (local - last) >= timedelta(hours=1)
    return local.date() > last.date()


def in_quiet_hours(rule: ManagementAutomationRule, *, now=None) -> bool:
    start = rule.quiet_hours_start
    end = rule.quiet_hours_end
    if start is None and end is None:
        start, end = DEFAULT_QUIET_START, DEFAULT_QUIET_END
    if start is None or end is None:
        return False
    hour = _local_now(now).hour
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def _has_active_license(user_id: int, *, now=None) -> bool:
    now = now or timezone.now()
    return License.objects.filter(
        order__user_id=user_id,
        order__status='paid',
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).exists()


def _resolve_license_expiring(*, within_days: int = 3) -> List[AutomationCandidate]:
    now = timezone.now()
    horizon = now + timedelta(days=within_days)
    out: List[AutomationCandidate] = []
    qs = (
        License.objects.filter(
            order__status='paid',
            status='active',
            expires_at__isnull=False,
            expires_at__gt=now,
            expires_at__lte=horizon,
        )
        .select_related('order', 'order__user', 'order__product', 'plan')
        .order_by('expires_at')[:500]
    )
    for lic in qs:
        user = lic.order.user
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        exp_date = timezone.localtime(lic.expires_at).date()
        days_left = max(1, (lic.expires_at - now).days)
        product = getattr(lic.order.product, 'title', None) or getattr(lic.plan, 'name', '') or 'فایلینگ'
        plan = _plan_name(lic)
        exp_label = _format_expiry_date(lic.expires_at)
        out.append(AutomationCandidate(
            trigger_key=f'license_expiring:{lic.pk}:{exp_date.isoformat()}',
            user=user,
            phone=phone,
            context={
                'name_part': _name_part(user),
                'product': product,
                'plan': plan,
                'license_plan': plan,
                'days': str(days_left),
                'days_left': str(days_left),
                'expiry_date': exp_label,
                'license_expiry': exp_label,
                'link': _renewal_link(),
            },
            metadata={'license_id': lic.pk, 'user_id': user.pk, 'expires_at': exp_date.isoformat()},
        ))
    return out


def _resolve_expired_renewal(*, within_days: int = 14) -> List[AutomationCandidate]:
    now = timezone.now()
    cutoff = now - timedelta(days=within_days)
    out: List[AutomationCandidate] = []
    seen_users: set[int] = set()
    qs = (
        License.objects.filter(
            order__status='paid',
            expires_at__isnull=False,
            expires_at__lte=now,
            expires_at__gte=cutoff,
        )
        .select_related('order', 'order__user', 'order__product', 'plan')
        .order_by('-expires_at')[:500]
    )
    for lic in qs:
        user = lic.order.user
        if user.pk in seen_users or _has_active_license(user.pk, now=now):
            continue
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        seen_users.add(user.pk)
        exp_date = timezone.localtime(lic.expires_at).date()
        product = getattr(lic.order.product, 'title', None) or getattr(lic.plan, 'name', '') or 'فایلینگ'
        plan = _plan_name(lic)
        exp_label = _format_expiry_date(lic.expires_at)
        out.append(AutomationCandidate(
            trigger_key=f'expired_license:{lic.pk}:{exp_date.isoformat()}',
            user=user,
            phone=phone,
            context={
                'name_part': _name_part(user),
                'product': product,
                'plan': plan,
                'license_plan': plan,
                'expiry_date': exp_label,
                'license_expiry': exp_label,
                'link': _renewal_link(),
                'code': '',
            },
            metadata={'license_id': lic.pk, 'user_id': user.pk},
        ))
    return out


def _resolve_pending_orders(*, stale_hours: int = 2) -> List[AutomationCandidate]:
    cutoff = timezone.now() - timedelta(hours=stale_hours)
    out: List[AutomationCandidate] = []
    qs = (
        pending_orders_queryset(dedupe_by_user=True)
        .filter(created_at__lte=cutoff)
        .select_related('user', 'product', 'plan')
        .order_by('-created_at')[:500]
    )
    for order in qs:
        user = order.user
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        from accounts.services.admin_marketing import _checkout_url, _format_amount
        amount = _format_amount(order.amount)
        out.append(AutomationCandidate(
            trigger_key=f'pending_order:{order.pk}',
            user=user,
            phone=phone,
            context={
                'name_part': _name_part(user),
                'product': order.product.title if order.product_id else 'محصول',
                'order_product': order.product.title if order.product_id else 'محصول',
                'plan': order.plan.name if order.plan_id else '',
                'amount': amount,
                'order_amount': amount,
                'order_id': str(order.pk),
                'link': _checkout_url(order.pk),
                'code': '',
            },
            metadata={'order_id': str(order.pk), 'user_id': user.pk},
        ))
    return out


def _resolve_failed_orders(*, days_lookback: int = 1, min_minutes: int = 30) -> List[AutomationCandidate]:
    since = timezone.now() - timedelta(days=max(1, days_lookback))
    min_cutoff = timezone.now() - timedelta(minutes=min_minutes)
    out: List[AutomationCandidate] = []
    qs = (
        Order.objects.filter(status='failed', created_at__gte=since, created_at__lte=min_cutoff)
        .select_related('user', 'product', 'plan')
        .order_by('-created_at')[:500]
    )
    failed_counts: Dict[int, int] = {}
    for order in qs:
        if order.user_id:
            failed_counts[order.user_id] = failed_counts.get(order.user_id, 0) + 1
    for order in qs:
        user = order.user
        if user and failed_counts.get(user.pk, 0) >= 3:
            continue
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        from accounts.services.admin_marketing import _checkout_url, _format_amount
        amount = _format_amount(order.amount)
        out.append(AutomationCandidate(
            trigger_key=f'failed_order:{order.pk}',
            user=user,
            phone=phone,
            context={
                'name_part': _name_part(user),
                'product': order.product.title if order.product_id else 'محصول',
                'order_product': order.product.title if order.product_id else 'محصول',
                'plan': order.plan.name if order.plan_id else '',
                'amount': amount,
                'order_amount': amount,
                'order_id': str(order.pk),
                'link': _checkout_url(order.pk),
                'code': '',
            },
            metadata={'order_id': str(order.pk), 'user_id': user.pk},
        ))
    return out


def _resolve_users_onboarding(*, min_hours: int = 24) -> List[AutomationCandidate]:
    since = timezone.now() - timedelta(days=14)
    cutoff = timezone.now() - timedelta(hours=min_hours)
    now = timezone.now()
    active_license_q = License.objects.filter(
        order__user=OuterRef('pk'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    out: List[AutomationCandidate] = []
    qs = (
        User.objects.filter(is_active=True, date_joined__gte=since, date_joined__lte=cutoff)
        .annotate(has_active=Exists(active_license_q))
        .filter(has_active=False)[:500]
    )
    for user in qs:
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        out.append(AutomationCandidate(
            trigger_key=f'user_onboarding:{user.pk}',
            user=user,
            phone=phone,
            context={
                'name_part': _name_part(user),
                'link': _site_link(),
                'code': '',
            },
            metadata={'user_id': user.pk},
        ))
    return out


def _resolve_windows_download_no_activate() -> List[AutomationCandidate]:
    activated_ids = LicenseActivation.objects.filter(WINDOWS_ACTIVATION_Q).values_list(
        'license__order__user_id', flat=True,
    )
    user_ids = (
        DownloadLog.objects.values_list('user_id', flat=True)
        .distinct()
        .exclude(user_id__in=activated_ids)
    )[:500]
    out: List[AutomationCandidate] = []
    for user in User.objects.filter(pk__in=list(user_ids)):
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        out.append(AutomationCandidate(
            trigger_key=f'windows_download:{user.pk}',
            user=user,
            phone=phone,
            context={'name_part': _name_part(user), 'link': _site_link()},
            metadata={'user_id': user.pk},
        ))
    return out


def _resolve_windows_activate_no_launch() -> List[AutomationCandidate]:
    launched = ClientAppEvent.objects.filter(
        event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
    ).values_list('user_id', flat=True)
    user_ids = (
        LicenseActivation.objects.filter(WINDOWS_ACTIVATION_Q)
        .exclude(license__order__user_id__in=launched)
        .values_list('license__order__user_id', flat=True)
        .distinct()
    )[:500]
    out: List[AutomationCandidate] = []
    for user in User.objects.filter(pk__in=list(user_ids)):
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        out.append(AutomationCandidate(
            trigger_key=f'windows_no_launch:{user.pk}',
            user=user,
            phone=phone,
            context={'name_part': _name_part(user), 'link': _site_link()},
            metadata={'user_id': user.pk},
        ))
    return out


def _resolve_crm_not_started() -> List[AutomationCandidate]:
    now = timezone.now()
    active_license_q = License.objects.filter(
        order__user=OuterRef('pk'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    has_crm_q = Customer.objects.filter(user=OuterRef('pk'))
    out: List[AutomationCandidate] = []
    qs = (
        User.objects.filter(is_active=True)
        .annotate(has_active=Exists(active_license_q), has_crm=Exists(has_crm_q))
        .filter(has_active=True, has_crm=False)[:500]
    )
    for user in qs:
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        out.append(AutomationCandidate(
            trigger_key=f'crm_not_started:{user.pk}',
            user=user,
            phone=phone,
            context={'name_part': _name_part(user), 'link': _site_link()},
            metadata={'user_id': user.pk},
        ))
    return out


def _resolve_sms_balance_alert(*, now=None) -> List[AutomationCandidate]:
    sms = get_sms_balance_snapshot()
    if not (sms.get('is_low') and sms.get('ok')):
        return []
    local = _local_now(now)
    bucket = local.strftime('%Y-%m-%d-%H') if True else local.date().isoformat()
    credit = int(sms.get('credit') or sms.get('sms_count') or 0)
    return [AutomationCandidate(
        trigger_key=f'sms_low:{bucket}',
        context={'credit': str(credit)},
        metadata={'credit': credit, 'alert': True},
    )]


def _resolve_stale_tickets_alert(*, hours: int = 12, now=None) -> List[AutomationCandidate]:
    cutoff = timezone.now() - timedelta(hours=hours)
    count = (
        Ticket.objects.exclude(status='closed')
        .filter(staff_has_unread=True)
        .filter(Q(last_message_at__lte=cutoff) | Q(last_message_at__isnull=True, created_at__lte=cutoff))
        .count()
    )
    if not count:
        return []
    local = _local_now(now)
    bucket = local.strftime('%Y-%m-%d-%H')
    return [AutomationCandidate(
        trigger_key=f'stale_tickets:{bucket}',
        metadata={'count': count, 'alert': True},
    )]


def _resolve_pending_orders_discount(*, stale_hours: int = 24) -> List[AutomationCandidate]:
    cutoff = timezone.now() - timedelta(hours=stale_hours)
    out: List[AutomationCandidate] = []
    qs = (
        pending_orders_queryset(dedupe_by_user=True)
        .filter(created_at__lte=cutoff)
        .select_related('user', 'product', 'plan')
        .order_by('-created_at')[:500]
    )
    for order in qs:
        user = order.user
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        from accounts.services.admin_marketing import _checkout_url, _format_amount
        amount = _format_amount(order.amount)
        out.append(AutomationCandidate(
            trigger_key=f'pending_discount:{order.pk}',
            user=user,
            phone=phone,
            context={
                'name_part': _name_part(user),
                'product': order.product.title if order.product_id else 'محصول',
                'order_product': order.product.title if order.product_id else 'محصول',
                'plan': order.plan.name if order.plan_id else '',
                'amount': amount,
                'order_amount': amount,
                'order_id': str(order.pk),
                'link': _checkout_url(order.pk),
            },
            metadata={'order_id': str(order.pk), 'user_id': user.pk, 'issue_discount': True},
        ))
    return out


def _resolve_returning_customer_renewal() -> List[AutomationCandidate]:
    now = timezone.now()
    recent = now - timedelta(days=7)
    active_q = License.objects.filter(
        order__user=OuterRef('pk'),
        order__status='paid',
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    renewed_q = Order.objects.filter(user=OuterRef('pk'), status='paid', paid_at__gte=recent)
    had_license_q = Order.objects.filter(user=OuterRef('pk'), status='paid', licenses__isnull=False)
    out: List[AutomationCandidate] = []
    qs = (
        User.objects.filter(is_active=True, last_login__gte=recent)
        .annotate(
            has_active=Exists(active_q),
            renewed_recently=Exists(renewed_q),
            had_license=Exists(had_license_q),
        )
        .filter(has_active=False, renewed_recently=False, had_license=True)
        .exclude(last_login__isnull=True)[:500]
    )
    for user in qs:
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        out.append(AutomationCandidate(
            trigger_key=f'returning_customer:{user.pk}',
            user=user,
            phone=phone,
            context={
                'name_part': _name_part(user),
                'link': _renewal_link(),
            },
            metadata={'user_id': user.pk, 'issue_discount': True},
        ))
    return out


def _resolve_purchase_no_download(*, min_hours: int = 24) -> List[AutomationCandidate]:
    now = timezone.now()
    cutoff = now - timedelta(hours=min_hours)
    downloaded = set(DownloadLog.objects.values_list('user_id', flat=True).distinct())
    active_license_q = License.objects.filter(
        order__user=OuterRef('pk'),
        order__status='paid',
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    paid_q = Order.objects.filter(user=OuterRef('pk'), status='paid', paid_at__lte=cutoff)
    out: List[AutomationCandidate] = []
    qs = (
        User.objects.filter(is_active=True)
        .annotate(has_active=Exists(active_license_q), had_paid=Exists(paid_q))
        .filter(has_active=True, had_paid=True)
        .exclude(pk__in=downloaded)[:500]
    )
    for user in qs:
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        out.append(AutomationCandidate(
            trigger_key=f'purchase_no_download:{user.pk}',
            user=user,
            phone=phone,
            context={'name_part': _name_part(user), 'link': _site_link()},
            metadata={'user_id': user.pk},
        ))
    return out


def _resolve_launch_no_dataset(*, hours: int = 48) -> List[AutomationCandidate]:
    cutoff = timezone.now() - timedelta(hours=hours)
    launched_ids = ClientAppEvent.objects.filter(
        event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
        created_at__lte=cutoff,
    ).values_list('user_id', flat=True)
    has_dataset_q = Dataset.objects.filter(user=OuterRef('pk'))
    out: List[AutomationCandidate] = []
    qs = (
        User.objects.filter(is_active=True, pk__in=launched_ids)
        .annotate(has_ds=Exists(has_dataset_q))
        .filter(has_ds=False)[:500]
    )
    for user in qs:
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        out.append(AutomationCandidate(
            trigger_key=f'launch_no_dataset:{user.pk}',
            user=user,
            phone=phone,
            context={'name_part': _name_part(user), 'link': _site_link()},
            metadata={'user_id': user.pk},
        ))
    return out


def _resolve_dataset_no_crm(*, days: int = 3) -> List[AutomationCandidate]:
    cutoff = timezone.now() - timedelta(days=days)
    has_dataset_q = Dataset.objects.filter(user=OuterRef('pk'), created_at__lte=cutoff)
    has_crm_q = Customer.objects.filter(user=OuterRef('pk'))
    out: List[AutomationCandidate] = []
    qs = (
        User.objects.filter(is_active=True)
        .annotate(has_ds=Exists(has_dataset_q), has_crm=Exists(has_crm_q))
        .filter(has_ds=True, has_crm=False)[:500]
    )
    for user in qs:
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        out.append(AutomationCandidate(
            trigger_key=f'dataset_no_crm:{user.pk}',
            user=user,
            phone=phone,
            context={'name_part': _name_part(user), 'link': _site_link()},
            metadata={'user_id': user.pk},
        ))
    return out


def _resolve_crm_abandoned(*, inactive_days: int = 14) -> List[AutomationCandidate]:
    cutoff = timezone.now() - timedelta(days=inactive_days)
    has_crm_q = Customer.objects.filter(user=OuterRef('pk'))
    recent_activity_q = CustomerActivity.objects.filter(
        customer__user=OuterRef('pk'),
        created_at__gte=cutoff,
    )
    out: List[AutomationCandidate] = []
    qs = (
        User.objects.filter(is_active=True)
        .annotate(has_crm=Exists(has_crm_q), recent_crm=Exists(recent_activity_q))
        .filter(has_crm=True, recent_crm=False)[:500]
    )
    for user in qs:
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        out.append(AutomationCandidate(
            trigger_key=f'crm_abandoned:{user.pk}',
            user=user,
            phone=phone,
            context={'name_part': _name_part(user), 'link': _site_link()},
            metadata={'user_id': user.pk},
        ))
    return out


def _resolve_license_inactive_usage(*, inactive_days: int = 14) -> List[AutomationCandidate]:
    now = timezone.now()
    cutoff = now - timedelta(days=inactive_days)
    active_license_q = License.objects.filter(
        order__user=OuterRef('pk'),
        status='active',
    ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
    had_usage_q = ClientAppEvent.objects.filter(user=OuterRef('pk'))
    out: List[AutomationCandidate] = []
    qs = (
        User.objects.filter(is_active=True)
        .annotate(has_active=Exists(active_license_q), had_usage=Exists(had_usage_q))
        .filter(has_active=True, had_usage=True)[:500]
    )
    for user in qs:
        recent_event = ClientAppEvent.objects.filter(user_id=user.pk, created_at__gte=cutoff).exists()
        recent_ds = Dataset.objects.filter(user_id=user.pk, updated_at__gte=cutoff).exists()
        recent_login = user.last_login and user.last_login >= cutoff
        if recent_event or recent_ds or recent_login:
            continue
        phone = _phone_ok(getattr(user, 'phone', ''))
        if not phone:
            continue
        out.append(AutomationCandidate(
            trigger_key=f'license_inactive:{user.pk}',
            user=user,
            phone=phone,
            context={'name_part': _name_part(user), 'link': _site_link()},
            metadata={'user_id': user.pk},
        ))
    return out


def _resolve_churn_risk_alert(*, now=None) -> List[AutomationCandidate]:
    now = now or timezone.now()
    horizon = now + timedelta(days=7)
    inactive_cutoff = now - timedelta(days=10)
    count = 0
    active_licenses = License.objects.filter(
        order__status='paid',
        status='active',
        expires_at__isnull=False,
        expires_at__gt=now,
        expires_at__lte=horizon,
    ).select_related('order__user')[:500]
    for lic in active_licenses:
        user = lic.order.user
        if not user:
            continue
        if ClientAppEvent.objects.filter(user_id=user.pk).exists():
            recent = (
                (user.last_login and user.last_login >= inactive_cutoff)
                or ClientAppEvent.objects.filter(user_id=user.pk, created_at__gte=inactive_cutoff).exists()
                or Dataset.objects.filter(user_id=user.pk, updated_at__gte=inactive_cutoff).exists()
            )
            if not recent:
                count += 1
    if not count:
        return []
    bucket = _local_now(now).date().isoformat()
    return [AutomationCandidate(
        trigger_key=f'churn_risk:{bucket}',
        metadata={'count': count, 'alert': True},
    )]


def _resolve_revenue_drop_alert(*, now=None) -> List[AutomationCandidate]:
    from accounts.services.admin_management_assistant import _revenue_drop_pct

    cur, prev, delta = _revenue_drop_pct()
    if delta is None or delta > -15:
        return []
    bucket = _local_now(now).date().isoformat()
    return [AutomationCandidate(
        trigger_key=f'revenue_drop:{bucket}',
        metadata={'count': abs(int(delta)), 'cur': cur, 'prev': prev, 'alert': True},
    )]


def _resolve_sms_failure_alert(*, now=None) -> List[AutomationCandidate]:
    from accounts.models import SmsMessageLog

    since = timezone.now() - timedelta(hours=6)
    failed = SmsMessageLog.objects.filter(status=SmsMessageLog.Status.FAILED, created_at__gte=since).count()
    if failed < 5:
        return []
    local = _local_now(now)
    bucket = local.strftime('%Y-%m-%d-%H')
    return [AutomationCandidate(
        trigger_key=f'sms_failures:{bucket}',
        metadata={'count': failed, 'alert': True},
    )]


AUDIENCE_RESOLVERS: Dict[str, Callable[[], List[AutomationCandidate]]] = {
    'license_expiring_3d': lambda: _resolve_license_expiring(within_days=3),
    'expired_renewal_campaign': lambda: _resolve_expired_renewal(within_days=14),
    'pending_recovery': lambda: _resolve_pending_orders(stale_hours=2),
    'pending_recovery_discount': lambda: _resolve_pending_orders_discount(stale_hours=24),
    'failed_payment_followup': lambda: _resolve_failed_orders(days_lookback=1),
    'users_onboarding': lambda: _resolve_users_onboarding(min_hours=24),
    'returning_customer_renewal': _resolve_returning_customer_renewal,
    'purchase_no_download': lambda: _resolve_purchase_no_download(min_hours=24),
    'windows_activation_nudge': _resolve_windows_download_no_activate,
    'windows_activate_no_launch': _resolve_windows_activate_no_launch,
    'launch_no_dataset': lambda: _resolve_launch_no_dataset(hours=48),
    'dataset_no_crm': lambda: _resolve_dataset_no_crm(days=3),
    'crm_not_started_nudge': _resolve_crm_not_started,
    'crm_abandoned_nudge': lambda: _resolve_crm_abandoned(inactive_days=14),
    'license_inactive_usage': lambda: _resolve_license_inactive_usage(inactive_days=14),
    'churn_risk_alert': _resolve_churn_risk_alert,
    'revenue_drop_alert': _resolve_revenue_drop_alert,
    'sms_balance_low': _resolve_sms_balance_alert,
    'sms_failure_alert': _resolve_sms_failure_alert,
    'stale_tickets_alert': lambda: _resolve_stale_tickets_alert(hours=12),
}


def resolve_audience(rule: ManagementAutomationRule) -> List[AutomationCandidate]:
    resolver = AUDIENCE_RESOLVERS.get(rule.key)
    if resolver:
        return resolver()
    if rule.segment_key:
        from accounts.services.admin_marketing import build_segment_recipients
        params = dict(rule.conditions or {})
        stale_hours = params.get('stale_hours')
        days_lookback = params.get('days_lookback')
        product_id = params.get('product_id')
        recipients = build_segment_recipients(
            rule.segment_key,
            stale_hours=stale_hours,
            days_lookback=days_lookback,
            product_id=product_id,
            limit=rule.max_recipients_per_run or 50,
        )
        out = []
        for idx, rec in enumerate(recipients):
            order_id = rec.context.get('order_id')
            trig = f'segment:{rule.segment_key}:{order_id or rec.phone or idx}'
            out.append(AutomationCandidate(
                trigger_key=trig,
                user=rec.user,
                phone=rec.phone,
                context=dict(rec.context),
                metadata={'segment_key': rule.segment_key},
            ))
        return out
    return []


def revalidate_candidate(rule: ManagementAutomationRule, candidate: AutomationCandidate) -> Tuple[bool, str]:
    meta = candidate.metadata or {}
    now = timezone.now()

    if rule.key in ('license_expiring_3d',):
        lic_id = meta.get('license_id')
        if not lic_id:
            return False, 'missing_license'
        lic = License.objects.filter(pk=lic_id).select_related('order').first()
        if not lic or lic.status != 'active':
            return False, 'license_not_active'
        if lic.expires_at and lic.expires_at <= now:
            return False, 'already_expired'
        if lic.order.user_id and _has_active_license(lic.order.user_id, now=now):
            if License.objects.filter(
                pk=lic_id, status='active',
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).exists():
                pass
            else:
                return False, 'renewed'
        return True, ''

    if rule.key == 'expired_renewal_campaign':
        user_id = meta.get('user_id')
        if user_id and _has_active_license(user_id, now=now):
            return False, 'renewed'
        return True, ''

    if rule.key in ('pending_recovery', 'pending_recovery_discount'):
        order_id = parse_order_id(meta.get('order_id'))
        if not order_id:
            return False, 'missing_order'
        order = Order.objects.filter(pk=order_id).first()
        if not order or order.status not in PENDING_ORDER_STATUSES:
            return False, 'order_paid_or_gone'
        if order.user_id and Order.objects.filter(
            user_id=order.user_id,
            status='paid',
            paid_at__isnull=False,
            paid_at__gte=order.created_at,
        ).exclude(pk=order.pk).exists():
            return False, 'user_has_paid_order_after'
        if order.user_id and _has_active_license(order.user_id, now=now):
            if not order.renewal_license_id:
                return False, 'has_valid_access'
        return True, ''

    if rule.key == 'failed_payment_followup':
        order_id = meta.get('order_id')
        if not order_id:
            return False, 'missing_order'
        order = Order.objects.filter(pk=order_id).first()
        if not order or order.status != 'failed':
            return False, 'order_not_failed'
        if order.user_id and Order.objects.filter(
            user_id=order.user_id, status='paid', created_at__gte=order.created_at,
        ).exists():
            return False, 'later_paid'
        return True, ''

    if rule.key == 'users_onboarding':
        user_id = meta.get('user_id')
        if user_id and _has_active_license(user_id, now=now):
            return False, 'has_license'
        return True, ''

    if rule.key == 'windows_activation_nudge':
        user_id = meta.get('user_id')
        if user_id and LicenseActivation.objects.filter(
            WINDOWS_ACTIVATION_Q, license__order__user_id=user_id,
        ).exists():
            return False, 'activated'
        return True, ''

    if rule.key == 'windows_activate_no_launch':
        user_id = meta.get('user_id')
        if user_id and ClientAppEvent.objects.filter(
            user_id=user_id, event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
        ).exists():
            return False, 'launched'
        return True, ''

    if rule.key == 'returning_customer_renewal':
        user_id = meta.get('user_id')
        if user_id and _has_active_license(user_id, now=now):
            return False, 'renewed'
        return True, ''

    if rule.key == 'purchase_no_download':
        user_id = meta.get('user_id')
        if user_id and DownloadLog.objects.filter(user_id=user_id).exists():
            return False, 'downloaded'
        return True, ''

    if rule.key == 'launch_no_dataset':
        user_id = meta.get('user_id')
        if user_id and Dataset.objects.filter(user_id=user_id).exists():
            return False, 'has_dataset'
        return True, ''

    if rule.key == 'dataset_no_crm':
        user_id = meta.get('user_id')
        cutoff = now - timedelta(days=30)
        if user_id and _crm_user_engaged(user_id, since=cutoff):
            return False, 'crm_started'
        return True, ''

    if rule.key == 'crm_abandoned_nudge':
        user_id = meta.get('user_id')
        cutoff = now - timedelta(days=14)
        if user_id and CustomerActivity.objects.filter(
            customer__user_id=user_id, created_at__gte=cutoff,
        ).exists():
            return False, 'crm_active'
        return True, ''

    if rule.key == 'license_inactive_usage':
        user_id = meta.get('user_id')
        if user_id and not _has_active_license(user_id, now=now):
            return False, 'license_not_active'
        cutoff = now - timedelta(days=14)
        if user_id:
            user = User.objects.filter(pk=user_id).first()
            if user and (
                (user.last_login and user.last_login >= cutoff)
                or ClientAppEvent.objects.filter(user_id=user_id, created_at__gte=cutoff).exists()
                or Dataset.objects.filter(user_id=user_id, updated_at__gte=cutoff).exists()
            ):
                return False, 'active_again'
        return True, ''

    if rule.key in ('sms_balance_low', 'stale_tickets_alert', 'churn_risk_alert', 'revenue_drop_alert', 'sms_failure_alert'):
        return True, ''

    if rule.key == 'crm_not_started_nudge':
        user_id = meta.get('user_id')
        cutoff = now - timedelta(days=30)
        if user_id and _crm_user_engaged(user_id, since=cutoff):
            return False, 'crm_started'
        return True, ''

    return True, ''


def _trigger_already_handled(rule: ManagementAutomationRule, trigger_key: str) -> bool:
    return ManagementAutomationRecipient.objects.filter(
        rule=rule,
        trigger_key=trigger_key,
        status__in=TERMINAL_RECIPIENT_STATUSES,
    ).exists()


def _user_cooldown_active(rule: ManagementAutomationRule, user_id: int, *, now=None) -> bool:
    if not user_id or not rule.cooldown_days:
        return False
    since = (now or timezone.now()) - timedelta(days=rule.cooldown_days)
    sent_count = ManagementAutomationRecipient.objects.filter(
        rule=rule,
        user_id=user_id,
        status__in=(
            ManagementAutomationRecipient.Status.SENT,
            ManagementAutomationRecipient.Status.ALERT,
        ),
        sent_at__gte=since,
        execution__dry_run=False,
    ).count()
    return sent_count >= max(1, rule.max_sends_per_user)


def _order_id_from_metadata(meta: Dict[str, Any]):
    return parse_order_id((meta or {}).get('order_id'))


def build_preview_message_context(rule: ManagementAutomationRule, candidate: AutomationCandidate) -> Tuple[Dict[str, str], List[str]]:
    """Context پیام برای Preview — شامل تخفیف نمایشی در صورت نیاز."""
    from accounts.services.discount_engine import enrich_preview_discount_context

    ctx = enrich_candidate_context(candidate.context or {}, user=candidate.user)
    extra_warnings: List[str] = []
    if rule.key in RULE_DISCOUNT_POLICIES:
        ctx, extra_warnings = enrich_preview_discount_context(
            ctx,
            rule_key=rule.key,
            user=candidate.user,
            order_id=_order_id_from_metadata(candidate.metadata),
        )
    return ctx, extra_warnings


def _message_for_rule(rule: ManagementAutomationRule, context: Dict[str, str], *, user=None) -> Tuple[str, str]:
    """Render پیام Rule — (body, skip_reason). skip_reason غیرخالی یعنی ارسال نشود."""
    template = get_effective_template(rule)
    if not template:
        return '', 'missing_template'

    enriched = enrich_candidate_context(context, user=user)
    result = render_template(
        template,
        enriched,
        rule_key=rule.key,
        strict_send=True,
    )
    if not result.ok:
        reason = 'missing_variables'
        if result.missing_variables:
            reason = f'missing_variables:{",".join(result.missing_variables[:3])}'
        elif result.error:
            reason = result.error[:200]
        return '', reason
    return result.message, ''


def _maybe_apply_discount(
    rule: ManagementAutomationRule,
    candidate: AutomationCandidate,
    *,
    dry_run: bool = False,
) -> Tuple[Dict[str, str], str]:
    """صدور تخفیف در صورت نیاز Rule — (context, skip_reason)."""
    if rule.key not in RULE_DISCOUNT_POLICIES:
        return candidate.context, ''
    if not candidate.user:
        return candidate.context, 'missing_user_for_discount'
    order_id = _order_id_from_metadata(candidate.metadata)
    ctx, err = enrich_context_with_discount(
        candidate.context,
        rule_key=rule.key,
        user=candidate.user,
        order_id=order_id,
        metadata=candidate.metadata,
        dry_run=dry_run,
    )
    if err and err != 'active_exists' and not dry_run:
        if not ctx.get('discount_code') and not ctx.get('code'):
            return ctx, f'discount:{err}'
    if dry_run:
        return ctx, ''
    if not (ctx.get('discount_code') or ctx.get('code')):
        return ctx, 'discount_not_issued'
    return ctx, ''


def _sms_purpose_for_rule(rule: ManagementAutomationRule) -> str:
    if rule.key in ('pending_recovery', 'pending_recovery_discount', 'failed_payment_followup'):
        return PURPOSE_RECOVERY
    if rule.key in ('license_expiring_3d', 'expired_renewal_campaign', 'returning_customer_renewal'):
        return PURPOSE_LICENSE_RENEWAL
    return PURPOSE_MARKETING


def _process_candidate(
    *,
    rule: ManagementAutomationRule,
    execution: ManagementAutomationExecution,
    candidate: AutomationCandidate,
    dry_run: bool,
) -> str:
    """Returns outcome: success | failed | skipped | deduped."""
    from accounts.services.automation_contact_policy import check_global_contact_policy

    if _trigger_already_handled(rule, candidate.trigger_key):
        execution.skipped_count += 1
        return 'deduped'

    ok, reason = revalidate_candidate(rule, candidate)
    if not ok:
        _, deduped = _persist_recipient(
            rule=rule,
            execution=execution,
            candidate=candidate,
            status=ManagementAutomationRecipient.Status.SKIPPED,
            skipped_reason=reason[:200],
        )
        if deduped:
            return 'deduped'
        execution.skipped_count += 1
        return 'skipped'

    user_id = getattr(candidate.user, 'pk', None) or candidate.metadata.get('user_id')
    if user_id and _user_cooldown_active(rule, user_id):
        execution.skipped_count += 1
        return 'skipped'

    if rule.action_type == ManagementAutomationRule.ActionType.MANAGEMENT_ALERT:
        status = (
            ManagementAutomationRecipient.Status.DRY_RUN if dry_run
            else ManagementAutomationRecipient.Status.ALERT
        )
        _, deduped = _persist_recipient(
            rule=rule,
            execution=execution,
            candidate=candidate,
            status=status,
            sent_at=timezone.now(),
        )
        if deduped:
            execution.skipped_count += 1
            return 'deduped'
        execution.success_count += 1
        return 'success'

    if rule.action_type == ManagementAutomationRule.ActionType.MANUAL_REVIEW:
        status = (
            ManagementAutomationRecipient.Status.DRY_RUN if dry_run
            else ManagementAutomationRecipient.Status.ALERT
        )
        _, deduped = _persist_recipient(
            rule=rule,
            execution=execution,
            candidate=candidate,
            status=status,
            sent_at=timezone.now(),
        )
        if deduped:
            execution.skipped_count += 1
            return 'deduped'
        execution.success_count += 1
        return 'success'

    if rule.action_type != ManagementAutomationRule.ActionType.SEND_SMS:
        execution.skipped_count += 1
        return 'skipped'

    template_check = rule_template_is_valid(rule)
    if not template_check.ok:
        execution.skipped_count += 1
        return 'skipped'

    phone = _phone_ok(candidate.phone)
    if not phone:
        execution.skipped_count += 1
        return 'skipped'

    if user_id:
        allowed, policy_reason = check_global_contact_policy(
            rule, user_id=int(user_id), dry_run=dry_run,
        )
        if not allowed:
            _, deduped = _persist_recipient(
                rule=rule,
                execution=execution,
                candidate=candidate,
                status=ManagementAutomationRecipient.Status.SKIPPED,
                skipped_reason=policy_reason[:200],
            )
            if deduped:
                return 'deduped'
            execution.skipped_count += 1
            return 'skipped'

    purpose = _sms_purpose_for_rule(rule)
    if not is_send_allowed(phone, purpose=purpose, user=candidate.user):
        _, deduped = _persist_recipient(
            rule=rule,
            execution=execution,
            candidate=candidate,
            status=ManagementAutomationRecipient.Status.SKIPPED,
            skipped_reason='suppressed',
        )
        if deduped:
            return 'deduped'
        execution.skipped_count += 1
        return 'skipped'

    send_context = dict(candidate.context)
    discount_skip = ''
    if rule.key in RULE_DISCOUNT_POLICIES:
        send_context, discount_skip = _maybe_apply_discount(rule, candidate, dry_run=dry_run)
        if discount_skip:
            _, deduped = _persist_recipient(
                rule=rule,
                execution=execution,
                candidate=candidate,
                status=ManagementAutomationRecipient.Status.SKIPPED,
                skipped_reason=discount_skip[:200],
            )
            if deduped:
                return 'deduped'
            execution.skipped_count += 1
            return 'skipped'

    body, render_reason = _message_for_rule(rule, send_context, user=candidate.user)
    if not body:
        _, deduped = _persist_recipient(
            rule=rule,
            execution=execution,
            candidate=candidate,
            status=ManagementAutomationRecipient.Status.SKIPPED,
            skipped_reason=(render_reason or 'render_failed')[:200],
        )
        if deduped:
            return 'deduped'
        execution.skipped_count += 1
        return 'skipped'

    if dry_run:
        _, deduped = _persist_recipient(
            rule=rule,
            execution=execution,
            candidate=candidate,
            status=ManagementAutomationRecipient.Status.DRY_RUN,
            sent_at=timezone.now(),
            metadata={**candidate.metadata, 'body_preview': body[:200]},
        )
        if deduped:
            execution.skipped_count += 1
            return 'deduped'
        execution.success_count += 1
        return 'success'

    recipient, deduped = _persist_recipient(
        rule=rule,
        execution=execution,
        candidate=candidate,
        status=ManagementAutomationRecipient.Status.PENDING,
    )
    if deduped or not recipient:
        execution.skipped_count += 1
        return 'deduped'

    claimed = ManagementAutomationRecipient.objects.filter(
        pk=recipient.pk,
        status=ManagementAutomationRecipient.Status.PENDING,
    ).update(
        status=ManagementAutomationRecipient.Status.SENT,
        sent_at=timezone.now(),
    )
    if claimed != 1:
        execution.skipped_count += 1
        return 'deduped'

    recipient.refresh_from_db()
    ok_send, sms_log = notify_marketing(phone=phone, text=body)
    if ok_send:
        recipient.metadata = _safe_metadata({**recipient.metadata, 'sms_log_id': sms_log.pk})
        recipient.save(update_fields=['metadata'])
        execution.success_count += 1
        return 'success'

    recipient.status = ManagementAutomationRecipient.Status.FAILED
    recipient.skipped_reason = (getattr(sms_log, 'error_message', '') or 'send_failed')[:200]
    recipient.save(update_fields=['status', 'skipped_reason'])
    execution.failed_count += 1
    return 'failed'


def classify_candidate_for_preview(
    rule: ManagementAutomationRule,
    candidate: AutomationCandidate,
) -> Tuple[str, str, str]:
    """Returns (status, reason_key, reason_label) — status: ready | skip."""
    if _trigger_already_handled(rule, candidate.trigger_key):
        return 'skip', 'deduped', SKIP_REASON_LABELS['deduped']

    ok, reason = revalidate_candidate(rule, candidate)
    if not ok:
        label = SKIP_REASON_LABELS.get(reason, reason or 'رد شده')
        return 'skip', reason, label

    user_id = getattr(candidate.user, 'pk', None) or candidate.metadata.get('user_id')
    if user_id and _user_cooldown_active(rule, user_id):
        return 'skip', 'cooldown', SKIP_REASON_LABELS['cooldown']

    return 'ready', '', 'آماده ارسال'


def run_rule(
    rule: ManagementAutomationRule,
    *,
    dry_run: bool = False,
    force: bool = False,
    now=None,
    staff_override: bool = False,
) -> Optional[ManagementAutomationExecution]:
    now = now or timezone.now()

    if not staff_override:
        if not rule.is_active or rule.is_paused:
            return None

    if not rule_is_due(rule, now=now, force=force):
        return None

    if in_quiet_hours(rule, now=now) and rule.action_type == ManagementAutomationRule.ActionType.SEND_SMS:
        return None

    if (
        rule.action_type == ManagementAutomationRule.ActionType.SEND_SMS
        and not rule_template_is_valid(rule).ok
    ):
        execution = ManagementAutomationExecution.objects.create(
            rule=rule,
            dry_run=dry_run,
            status=ManagementAutomationExecution.Status.FAILED,
            error_summary='قالب پیام نامعتبر است — ارسال متوقف شد.',
            finished_at=now,
        )
        return execution

    with transaction.atomic():
        locked = ManagementAutomationRule.objects.select_for_update().get(pk=rule.pk)
        if not rule_is_due(locked, now=now, force=force):
            return None
        locked.last_run_at = now
        locked.save(update_fields=['last_run_at', 'updated_at'])

    execution = ManagementAutomationExecution.objects.create(
        rule=rule,
        dry_run=dry_run,
        status=ManagementAutomationExecution.Status.RUNNING,
    )

    try:
        raw_candidates = resolve_audience(rule)
        execution.matched_count = len(raw_candidates)
        limit = max(1, rule.max_recipients_per_run or 50)
        eligible = _filter_eligible_candidates(rule, raw_candidates, dry_run=dry_run)
        candidates = eligible[:limit]

        for candidate in candidates:
            execution.processed_count += 1
            try:
                _process_candidate(
                    rule=rule,
                    execution=execution,
                    candidate=candidate,
                    dry_run=dry_run,
                )
            except Exception as exc:
                logger.exception('mgmt automation candidate failed rule=%s', rule.key)
                execution.failed_count += 1
                err = (execution.error_summary or '') + f'; {exc}'[:120]
                execution.error_summary = err.strip('; ')[:500]

        execution.status = ManagementAutomationExecution.Status.COMPLETED
    except Exception as exc:
        logger.exception('mgmt automation rule failed rule=%s', rule.key)
        execution.status = ManagementAutomationExecution.Status.FAILED
        execution.error_summary = str(exc)[:500]
    finally:
        execution.finished_at = timezone.now()
        execution.save()

    return execution


def run_management_automations(
    *,
    dry_run: bool = False,
    rule_key: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Runner مرکزی — fail-safe برای هر Rule."""
    qs = ManagementAutomationRule.objects.filter(is_active=True, is_paused=False)
    if rule_key:
        qs = qs.filter(key=rule_key)

    summary = {
        'dry_run': dry_run,
        'rules_examined': 0,
        'rules_run': 0,
        'rules_skipped': 0,
        'executions': [],
        'errors': [],
    }

    for rule in qs.order_by('key'):
        summary['rules_examined'] += 1
        try:
            execution = run_rule(rule, dry_run=dry_run, force=force)
            if execution:
                summary['rules_run'] += 1
                summary['executions'].append({
                    'rule_key': rule.key,
                    'execution_id': execution.pk,
                    'matched': execution.matched_count,
                    'success': execution.success_count,
                    'failed': execution.failed_count,
                    'skipped': execution.skipped_count,
                    'status': execution.status,
                })
            else:
                summary['rules_skipped'] += 1
        except Exception as exc:
            logger.exception('mgmt automation runner rule=%s', rule.key)
            summary['errors'].append({'rule_key': rule.key, 'error': str(exc)[:200]})

    return summary
