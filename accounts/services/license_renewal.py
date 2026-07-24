"""اتوماسیون تمدید لایسنس نزدیک به انقضا / ریسک ریزش."""
from __future__ import annotations

import hashlib
import logging
from datetime import timedelta
from typing import Any, Optional

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import GrowthJourney, MarketingAutomationActionLog, MarketingAutomationRun
from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from accounts.services.growth_journey import transition
from accounts.services.growth_suppression import PURPOSE_LICENSE_RENEWAL, is_send_allowed
from accounts.services.notifications import notify_marketing

logger = logging.getLogger(__name__)

FLOW_KEY = 'license_renewal'
STEP_EXPIRING = 'expiring_soon'
STEP_CHURN = 'churn_risk'

DEFAULT_TEMPLATE_EXPIRING = (
    'سلام{name_part}، لایسنس «{product}» تا {days} روز دیگر منقضی می‌شود. '
    'برای تمدید: {link}'
)
DEFAULT_TEMPLATE_CHURN = (
    'سلام{name_part}، لایسنس «{product}» منقضی شده است. '
    'برای تمدید و ادامه کار: {link}'
)


def _cfg_int(name: str, default: int) -> int:
    try:
        return int(getattr(settings, name, default) or default)
    except (TypeError, ValueError):
        return default


def renewal_enabled() -> bool:
    return bool(getattr(settings, 'LICENSE_RENEWAL_FLOW_ENABLED', True))


def expiring_within_days() -> int:
    return max(1, _cfg_int('LICENSE_RENEWAL_WITHIN_DAYS', 7))


def churn_after_days() -> int:
    return max(0, _cfg_int('LICENSE_RENEWAL_CHURN_AFTER_DAYS', 3))


def renewal_landing_url() -> str:
    return getattr(
        settings,
        'LICENSE_RENEWAL_LANDING_URL',
        'https://divarfiling.ir/pricing/',
    )


def _mask_phone(phone: str) -> str:
    phone = normalize_phone(phone)
    if len(phone) < 7:
        return phone
    return f'{phone[:4]}***{phone[-2:]}'


def _phone_hash(phone: str) -> str:
    return hashlib.sha256(normalize_phone(phone).encode('utf-8')).hexdigest()


def _idempotency_key(*, license_id: int, step_key: str, day_bucket: str) -> str:
    return f'licren:{license_id}:{step_key}:{day_bucket}'


def _name_part(user) -> str:
    name = (getattr(user, 'first_name', '') or '').strip()
    return f' {name}' if name else ''


def _render_body(*, user, product_title: str, days: int, step_key: str) -> str:
    catalog = getattr(settings, 'LICENSE_RENEWAL_TEMPLATES', None) or {}
    if step_key == STEP_CHURN:
        template = catalog.get('churn') or DEFAULT_TEMPLATE_CHURN
    else:
        template = catalog.get('expiring') or DEFAULT_TEMPLATE_EXPIRING
    return (
        template
        .replace('{name_part}', _name_part(user))
        .replace('{product}', product_title or 'فایلینگ دیوار')
        .replace('{days}', str(days))
        .replace('{link}', renewal_landing_url())
        .replace('{code}', '')
    )


def iter_renewal_candidates(*, now=None) -> list[dict[str, Any]]:
    """لایسنس‌های نزدیک انقضا یا تازه منقضی‌شده."""
    from licenses.models import License

    now = now or timezone.now()
    within = expiring_within_days()
    churn_grace = churn_after_days()
    horizon = now + timedelta(days=within)
    churn_since = now - timedelta(days=churn_grace)

    candidates: list[dict[str, Any]] = []

    expiring = (
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
    for lic in expiring:
        user = lic.order.user
        phone = normalize_phone(getattr(user, 'phone', '') or '')
        if not phone or not is_valid_iran_mobile(phone):
            continue
        days_left = max(1, (lic.expires_at - now).days)
        candidates.append({
            'license': lic,
            'user': user,
            'phone': phone,
            'step_key': STEP_EXPIRING,
            'days': days_left,
            'product': getattr(lic.order.product, 'title', None) or getattr(lic.plan, 'name', '') or 'فایلینگ',
        })

    expired = (
        License.objects.filter(
            order__status='paid',
            expires_at__isnull=False,
            expires_at__lte=now,
            expires_at__gte=churn_since - timedelta(days=30),
        )
        .filter(
            # هنوز لایسنس فعال دیگری برای همان کاربر نباشد
        )
        .select_related('order', 'order__user', 'order__product', 'plan')
        .order_by('-expires_at')[:500]
    )
    seen_users: set[int] = set()
    for lic in expired:
        user = lic.order.user
        if user.pk in seen_users:
            continue
        # اگر لایسنس فعال دیگری دارد، skip
        from django.db.models import Q
        has_active = License.objects.filter(
            order__user=user,
            order__status='paid',
            status='active',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        ).exists()
        if has_active:
            continue
        phone = normalize_phone(getattr(user, 'phone', '') or '')
        if not phone or not is_valid_iran_mobile(phone):
            continue
        seen_users.add(user.pk)
        days_expired = max(0, (now - lic.expires_at).days)
        step = STEP_CHURN if days_expired >= churn_grace else STEP_EXPIRING
        candidates.append({
            'license': lic,
            'user': user,
            'phone': phone,
            'step_key': step,
            'days': days_expired,
            'product': getattr(lic.order.product, 'title', None) or getattr(lic.plan, 'name', '') or 'فایلینگ',
        })

    return candidates


def run_license_renewal(
    *,
    dry_run: bool = True,
    limit: int = 100,
    live: bool = False,
) -> dict[str, Any]:
    # Per-action atomics only — outer atomic would poison the loop on UniqueViolation.
    if not renewal_enabled() and live:
        return {'ok': False, 'error': 'LICENSE_RENEWAL_FLOW_ENABLED=False', 'sent': 0}

    now = timezone.now()
    day_bucket = timezone.localtime(now).strftime('%Y%m%d')
    mode = MarketingAutomationRun.Mode.LIVE if live and not dry_run else MarketingAutomationRun.Mode.DRY_RUN
    run = MarketingAutomationRun.objects.create(
        flow_key=FLOW_KEY,
        mode=mode,
        status=MarketingAutomationRun.Status.RUNNING,
        config_snapshot={
            'within_days': expiring_within_days(),
            'churn_after_days': churn_after_days(),
            'dry_run': dry_run,
            'live': live,
        },
    )

    candidates = iter_renewal_candidates(now=now)[: max(1, limit)]
    stats = {
        'run_id': run.pk,
        'examined': 0,
        'eligible': 0,
        'suppressed': 0,
        'would_send': 0,
        'sent': 0,
        'failed': 0,
        'errors': 0,
    }

    for item in candidates:
        stats['examined'] += 1
        lic = item['license']
        user = item['user']
        phone = item['phone']
        step_key = item['step_key']

        # Journey stage (own atomic inside transition)
        try:
            if step_key == STEP_CHURN:
                transition(
                    phone=phone,
                    user=user,
                    event_type='expired_no_renew',
                    stage=GrowthJourney.Stage.CHURN_RISK,
                    allow_regress=True,
                    ref_model='License',
                    ref_id=lic.pk,
                )
            else:
                transition(
                    phone=phone,
                    user=user,
                    event_type='license_expiring',
                    stage=GrowthJourney.Stage.EXPIRING_SOON,
                    allow_regress=True,
                    ref_model='License',
                    ref_id=lic.pk,
                )
        except Exception:
            logger.exception('license renewal journey transition failed lic=%s', lic.pk)

        if not is_send_allowed(phone, purpose=PURPOSE_LICENSE_RENEWAL, user=user):
            stats['suppressed'] += 1
            continue

        send_key = _idempotency_key(license_id=lic.pk, step_key=step_key, day_bucket=day_bucket)
        # Dry keys are run-scoped so re-running dry_run the same day is safe.
        # Live keys stay day-scoped for cross-run send idempotency.
        if dry_run or not live:
            decision_key = f'dry:{run.pk}:{send_key}'
        else:
            decision_key = f'live:{send_key}'
        body = _render_body(
            user=user,
            product_title=item['product'],
            days=item['days'],
            step_key=step_key,
        )

        if dry_run or not live:
            try:
                with transaction.atomic():
                    MarketingAutomationActionLog.objects.create(
                        run=run,
                        flow_key=FLOW_KEY,
                        step_key=step_key,
                        user=user,
                        phone_hash=_phone_hash(phone),
                        masked_phone=_mask_phone(phone),
                        order=lic.order,
                        product=getattr(lic.order, 'product', None),
                        action=MarketingAutomationActionLog.Action.WOULD_SEND,
                        reason='dry_run',
                        metadata={'body_preview': body[:200], 'license_id': lic.pk},
                        decision_key=decision_key,
                        send_idempotency_key=None,
                    )
                stats['would_send'] += 1
                stats['eligible'] += 1
            except IntegrityError:
                stats['suppressed'] += 1
            continue

        # Live send
        try:
            with transaction.atomic():
                log = MarketingAutomationActionLog.objects.create(
                    run=run,
                    flow_key=FLOW_KEY,
                    step_key=step_key,
                    user=user,
                    phone_hash=_phone_hash(phone),
                    masked_phone=_mask_phone(phone),
                    order=lic.order,
                    product=getattr(lic.order, 'product', None),
                    action=MarketingAutomationActionLog.Action.SEND_REQUESTED,
                    reason='',
                    metadata={'license_id': lic.pk},
                    decision_key=decision_key,
                    send_idempotency_key=send_key,
                )
        except IntegrityError:
            stats['suppressed'] += 1
            continue

        ok, sms_log = notify_marketing(phone=phone, text=body)
        log.sms_log = sms_log
        if ok:
            log.action = MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED
            log.provider_message_id = getattr(sms_log, 'provider_message_id', '') or ''
            stats['sent'] += 1
            stats['eligible'] += 1
        else:
            log.action = MarketingAutomationActionLog.Action.FAILED
            log.reason = (getattr(sms_log, 'error_message', '') or 'send_failed')[:200]
            stats['failed'] += 1
        log.save()

    run.examined_count = stats['examined']
    run.eligible_count = stats['eligible']
    run.suppressed_count = stats['suppressed']
    run.would_send_count = stats['would_send']
    run.error_count = stats['failed'] + stats['errors']
    run.status = MarketingAutomationRun.Status.COMPLETED
    run.finished_at = timezone.now()
    run.save()
    stats['ok'] = True
    return stats
