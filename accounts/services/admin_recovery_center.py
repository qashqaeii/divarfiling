"""Recovery Center — Data product for checkout recovery intelligence (Week 1 MVP)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import jdatetime
from django.conf import settings
from django.db.models import Count, Max, Q
from django.utils import timezone

from accounts.models import MarketingAutomationActionLog, MarketingAutomationRun
from accounts.services.pending_recovery import (
    FLOW_KEY,
    REAL_DELIVERY_ACTIONS,
    STEP_LABELS_FA,
    get_recovery_config,
    resolve_pending_recovery_audience,
)
from accounts.services.pending_recovery_live import TEST_SEND_KEY_PREFIX
from accounts.services.plan_bi import (
    EMPTY_MSG,
    conversion_rate,
    funnel_events_since,
    jalali_iso,
    period_bounds,
)
from accounts.services.sms import get_sms_balance_snapshot
from shop.models import PlanFunnelEvent
from workspace.services.jalali_input import to_persian_digits

SCHEMA_VERSION = 'recovery_center_v1'
ATTRIBUTION_PHASE = 2
EXPLORER_PAGE_SIZE = 50

JOURNEY_STEP_KEYS = (
    'recovery_step_1',
    'recovery_step_1_late',
    'recovery_step_2',
)

ACTION_LABELS_FA = {
    MarketingAutomationActionLog.Action.WOULD_SEND: 'Would Send',
    MarketingAutomationActionLog.Action.SEND_REQUESTED: 'Send Requested',
    MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED: 'SMS Accepted',
    MarketingAutomationActionLog.Action.TEST_PROVIDER_ACCEPTED: 'Test Accepted',
    MarketingAutomationActionLog.Action.DELIVERED: 'Delivered',
    MarketingAutomationActionLog.Action.SENT: 'Sent',
    MarketingAutomationActionLog.Action.FAILED: 'Failed',
    MarketingAutomationActionLog.Action.SUPPRESSED: 'Suppressed',
    MarketingAutomationActionLog.Action.CANCELLED: 'Cancelled',
}


def is_production_recovery_send(log: MarketingAutomationActionLog) -> bool:
    if log.action not in REAL_DELIVERY_ACTIONS:
        return False
    if log.action == MarketingAutomationActionLog.Action.TEST_PROVIDER_ACCEPTED:
        return False
    send_key = log.send_idempotency_key or ''
    if send_key.startswith(TEST_SEND_KEY_PREFIX):
        return False
    if (log.metadata or {}).get('send_target_redirected'):
        return False
    return True


def is_delivered_recovery_send(log: MarketingAutomationActionLog) -> bool:
    if not is_production_recovery_send(log):
        return False
    if log.action == MarketingAutomationActionLog.Action.DELIVERED:
        return True
    if log.sms_log_id and log.sms_log.status == log.sms_log.Status.SENT:
        return True
    return log.action in (
        MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED,
        MarketingAutomationActionLog.Action.SENT,
    )


def _production_sends_qs(*, since=None, until=None):
    qs = MarketingAutomationActionLog.objects.filter(flow_key=FLOW_KEY).select_related(
        'sms_log', 'order', 'user', 'product', 'run',
    )
    if since:
        qs = qs.filter(created_at__gte=since)
    if until:
        qs = qs.filter(created_at__lt=until)
    return [log for log in qs if is_production_recovery_send(log)]


def _funnel_stage(
    *,
    key: str,
    label: str,
    count: int | None,
    prev_count: int | None,
    available: bool = True,
    note: str = '',
) -> dict[str, Any]:
    conv = conversion_rate(count or 0, prev_count, 1) if prev_count else None
    drop = round(100.0 - conv, 1) if conv is not None else None
    return {
        'key': key,
        'label': label,
        'count': count,
        'available': available,
        'conversion_from_prev': conv,
        'dropoff_from_prev': drop,
        'display': count if available else EMPTY_MSG,
        'note': note,
    }


def build_data_freshness(*, now=None) -> dict[str, Any]:
    now = now or timezone.now()
    last_event = (
        PlanFunnelEvent.objects.filter(event_type='checkout_abandon')
        .aggregate(ts=Max('created_at'))
        .get('ts')
    )
    last_run = (
        MarketingAutomationRun.objects.filter(flow_key=FLOW_KEY)
        .aggregate(ts=Max('started_at'))
        .get('ts')
    )
    return {
        'generated_at': now.isoformat(),
        'last_event_at': last_event.isoformat() if last_event else None,
        'last_recovery_run_at': last_run.isoformat() if last_run else None,
    }


def build_recovery_funnel(*, since, now=None) -> dict[str, Any]:
    now = now or timezone.now()
    pricing = funnel_events_since(since, 'pricing_view').count()
    checkout = funnel_events_since(since, 'checkout_view').count()
    abandoned = funnel_events_since(since, 'checkout_abandon').count()

    audience = resolve_pending_recovery_audience(simulate_enabled=False, now=now)
    eligible_now = audience['stats']['would_send']

    sends = _production_sends_qs(since=since)
    accepted = len(sends)
    delivered = sum(1 for log in sends if is_delivered_recovery_send(log))

    stages = [
        _funnel_stage(
            key='pricing_viewed',
            label='بازدید قیمت',
            count=pricing,
            prev_count=None,
            available=pricing > 0,
            note='' if pricing else 'ردیابی pricing_view',
        ),
        _funnel_stage(
            key='checkout_started',
            label='شروع Checkout',
            count=checkout,
            prev_count=pricing or None,
            available=checkout > 0,
        ),
        _funnel_stage(
            key='checkout_abandoned',
            label='رها کردن Checkout',
            count=abandoned,
            prev_count=checkout or None,
            available=abandoned > 0,
        ),
        _funnel_stage(
            key='recovery_eligible',
            label='واجد Recovery (الان)',
            count=eligible_now,
            prev_count=abandoned or None,
            available=True,
            note='Snapshot لحظه‌ای — would_send',
        ),
        _funnel_stage(
            key='sms_accepted',
            label='SMS پذیرفته',
            count=accepted,
            prev_count=eligible_now or None,
            available=True,
        ),
        _funnel_stage(
            key='sms_delivered',
            label='SMS تحویل',
            count=delivered,
            prev_count=accepted or None,
            available=True,
            note='delivered یا accepted + sms_log.sent',
        ),
        _funnel_stage(
            key='recovered_paid',
            label='پرداخت بازیابی',
            count=None,
            prev_count=None,
            available=False,
            note='فاز ۲ — Strict Attribution',
        ),
    ]

    executive = {
        'abandoned': abandoned,
        'eligible_now': eligible_now,
        'sms_accepted': accepted,
        'sms_delivered': delivered,
        'recovered': None,
        'recovery_revenue': None,
        'conversion_rate': None,
        'revenue_per_sms': None,
        'attribution_phase': ATTRIBUTION_PHASE,
        'attribution_note': 'Recovered Revenue پس از فاز Attribution (Strict + Assisted)',
    }

    return {'stages': stages, 'executive': executive}


def build_journey_performance(*, since, now=None) -> list[dict[str, Any]]:
    now = now or timezone.now()
    audience = resolve_pending_recovery_audience(simulate_enabled=False, now=now)
    stats = audience['stats']

    logs_qs = MarketingAutomationActionLog.objects.filter(
        flow_key=FLOW_KEY,
        created_at__gte=since,
    )
    rows = []
    for step_key in JOURNEY_STEP_KEYS:
        step_logs = logs_qs.filter(step_key=step_key)
        sent = sum(1 for log in step_logs if is_production_recovery_send(log))
        failed = step_logs.filter(action=MarketingAutomationActionLog.Action.FAILED).count()
        suppressed = step_logs.filter(action=MarketingAutomationActionLog.Action.SUPPRESSED).count()
        eligible_key = {
            'recovery_step_1': 'step_1_recipients',
            'recovery_step_1_late': 'step_1_late_recipients',
            'recovery_step_2': 'step_2_recipients',
        }[step_key]
        rows.append({
            'step_key': step_key,
            'label': STEP_LABELS_FA.get(step_key, step_key),
            'sent': sent,
            'failed': failed,
            'suppressed': suppressed,
            'eligible_snapshot': stats.get(eligible_key, 0),
            'paid': None,
            'conversion': None,
            'attribution_phase': ATTRIBUTION_PHASE,
        })
    return rows


def build_recovery_data_quality(*, since) -> dict[str, Any]:
    abandon_qs = funnel_events_since(since, 'checkout_abandon')
    abandon_total = abandon_qs.count()
    abandon_no_user = abandon_qs.filter(user__isnull=True).count()
    abandon_no_user_pct = (
        round(100.0 * abandon_no_user / abandon_total, 1) if abandon_total else 0.0
    )

    send_logs = MarketingAutomationActionLog.objects.filter(
        flow_key=FLOW_KEY,
        created_at__gte=since,
        action__in=REAL_DELIVERY_ACTIONS,
    )
    sms_without_order = send_logs.filter(order__isnull=True).count()
    missing_step = (
        MarketingAutomationActionLog.objects.filter(flow_key=FLOW_KEY, created_at__gte=since)
        .filter(Q(step_key='') | Q(step_key__isnull=True))
        .count()
    )

    warnings: list[dict[str, str]] = []
    if abandon_total and abandon_no_user_pct >= 10:
        warnings.append({
            'severity': 'warn',
            'message': f'{abandon_no_user_pct}٪ checkout_abandon بدون user',
        })
    if sms_without_order:
        warnings.append({
            'severity': 'warn',
            'message': f'{sms_without_order} SMS بدون order',
        })
    if missing_step:
        warnings.append({
            'severity': 'medium',
            'message': f'{missing_step} ActionLog بدون step_key',
        })

    return {
        'checkout_abandon_without_user_pct': abandon_no_user_pct,
        'checkout_abandon_without_user_count': abandon_no_user,
        'checkout_abandon_total': abandon_total,
        'sms_without_order': sms_without_order,
        'action_log_missing_step': missing_step,
        'duplicate_attribution': 0,
        'duplicate_attribution_note': 'فاز ۲ — پس از Attribution Engine',
        'warnings': warnings,
    }


def build_recovery_health(*, now=None) -> dict[str, Any]:
    now = now or timezone.now()
    since_24h = now - timedelta(hours=24)

    last_run = (
        MarketingAutomationRun.objects.filter(flow_key=FLOW_KEY)
        .order_by('-started_at')
        .first()
    )
    last_abandon_event = (
        PlanFunnelEvent.objects.filter(event_type='checkout_abandon')
        .order_by('-created_at')
        .first()
    )

    audience = resolve_pending_recovery_audience(simulate_enabled=False, now=now)
    queue = audience['stats']['would_send']

    errors_24h = MarketingAutomationActionLog.objects.filter(
        flow_key=FLOW_KEY,
        created_at__gte=since_24h,
        action=MarketingAutomationActionLog.Action.FAILED,
    ).count()

    cfg = get_recovery_config()
    sms_balance = get_sms_balance_snapshot()

    def _age_label(ts):
        if not ts:
            return EMPTY_MSG
        delta = now - ts
        minutes = int(delta.total_seconds() // 60)
        if minutes < 60:
            return f'{minutes} دقیقه پیش'
        hours = minutes // 60
        if hours < 48:
            return f'{hours} ساعت پیش'
        return f'{hours // 24} روز پیش'

    return {
        'recovery_engine': {
            'flow_enabled': cfg['flow_enabled'],
            'live_send_enabled': bool(getattr(settings, 'RECOVERY_LIVE_SEND_ENABLED', False)),
            'test_only': bool(getattr(settings, 'RECOVERY_LIVE_TEST_ONLY', True)),
            'status': 'on' if cfg['flow_enabled'] else 'off',
        },
        'record_checkout_abandons': {
            'label': 'record_checkout_abandons',
            'last_signal_at': (
                last_abandon_event.created_at.isoformat() if last_abandon_event else None
            ),
            'last_signal_label': _age_label(
                last_abandon_event.created_at if last_abandon_event else None,
            ),
            'note': 'آخرین checkout_abandon event — cron جداگانه در Run ثبت نمی‌شود',
        },
        'run_pending_recovery': {
            'label': 'run_pending_recovery',
            'last_run_at': last_run.started_at.isoformat() if last_run else None,
            'last_run_label': _age_label(last_run.started_at if last_run else None),
            'last_mode': last_run.mode if last_run else None,
            'last_status': last_run.status if last_run else None,
            'last_would_send': last_run.would_send_count if last_run else None,
            'last_examined': last_run.examined_count if last_run else None,
        },
        'sms_provider': sms_balance,
        'queue': queue,
        'errors_24h': errors_24h,
    }


def build_explorer_rows(
    *,
    since,
    page: int = 1,
    page_size: int = EXPLORER_PAGE_SIZE,
) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or EXPLORER_PAGE_SIZE), 100))

    qs = (
        MarketingAutomationActionLog.objects.filter(
            flow_key=FLOW_KEY,
            created_at__gte=since,
        )
        .select_related('user', 'order', 'product', 'run')
        .order_by('-created_at')
    )
    total = qs.count()
    offset = (page - 1) * page_size
    logs = list(qs[offset : offset + page_size])

    rows = []
    for log in logs:
        rows.append({
            'id': log.pk,
            'user_id': log.user_id,
            'order_id': str(log.order_id) if log.order_id else None,
            'masked_phone': log.masked_phone,
            'step_key': log.step_key,
            'step_label': STEP_LABELS_FA.get(log.step_key, log.step_key),
            'action': log.action,
            'action_label': ACTION_LABELS_FA.get(log.action, log.action),
            'reason': log.reason,
            'created_at': log.created_at.isoformat(),
            'product_title': log.product.title if log.product_id else '',
            'is_production_send': is_production_recovery_send(log),
            'attribution_status': 'pending',
            'status_label': _explorer_status_label(log),
        })

    return {
        'rows': rows,
        'total': total,
        'page': page,
        'page_size': page_size,
        'pages': max(1, (total + page_size - 1) // page_size),
    }


def _explorer_status_label(log: MarketingAutomationActionLog) -> str:
    if log.action == MarketingAutomationActionLog.Action.SUPPRESSED:
        return log.reason or 'Suppressed'
    if log.action == MarketingAutomationActionLog.Action.FAILED:
        return 'Failed'
    if is_production_recovery_send(log):
        if log.order and log.order.status == 'paid':
            return 'Paid (attribution pending)'
        return 'Waiting payment'
    if log.action == MarketingAutomationActionLog.Action.WOULD_SEND:
        return 'Dry run'
    return log.get_action_display()


def get_recovery_center_context(*, days: int = 30, page: int = 1) -> dict[str, Any]:
    bounds = period_bounds(days)
    days = bounds['days']
    since = bounds['since']
    now = bounds['now']

    funnel = build_recovery_funnel(since=since, now=now)
    journey = build_journey_performance(since=since, now=now)
    health = build_recovery_health(now=now)
    data_quality = build_recovery_data_quality(since=since)
    explorer = build_explorer_rows(since=since, page=page)
    freshness = build_data_freshness(now=now)

    summary = {
        'period_start': bounds['period_start'].isoformat(),
        'period_end': bounds['period_end'].isoformat(),
        'period_start_jalali': jalali_iso(bounds['period_start']),
        'period_end_jalali': jalali_iso(bounds['period_end']),
        'generated_at': now.isoformat(),
        'generated_at_jalali': to_persian_digits(
            jdatetime.datetime.fromgregorian(
                datetime=timezone.localtime(now),
            ).strftime('%Y/%m/%d %H:%M'),
        ),
        **funnel['executive'],
    }

    return {
        'schema_version': SCHEMA_VERSION,
        'days': days,
        'summary': summary,
        'funnel': funnel,
        'journey': journey,
        'health': health,
        'data_quality': data_quality,
        'explorer': explorer,
        'data_freshness': freshness,
        'attribution_rules': {
            'strict_primary': 'paid_order_id == ActionLog.order_id',
            'assisted_fallback': 'same user + product + 72h + linked checkout journey',
            'executive_kpi': 'strict_only',
            'phase': ATTRIBUTION_PHASE,
        },
    }


def build_recovery_center_json(*, days: int = 30, page: int = 1) -> dict[str, Any]:
    ctx = get_recovery_center_context(days=days, page=page)
    bounds = period_bounds(days)
    return {
        'schema_version': ctx['schema_version'],
        'generated_at': ctx['data_freshness']['generated_at'],
        'data_freshness': ctx['data_freshness'],
        'period': {
            'days': ctx['days'],
            'since': bounds['since'].isoformat(),
            'until': bounds['now'].isoformat(),
            'start': ctx['summary']['period_start'],
            'end': ctx['summary']['period_end'],
        },
        'funnel': ctx['funnel'],
        'journey': ctx['journey'],
        'health': ctx['health'],
        'data_quality': ctx['data_quality'],
        'explorer': ctx['explorer'],
        'attribution_rules': ctx['attribution_rules'],
    }
