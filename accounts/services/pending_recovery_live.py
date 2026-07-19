"""ارسال Live Recovery — رزرو Idempotency قبل از Provider + state machine."""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import MarketingAutomationActionLog, MarketingAutomationRun
from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from accounts.services.notifications import notify_marketing
from accounts.services.pending_recovery import (
    FLOW_KEY,
    RecoveryResolution,
    _order_phone,
    get_recovery_config,
    live_send_idempotency_key,
    resolve_checkout_detection_source,
    resolve_pending_recovery_audience,
)
from accounts.services.sms import SmsError

logger = logging.getLogger(__name__)


def live_decision_key(send_idempotency_key: str) -> str:
    return f'live:decision:{send_idempotency_key}'


def get_live_config(*, test_only: bool | None = None) -> dict[str, Any]:
    cfg = get_recovery_config(simulate_enabled=False)
    test_only_mode = (
        test_only
        if test_only is not None
        else bool(getattr(settings, 'RECOVERY_LIVE_TEST_ONLY', True))
    )
    test_phone = normalize_phone(getattr(settings, 'RECOVERY_LIVE_TEST_PHONE', '') or '')
    cfg.update({
        'live_send_enabled': bool(getattr(settings, 'RECOVERY_LIVE_SEND_ENABLED', False)),
        'test_only': test_only_mode,
        'test_phone': test_phone,
        'max_sends_per_run': int(getattr(settings, 'RECOVERY_LIVE_MAX_SENDS_PER_RUN', 1) or 1),
        'provider_timeout_seconds': int(
            getattr(settings, 'RECOVERY_PROVIDER_TIMEOUT_SECONDS', 15) or 15
        ),
        'resolution_enabled': cfg['flow_enabled'],
    })
    return cfg


def validate_live_send_prerequisites(*, confirm_live: bool, test_only: bool | None = None) -> dict[str, Any]:
    cfg = get_live_config(test_only=test_only)
    if not confirm_live:
        raise ValueError('ارسال Live نیاز به --confirm-live دارد.')
    if not cfg['flow_enabled']:
        raise ValueError(
            'PENDING_RECOVERY_FLOW_ENABLED خاموش است. Kill Switch Live را فقط برای تست دستی فعال کنید.'
        )
    if not cfg['live_send_enabled']:
        raise ValueError('RECOVERY_LIVE_SEND_ENABLED خاموش است.')
    if cfg['test_only']:
        if not cfg['test_phone'] or not is_valid_iran_mobile(cfg['test_phone']):
            raise ValueError('RECOVERY_LIVE_TEST_PHONE معتبر تنظیم نشده است.')
    return cfg


def build_recovery_sms_text(order, *, step_key: str) -> str:
    template = getattr(
        settings,
        'RECOVERY_SMS_TEMPLATE',
        '{name_part}سفارش «{product}» ({amount} ت) منتظر پرداخت است. {link}',
    )
    site = (getattr(settings, 'SITE_URL', '') or 'https://divarfiling.ir').rstrip('/')
    link = f'{site}/payment/checkout/{order.pk}/'
    user = order.user
    name_part = ''
    if getattr(user, 'first_name', None):
        name_part = f'{user.first_name}، '
    product_title = order.product.title if order.product_id else 'محصول'
    plan_name = order.plan.name if order.plan_id else ''
    product_label = f'{product_title} · {plan_name}' if plan_name else product_title
    try:
        amount = f'{int(order.amount or 0):,}'
    except (TypeError, ValueError):
        amount = str(order.amount or '')
    return template.format(
        name_part=name_part,
        product=product_label,
        amount=amount,
        link=link,
        step_key=step_key,
    )


def resolve_send_target_phone(order, *, cfg: dict[str, Any]) -> tuple[str, bool, str]:
    phone_norm, _phash, masked, phone_ok = _order_phone(order)
    if not phone_ok:
        raise ValueError('شماره مخاطب نامعتبر است.')
    if cfg.get('test_only'):
        return cfg['test_phone'], True, masked
    return phone_norm, False, masked


def get_existing_live_send(send_idempotency_key: str) -> MarketingAutomationActionLog | None:
    if not send_idempotency_key:
        return None
    return MarketingAutomationActionLog.objects.filter(
        send_idempotency_key=send_idempotency_key,
    ).first()


def reserve_live_send(
    *,
    run: MarketingAutomationRun,
    res: RecoveryResolution,
    cfg: dict[str, Any],
    allow_retry_failed: bool = False,
) -> tuple[MarketingAutomationActionLog | None, str | None]:
    """
    رزرو send_idempotency_key قبل از فراخوانی Provider.
    اگر رزرو قبلی in-flight یا موفق باشد، ارسال تکراری ممنوع است.
    """
    order = res.order
    send_key = live_send_idempotency_key(
        step_key=res.step_key,
        phone_hash=res.phone_hash,
        product_id=order.product_id,
        order_id=order.pk,
    )
    existing = get_existing_live_send(send_key)
    if existing:
        if existing.action in (
            MarketingAutomationActionLog.Action.SEND_REQUESTED,
            MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED,
            MarketingAutomationActionLog.Action.DELIVERED,
            MarketingAutomationActionLog.Action.SENT,
        ):
            return None, f'in_flight_or_done:{existing.action}'
        if existing.action == MarketingAutomationActionLog.Action.FAILED:
            if not allow_retry_failed:
                return None, 'failed_previous'
        else:
            return None, f'blocked:{existing.action}'

    detection = resolve_checkout_detection_source(order)
    _target_phone, redirected, masked = resolve_send_target_phone(order, cfg=cfg)
    meta = {
        'raw_event_count': res.raw_orders_in_group,
        'suppressed_order_ids': res.suppressed_order_ids,
        'age_hours': res.age_hours,
        'amount': int(order.amount or 0),
        'intended_masked_phone': masked,
        'send_target_redirected': redirected,
        'intended_user_id': order.user_id,
        'step_key': res.step_key,
    }
    if redirected:
        meta['test_phone_masked'] = _mask_for_log(cfg['test_phone'])

    try:
        with transaction.atomic():
            log = MarketingAutomationActionLog.objects.create(
                run=run,
                flow_key=FLOW_KEY,
                step_key=res.step_key,
                user=order.user,
                phone_hash=res.phone_hash,
                masked_phone=masked,
                order=order,
                product=order.product,
                action=MarketingAutomationActionLog.Action.SEND_REQUESTED,
                reason=detection.get('label') or 'order_created_at',
                decision_key=live_decision_key(send_key),
                send_idempotency_key=send_key,
                metadata=meta,
            )
        return log, None
    except IntegrityError:
        return None, 'race_duplicate'


def _mask_for_log(phone: str) -> str:
    raw = (phone or '').strip()
    if len(raw) < 7:
        return '***'
    return f'{raw[:4]}***{raw[-2:]}'


def execute_reserved_send(
    log: MarketingAutomationActionLog,
    *,
    cfg: dict[str, Any],
):
    """
    فراخوانی Provider پس از رزرو.
    send_requested → provider_accepted | failed
    در Timeout مبهم: send_requested باقی می‌ماند (بدون retry خودکار).
    """
    order = log.order
    if order is None:
        log.action = MarketingAutomationActionLog.Action.FAILED
        log.reason = 'missing_order'
        log.save(update_fields=['action', 'reason', 'updated_at'])
        return log.action, None

    target_phone, redirected, _masked = resolve_send_target_phone(order, cfg=cfg)
    text = build_recovery_sms_text(order, step_key=log.step_key)

    try:
        ok, sms_log = notify_marketing(phone=target_phone, text=text)
    except SmsError as exc:
        log.action = MarketingAutomationActionLog.Action.FAILED
        log.reason = (exc.code or 'sms_error')[:200]
        meta = dict(log.metadata or {})
        meta['error'] = str(exc.message or exc)[:500]
        log.metadata = meta
        log.save(update_fields=['action', 'reason', 'metadata', 'updated_at'])
        return log.action, None
    except Exception as exc:  # noqa: BLE001 — مرز Provider
        logger.exception('recovery live send unexpected error log_id=%s', log.pk)
        meta = dict(log.metadata or {})
        meta['ambiguous_error'] = str(exc)[:500]
        log.metadata = meta
        log.reason = 'ambiguous_provider_error'
        log.save(update_fields=['metadata', 'reason', 'updated_at'])
        return log.action, None

    meta = dict(log.metadata or {})
    meta['sms_log_id'] = sms_log.pk
    meta['send_target_redirected'] = redirected

    if ok:
        log.action = MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED
        log.sms_log = sms_log
        log.provider_message_id = sms_log.provider_message_id or ''
        log.reason = 'provider_accepted'
        meta['provider'] = sms_log.provider
    else:
        log.action = MarketingAutomationActionLog.Action.FAILED
        log.sms_log = sms_log
        log.reason = (sms_log.error_message or 'provider_rejected')[:200]
        meta['provider_error'] = log.reason

    log.metadata = meta
    log.save(update_fields=[
        'action', 'sms_log', 'provider_message_id', 'reason', 'metadata', 'updated_at',
    ])
    return log.action, sms_log


def run_pending_recovery_live(
    *,
    confirm_live: bool = True,
    test_only: bool | None = None,
    batch_limit: int | None = None,
    lookback_days: int | None = None,
    allow_retry_failed: bool = False,
    max_sends_per_run: int | None = None,
) -> dict[str, Any]:
    cfg = validate_live_send_prerequisites(confirm_live=confirm_live, test_only=test_only)
    if max_sends_per_run is not None:
        cfg['max_sends_per_run'] = max(1, int(max_sends_per_run))
    now = timezone.now()

    run = MarketingAutomationRun.objects.create(
        flow_key=FLOW_KEY,
        mode=MarketingAutomationRun.Mode.LIVE,
        status=MarketingAutomationRun.Status.RUNNING,
        config_snapshot=cfg,
    )

    banner = 'LIVE SEND — TEST MODE (redirected phone)' if cfg['test_only'] else 'LIVE SEND'
    result_stats: dict[str, Any] = {
        'dry_run': False,
        'live': True,
        'test_only': cfg['test_only'],
        'flow_live_enabled': cfg['flow_enabled'],
        'live_send_enabled': cfg['live_send_enabled'],
        'simulation_banner': banner,
        'flow_key': FLOW_KEY,
        'run_id': run.pk,
        'examined': 0,
        'eligible': 0,
        'suppressed': 0,
        'would_send': 0,
        'send_requested': 0,
        'provider_accepted': 0,
        'failed': 0,
        'skipped': 0,
        'errors': 0,
        'config': cfg,
    }

    try:
        data = resolve_pending_recovery_audience(
            batch_limit=batch_limit,
            lookback_days=lookback_days,
            now=now,
            simulate_enabled=False,
        )
        stats = data['stats']
        result_stats.update({
            'examined': stats['examined'],
            'eligible': stats['unique_recipients'],
            'suppressed': stats['suppressed'],
            'would_send': stats['would_send'],
            'recovery_stats': stats,
        })

        max_sends = max(1, int(max_sends_per_run if max_sends_per_run is not None else cfg.get('max_sends_per_run') or 1))
        sent_count = 0

        for res in data['resolutions']:
            if not res.would_send:
                continue
            if sent_count >= max_sends:
                result_stats['skipped'] += 1
                continue

            log, skip_reason = reserve_live_send(
                run=run,
                res=res,
                cfg=cfg,
                allow_retry_failed=allow_retry_failed,
            )
            if log is None:
                result_stats['skipped'] += 1
                result_stats.setdefault('skip_breakdown', {})
                key = skip_reason or 'unknown'
                result_stats['skip_breakdown'][key] = (
                    result_stats['skip_breakdown'].get(key, 0) + 1
                )
                continue

            result_stats['send_requested'] += 1
            final_action, _sms_log = execute_reserved_send(log, cfg=cfg)

            if final_action == MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED:
                result_stats['provider_accepted'] += 1
                sent_count += 1
            elif final_action == MarketingAutomationActionLog.Action.FAILED:
                result_stats['failed'] += 1
            elif final_action == MarketingAutomationActionLog.Action.SEND_REQUESTED:
                result_stats.setdefault('ambiguous_in_flight', 0)
                result_stats['ambiguous_in_flight'] += 1
            else:
                result_stats['errors'] += 1

        run.examined_count = stats['examined']
        run.eligible_count = stats['unique_recipients']
        run.suppressed_count = stats['suppressed']
        run.would_send_count = stats['would_send']
        run.error_count = result_stats['errors']
        run.status = (
            MarketingAutomationRun.Status.FAILED
            if result_stats['errors']
            else MarketingAutomationRun.Status.COMPLETED
        )
        run.finished_at = timezone.now()
        run.save()
    except Exception:
        run.status = MarketingAutomationRun.Status.FAILED
        run.finished_at = timezone.now()
        run.error_count = 1
        run.save(update_fields=['status', 'finished_at', 'error_count'])
        raise

    return result_stats
