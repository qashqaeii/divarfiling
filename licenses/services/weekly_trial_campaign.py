"""کمپین هدیه ۷ روز دسترسی حرفه‌ای — eligibility، اعطا و پیامک."""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any, Iterable, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q, QuerySet
from django.utils import timezone

from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from accounts.services.growth_suppression import PURPOSE_MARKETING, is_send_allowed
from accounts.services.notifications import _send_templated_or_simple_sms
from licenses.models import AuditLog, License, LicenseActivation, LicenseCampaignGrant
from licenses.utils import generate_license_key
from shop.models import LicensePlan, Order, Product
from shop.services.license_entitlement import LICENSE_ACCESS_ORDER_STATUSES
from workspace.services.access import (
    _assigned_active_seat_qs,
    _assigned_license_qs,
    has_active_bot_license,
    has_purchased_bot_license,
)

User = get_user_model()
logger = logging.getLogger(__name__)

CAMPAIGN_DURATION_DAYS = 7
DEFAULT_CAMPAIGN_KEY = 'weekly_professional_gift_v1'
SMS_PURPOSE = 'weekly_trial_campaign'
ESTIMATED_SMS_COST_TOMAN = Decimal('300')


class WeeklyTrialCampaignError(Exception):
    pass


@dataclass
class EligibilityResult:
    eligible: bool
    reason: str = ''


@dataclass
class CampaignRunStats:
    campaign_key: str
    dry_run: bool = False
    eligible_count: int = 0
    excluded_counts: dict[str, int] = field(default_factory=dict)
    grants_attempted: int = 0
    grants_created: int = 0
    grants_skipped_existing: int = 0
    grants_failed: int = 0
    sms_attempted: int = 0
    sms_sent: int = 0
    sms_failed: int = 0
    sms_skipped: int = 0
    estimated_sms_cost_toman: Decimal = Decimal('0')
    sample_eligible_user_ids: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'campaign_key': self.campaign_key,
            'dry_run': self.dry_run,
            'eligible_count': self.eligible_count,
            'excluded_counts': self.excluded_counts,
            'grants_attempted': self.grants_attempted,
            'grants_created': self.grants_created,
            'grants_skipped_existing': self.grants_skipped_existing,
            'grants_failed': self.grants_failed,
            'sms_attempted': self.sms_attempted,
            'sms_sent': self.sms_sent,
            'sms_failed': self.sms_failed,
            'sms_skipped': self.sms_skipped,
            'estimated_sms_cost_toman': str(self.estimated_sms_cost_toman),
            'sample_eligible_user_ids': self.sample_eligible_user_ids,
        }


def default_campaign_key() -> str:
    return (
        getattr(settings, 'WEEKLY_TRIAL_CAMPAIGN_DEFAULT_KEY', None)
        or DEFAULT_CAMPAIGN_KEY
    )


def sms_batch_size() -> int:
    return int(
        getattr(settings, 'WEEKLY_TRIAL_CAMPAIGN_SMS_BATCH_SIZE', None)
        or getattr(settings, 'LEAD_CAMPAIGN_SEND_BATCH_SIZE', 10)
        or 10
    )


def resolve_professional_gift_plan() -> LicensePlan:
    product = (
        Product.objects.filter(slug='professional', is_active=True).first()
        or Product.objects.filter(is_active=True).order_by('order', 'pk').first()
    )
    if not product:
        raise WeeklyTrialCampaignError('محصول فعال برای صدور لایسنس کمپین یافت نشد.')

    plan = (
        LicensePlan.objects.filter(
            product=product,
            plan_type='monthly',
            allow_bulk_purchase=False,
            is_active=True,
        )
        .order_by('order', 'pk')
        .first()
    )
    if not plan:
        plan = (
            LicensePlan.objects.filter(product=product, is_active=True)
            .order_by('order', 'pk')
            .first()
        )
    if not plan:
        raise WeeklyTrialCampaignError('پلن فعال برای کمپین یافت نشد.')
    return plan


def _user_has_valid_license_entitlement(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    if has_active_bot_license(user):
        return True
    now = timezone.now()
    if (
        License.objects.filter(
            order__user=user,
            order__status__in=LICENSE_ACCESS_ORDER_STATUSES,
        )
        .exclude(status__in=['suspended', 'expired'])
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .exists()
    ):
        return True
    if _assigned_license_qs(user).exists():
        return True
    if _assigned_active_seat_qs(user).exists():
        return True
    seat_valid = LicenseActivation.objects.filter(
        assigned_user=user,
        license__order__status__in=LICENSE_ACCESS_ORDER_STATUSES,
    ).exclude(
        license__status__in=['suspended', 'expired'],
    ).filter(
        Q(license__expires_at__isnull=True) | Q(license__expires_at__gt=now),
    ).exists()
    return seat_valid


def evaluate_user_eligibility(user, campaign_key: str) -> EligibilityResult:
    if not user or not user.is_active:
        return EligibilityResult(False, 'inactive_user')
    if LicenseCampaignGrant.objects.filter(
        user=user,
        campaign_key=campaign_key,
        status=LicenseCampaignGrant.Status.GRANTED,
    ).exists():
        return EligibilityResult(False, 'already_granted_campaign')
    if has_purchased_bot_license(user):
        return EligibilityResult(False, 'has_paid_purchase')
    if _user_has_valid_license_entitlement(user):
        return EligibilityResult(False, 'has_license_entitlement')
    return EligibilityResult(True, '')


def _already_granted_subquery(campaign_key: str):
    return LicenseCampaignGrant.objects.filter(
        user_id=OuterRef('pk'),
        campaign_key=campaign_key,
        status=LicenseCampaignGrant.Status.GRANTED,
    )


def _paid_purchase_subquery():
    return Order.objects.filter(user_id=OuterRef('pk'), status='paid')


def eligible_users_queryset(campaign_key: str) -> QuerySet:
    now = timezone.now()
    valid_license_on_order = License.objects.filter(
        order__user_id=OuterRef('pk'),
        order__status__in=LICENSE_ACCESS_ORDER_STATUSES,
    ).exclude(status__in=['suspended', 'expired']).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now),
    )
    assigned_key = License.objects.filter(
        assigned_user_id=OuterRef('pk'),
        order__status__in=LICENSE_ACCESS_ORDER_STATUSES,
    ).exclude(status__in=['suspended', 'expired']).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now),
    )
    active_seat = LicenseActivation.objects.filter(
        assigned_user_id=OuterRef('pk'),
        is_active=True,
        license__order__status__in=LICENSE_ACCESS_ORDER_STATUSES,
        license__status='active',
    ).filter(
        Q(license__expires_at__isnull=True) | Q(license__expires_at__gt=now),
    ).exclude(license__status__in=['suspended', 'expired'])
    return (
        User.objects.filter(is_active=True)
        .exclude(Exists(_paid_purchase_subquery()))
        .exclude(Exists(_already_granted_subquery(campaign_key)))
        .exclude(Exists(valid_license_on_order))
        .exclude(Exists(assigned_key))
        .exclude(Exists(active_seat))
        .order_by('pk')
    )


def _grant_track_id(campaign_key: str, user_id: int) -> str:
    safe_key = ''.join(ch for ch in campaign_key if ch.isalnum() or ch in '-_')[:24]
    return f'GRANT-{safe_key}-{user_id}'[:50]


def _campaign_expires_at() -> timezone.datetime:
    return timezone.now() + timedelta(days=CAMPAIGN_DURATION_DAYS)


@transaction.atomic
def grant_weekly_trial_to_user(
    user,
    *,
    campaign_key: str,
    plan: LicensePlan,
    dry_run: bool = False,
) -> tuple[LicenseCampaignGrant | None, str]:
    """
    اعطای هدیه به یک کاربر — idempotent per (user, campaign_key).
    خروجی: (رکورد grant یا None در dry-run، پیام وضعیت)
    """
    existing = LicenseCampaignGrant.objects.filter(
        user=user,
        campaign_key=campaign_key,
    ).first()
    if existing and existing.status == LicenseCampaignGrant.Status.GRANTED and existing.license_id:
        return existing, 'already_granted'

    elig = evaluate_user_eligibility(user, campaign_key)
    if not elig.eligible:
        return None, elig.reason or 'not_eligible'

    if dry_run:
        return None, 'dry_run_would_grant'

    grant_row = existing
    if not grant_row:
        try:
            grant_row = LicenseCampaignGrant.objects.create(
                user=user,
                campaign_key=campaign_key,
                status=LicenseCampaignGrant.Status.GRANTED,
                metadata={'source': 'weekly_trial_campaign'},
            )
        except IntegrityError:
            grant_row = LicenseCampaignGrant.objects.select_for_update().get(
                user=user,
                campaign_key=campaign_key,
            )
            if grant_row.status == LicenseCampaignGrant.Status.GRANTED:
                return grant_row, 'already_granted'

    grant_row = LicenseCampaignGrant.objects.select_for_update().get(pk=grant_row.pk)

    if grant_row.license_id and grant_row.order_id:
        return grant_row, 'already_granted'

    now = timezone.now()
    expires_at = _campaign_expires_at()
    track = _grant_track_id(campaign_key, user.pk)

    order = Order.objects.create(
        user=user,
        product=plan.product,
        plan=plan,
        quantity=1,
        amount=Decimal('0'),
        original_price=Decimal('0'),
        discount_amount=Decimal('0'),
        status='granted',
        zibal_track_id=track,
    )

    license_obj = License.objects.create(
        order=order,
        license_key=generate_license_key(order),
        plan=plan,
        status='active',
        max_activations=plan.max_activations,
        expires_at=expires_at,
    )
    AuditLog.objects.create(
        license=license_obj,
        action_type='activation',
        details={
            'event': 'weekly_trial_campaign_granted',
            'campaign_key': campaign_key,
            'duration_days': CAMPAIGN_DURATION_DAYS,
            'order_id': str(order.pk),
        },
    )

    grant_row.order = order
    grant_row.license = license_obj
    grant_row.status = LicenseCampaignGrant.Status.GRANTED
    grant_row.granted_at = now
    grant_row.expires_at = expires_at
    grant_row.error_message = ''
    grant_row.save(
        update_fields=[
            'order',
            'license',
            'status',
            'granted_at',
            'expires_at',
            'error_message',
            'updated_at',
        ],
    )
    logger.info(
        'weekly_trial_campaign granted user_id=%s campaign=%s license_id=%s',
        user.pk,
        campaign_key,
        license_obj.pk,
    )
    return grant_row, 'granted'


def _default_sms_text() -> str:
    return (
        'فایلینگ دیوار: ۷ روز دسترسی حرفه‌ای میزکار، استخراج و هوش مصنوعی برای شما فعال شد. '
        'وارد میزکار شوید و امکانات را امتحان کنید.'
    )


def _user_may_receive_campaign_sms(user) -> tuple[bool, str]:
    if getattr(user, 'marketing_sms_opt_out', False):
        return False, 'marketing_opt_out'
    phone = normalize_phone(getattr(user, 'phone', '') or '')
    if not phone or not is_valid_iran_mobile(phone):
        return False, 'invalid_phone'
    if not is_send_allowed(phone, purpose=PURPOSE_MARKETING, user=user):
        return False, 'suppressed'
    return True, ''


@transaction.atomic
def send_campaign_sms_for_grant(grant: LicenseCampaignGrant) -> tuple[bool, str]:
    grant = LicenseCampaignGrant.objects.select_for_update().select_related('user', 'license').get(
        pk=grant.pk,
    )
    if grant.status != LicenseCampaignGrant.Status.GRANTED or not grant.license_id:
        return False, 'not_granted'
    if grant.sms_sent_at:
        return False, 'sms_already_sent'
    if not grant.license.is_valid():
        return False, 'license_not_valid'

    user = grant.user
    ok, reason = _user_may_receive_campaign_sms(user)
    if not ok:
        return False, reason

    phone = normalize_phone(user.phone)
    attrs = {
        'days': str(CAMPAIGN_DURATION_DAYS),
        'campaign': grant.campaign_key,
    }
    sent = _send_templated_or_simple_sms(
        phone,
        purpose=SMS_PURPOSE,
        text=_default_sms_text(),
        attributes=attrs,
    )
    if not sent:
        return False, 'sms_send_failed'

    from accounts.models import SmsMessageLog

    log = (
        SmsMessageLog.objects.filter(phone=phone, purpose=SMS_PURPOSE)
        .order_by('-pk')
        .first()
    )
    grant.sms_sent_at = timezone.now()
    grant.sms_log = log
    grant.save(update_fields=['sms_sent_at', 'sms_log', 'updated_at'])
    return True, 'sent'


def run_weekly_trial_campaign(
    *,
    campaign_key: str,
    dry_run: bool = False,
    apply: bool = False,
    send_sms: bool = False,
    limit: Optional[int] = None,
) -> CampaignRunStats:
    stats = CampaignRunStats(campaign_key=campaign_key, dry_run=dry_run)
    plan = resolve_professional_gift_plan()

    eligible_qs = eligible_users_queryset(campaign_key)
    stats.eligible_count = eligible_qs.count()
    stats.sample_eligible_user_ids = list(eligible_qs.values_list('pk', flat=True)[:10])

    if dry_run:
        inactive = User.objects.filter(is_active=False).count()
        paid_users = User.objects.filter(is_active=True, orders__status='paid').distinct().count()
        stats.excluded_counts = {
            'inactive_users': inactive,
            'users_with_paid_order_sample': paid_users,
        }
        sms_candidates = 0
        if stats.eligible_count:
            for user in eligible_qs.iterator(chunk_size=200):
                ok, _ = _user_may_receive_campaign_sms(user)
                if ok:
                    sms_candidates += 1
        stats.estimated_sms_cost_toman = ESTIMATED_SMS_COST_TOMAN * sms_candidates
        return stats

    if apply:
        users = eligible_qs
        if limit is not None:
            users = users[: max(0, int(limit))]
        for user in users.iterator(chunk_size=100):
            stats.grants_attempted += 1
            try:
                grant_row, status = grant_weekly_trial_to_user(
                    user,
                    campaign_key=campaign_key,
                    plan=plan,
                    dry_run=False,
                )
            except Exception as exc:
                stats.grants_failed += 1
                logger.exception('weekly_trial grant failed user_id=%s', user.pk)
                LicenseCampaignGrant.objects.update_or_create(
                    user=user,
                    campaign_key=campaign_key,
                    defaults={
                        'status': LicenseCampaignGrant.Status.FAILED,
                        'error_message': str(exc)[:500],
                    },
                )
                continue
            if status == 'granted':
                stats.grants_created += 1
            elif status == 'already_granted':
                stats.grants_skipped_existing += 1
            elif status in ('not_eligible', 'inactive_user', 'has_paid_purchase', 'has_license_entitlement'):
                stats.grants_failed += 1
            else:
                stats.grants_failed += 1

    if send_sms:
        pending = LicenseCampaignGrant.objects.filter(
            campaign_key=campaign_key,
            status=LicenseCampaignGrant.Status.GRANTED,
            sms_sent_at__isnull=True,
            license__isnull=False,
        ).select_related('user', 'license').order_by('pk')
        if limit is not None:
            pending = pending[: max(0, int(limit))]
        batch_cap = sms_batch_size()
        for grant in pending[:batch_cap]:
            stats.sms_attempted += 1
            try:
                ok, reason = send_campaign_sms_for_grant(grant)
            except Exception:
                stats.sms_failed += 1
                logger.exception('weekly_trial sms failed grant_id=%s', grant.pk)
                continue
            if ok:
                stats.sms_sent += 1
            elif reason in ('marketing_opt_out', 'invalid_phone', 'suppressed'):
                stats.sms_skipped += 1
            else:
                stats.sms_failed += 1

    return stats


def format_stats_lines(stats: CampaignRunStats) -> Iterable[str]:
    d = stats.to_dict()
    lines = [
        f"campaign_key={d['campaign_key']}",
        f"dry_run={d['dry_run']}",
        f"eligible_count={d['eligible_count']:,}",
        f"grants_attempted={d['grants_attempted']:,}",
        f"grants_created={d['grants_created']:,}",
        f"grants_skipped_existing={d['grants_skipped_existing']:,}",
        f"grants_failed={d['grants_failed']:,}",
        f"sms_attempted={d['sms_attempted']:,}",
        f"sms_sent={d['sms_sent']:,}",
        f"sms_skipped={d['sms_skipped']:,}",
        f"sms_failed={d['sms_failed']:,}",
    ]
    if stats.dry_run:
        lines.append(f"estimated_sms_cost_toman={d['estimated_sms_cost_toman']}")
        if stats.excluded_counts:
            lines.append(f"excluded_counts={stats.excluded_counts}")
    if stats.sample_eligible_user_ids:
        lines.append(f"sample_eligible_user_ids={stats.sample_eligible_user_ids}")
    return lines
