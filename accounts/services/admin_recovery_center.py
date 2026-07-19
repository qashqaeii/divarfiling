"""Recovery Center — Data product for checkout recovery intelligence (Week 1 MVP)."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import jdatetime
from django.conf import settings
from django.db.models import Count, Max, Q
from django.utils import timezone

from accounts.models import MarketingAutomationActionLog, MarketingAutomationRun, RecoveryAttribution
from accounts.services.pending_recovery import (
    FLOW_KEY,
    REAL_DELIVERY_ACTIONS,
    STEP_LABELS_FA,
    get_recovery_config,
    resolve_pending_recovery_audience,
)
from accounts.services.pending_recovery_live import get_daily_sms_guard_status, local_day_bounds
from accounts.services.recovery_attribution import (
    ATTRIBUTION_WINDOW_HOURS,
    backfill_attributions,
    attribution_map_for_logs,
    count_duplicate_strict_attributions,
    executive_attribution_summary,
    is_delivered_recovery_send,
    is_production_recovery_send,
    serialize_attribution_for_explorer,
    strict_matched_qs,
)
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

SCHEMA_VERSION = 'recovery_center_v1.2'
ATTRIBUTION_PHASE = 2
EXPLORER_PAGE_SIZE = 50

JOURNEY_STEP_KEYS = (
    'recovery_step_1',
    'recovery_step_1_late',
    'recovery_step_2',
)

JOURNEY_STEP_LABELS_FA = {
    'recovery_step_1': 'مرحله ۱ (۲–۲۴ ساعت)',
    'recovery_step_1_late': 'مرحله ۱ دیررس (۲۴–۷۲ ساعت)',
    'recovery_step_2': 'مرحله ۲ (پس از مرحله ۱ + ۲۴ ساعت)',
}

RUN_MODE_LABELS_FA = {
    MarketingAutomationRun.Mode.DRY_RUN: 'آزمایشی',
    MarketingAutomationRun.Mode.LIVE: 'واقعی',
}

RUN_STATUS_LABELS_FA = {
    MarketingAutomationRun.Status.RUNNING: 'در حال اجرا',
    MarketingAutomationRun.Status.COMPLETED: 'تکمیل‌شده',
    MarketingAutomationRun.Status.FAILED: 'ناموفق',
}

ACTION_LABELS_FA = {
    MarketingAutomationActionLog.Action.WOULD_SEND: 'ارسال شبیه‌سازی',
    MarketingAutomationActionLog.Action.SEND_REQUESTED: 'درخواست ارسال',
    MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED: 'پیامک پذیرفته',
    MarketingAutomationActionLog.Action.TEST_PROVIDER_ACCEPTED: 'تست — پذیرفته',
    MarketingAutomationActionLog.Action.DELIVERED: 'تحویل‌شده',
    MarketingAutomationActionLog.Action.SENT: 'ارسال‌شده',
    MarketingAutomationActionLog.Action.FAILED: 'ناموفق',
    MarketingAutomationActionLog.Action.SUPPRESSED: 'حذف‌شده',
    MarketingAutomationActionLog.Action.CANCELLED: 'لغوشده',
}


def _format_jalali_datetime(value) -> str:
    if not value:
        return ''
    dt = value
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    jdt = jdatetime.datetime.fromgregorian(datetime=dt)
    return to_persian_digits(jdt.strftime('%Y/%m/%d %H:%M'))


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


def build_recovery_funnel(*, since, now=None, attribution_summary: dict | None = None) -> dict[str, Any]:
    now = now or timezone.now()
    pricing = funnel_events_since(since, 'pricing_view').count()
    checkout = funnel_events_since(since, 'checkout_view').count()
    abandoned = funnel_events_since(since, 'checkout_abandon').count()

    audience = resolve_pending_recovery_audience(simulate_enabled=False, now=now)
    eligible_now = audience['stats']['would_send']

    sends = _production_sends_qs(since=since)
    accepted = len(sends)
    delivered = sum(1 for log in sends if is_delivered_recovery_send(log))

    attribution_summary = attribution_summary or executive_attribution_summary(since=since)
    recovered = attribution_summary['recovered']
    recovery_revenue = attribution_summary['recovery_revenue']
    conversion_rate_val = conversion_rate(recovered, accepted, 1) if accepted else None
    revenue_per_sms = (
        int(recovery_revenue / accepted) if accepted and recovery_revenue else None
    )

    stages = [
        _funnel_stage(
            key='pricing_viewed',
            label='بازدید قیمت',
            count=pricing,
            prev_count=None,
            available=pricing > 0,
            note='' if pricing else 'ردیابی بازدید قیمت‌گذاری',
        ),
        _funnel_stage(
            key='checkout_started',
            label='شروع تسویه',
            count=checkout,
            prev_count=pricing or None,
            available=checkout > 0,
        ),
        _funnel_stage(
            key='checkout_abandoned',
            label='رها کردن تسویه',
            count=abandoned,
            prev_count=checkout or None,
            available=abandoned > 0,
        ),
        _funnel_stage(
            key='recovery_eligible',
            label='واجد بازیابی (الان)',
            count=eligible_now,
            prev_count=abandoned or None,
            available=True,
            note='نمای لحظه‌ای — آماده ارسال',
        ),
        _funnel_stage(
            key='sms_accepted',
            label='پیامک پذیرفته',
            count=accepted,
            prev_count=eligible_now or None,
            available=True,
        ),
        _funnel_stage(
            key='sms_delivered',
            label='پیامک تحویل',
            count=delivered,
            prev_count=accepted or None,
            available=True,
            note='تحویل یا پذیرش + ارسال موفق',
        ),
        _funnel_stage(
            key='recovered_paid',
            label='پرداخت بازیابی',
            count=recovered,
            prev_count=delivered or None,
            available=True,
            note='Strict — rule_version strict_v1',
        ),
    ]

    executive = {
        'abandoned': abandoned,
        'eligible_now': eligible_now,
        'sms_accepted': accepted,
        'sms_delivered': delivered,
        'recovered': recovered,
        'recovery_revenue': recovery_revenue,
        'conversion_rate': conversion_rate_val,
        'revenue_per_sms': revenue_per_sms,
        'attribution_phase': ATTRIBUTION_PHASE,
        'attribution_note': 'KPI اجرایی: Strict matched · Assisted فقط Explorer',
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
        paid = strict_matched_qs(since=since).filter(action_log__step_key=step_key).count()
        conv = conversion_rate(paid, sent, 1) if sent else None
        eligible_key = {
            'recovery_step_1': 'step_1_recipients',
            'recovery_step_1_late': 'step_1_late_recipients',
            'recovery_step_2': 'step_2_recipients',
        }[step_key]
        rows.append({
            'step_key': step_key,
            'label': JOURNEY_STEP_LABELS_FA.get(step_key, STEP_LABELS_FA.get(step_key, step_key)),
            'sent': sent,
            'failed': failed,
            'suppressed': suppressed,
            'eligible_snapshot': stats.get(eligible_key, 0),
            'paid': paid,
            'conversion': conv,
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
            'message': f'{to_persian_digits(str(abandon_no_user_pct))}٪ رویداد رها کردن بدون کاربر',
        })
    if sms_without_order:
        warnings.append({
            'severity': 'warn',
            'message': f'{to_persian_digits(str(sms_without_order))} پیامک بدون سفارش',
        })
    if missing_step:
        warnings.append({
            'severity': 'medium',
            'message': f'{to_persian_digits(str(missing_step))} لاگ بدون مرحله',
        })

    return {
        'checkout_abandon_without_user_pct': abandon_no_user_pct,
        'checkout_abandon_without_user_count': abandon_no_user,
        'checkout_abandon_total': abandon_total,
        'sms_without_order': sms_without_order,
        'action_log_missing_step': missing_step,
        'duplicate_attribution': count_duplicate_strict_attributions(since=since),
        'duplicate_attribution_note': 'تعداد پرداخت‌های Strict تکراری (باید ۰ باشد)',
        'warnings': warnings,
    }


def _health_age_label(ts, *, now) -> str:
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


def _run_health_snapshot(run: MarketingAutomationRun | None, *, now) -> dict[str, Any]:
    if not run:
        return {
            'last_run_at': None,
            'last_run_label': EMPTY_MSG,
            'last_mode': None,
            'last_mode_label': None,
            'last_status': None,
            'last_status_label': None,
            'last_would_send': None,
            'last_examined': None,
        }
    return {
        'last_run_at': run.started_at.isoformat(),
        'last_run_label': _health_age_label(run.started_at, now=now),
        'last_mode': run.mode,
        'last_mode_label': RUN_MODE_LABELS_FA.get(run.mode, run.mode),
        'last_status': run.status,
        'last_status_label': RUN_STATUS_LABELS_FA.get(run.status, run.status),
        'last_would_send': run.would_send_count,
        'last_examined': run.examined_count,
    }


def build_recovery_health(*, now=None) -> dict[str, Any]:
    now = now or timezone.now()
    since_24h = now - timedelta(hours=24)
    since_30d = now - timedelta(days=30)

    last_dry_run = (
        MarketingAutomationRun.objects.filter(
            flow_key=FLOW_KEY,
            mode=MarketingAutomationRun.Mode.DRY_RUN,
        )
        .order_by('-started_at')
        .first()
    )
    last_live_run = (
        MarketingAutomationRun.objects.filter(
            flow_key=FLOW_KEY,
            mode=MarketingAutomationRun.Mode.LIVE,
        )
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
    daily_guard = get_daily_sms_guard_status(now=now)
    _, day_end = local_day_bounds(now=now)
    pending_attributions = RecoveryAttribution.objects.filter(
        status=RecoveryAttribution.Status.PENDING,
        action_log__flow_key=FLOW_KEY,
        action_log__created_at__gte=since_30d,
    ).count()
    strict_matched_30d = strict_matched_qs(since=since_30d).count()
    duplicate_strict = count_duplicate_strict_attributions(since=since_30d)

    max_per_run = int(getattr(settings, 'RECOVERY_LIVE_MAX_SENDS_PER_RUN', 1) or 1)

    return {
        'recovery_engine': {
            'flow_enabled': cfg['flow_enabled'],
            'live_send_enabled': bool(getattr(settings, 'RECOVERY_LIVE_SEND_ENABLED', False)),
            'test_only': bool(getattr(settings, 'RECOVERY_LIVE_TEST_ONLY', True)),
            'max_sends_per_run': max_per_run,
            'status': 'on' if cfg['flow_enabled'] else 'off',
        },
        'record_checkout_abandons': {
            'label': 'ثبت رها کردن checkout',
            'last_signal_at': (
                last_abandon_event.created_at.isoformat() if last_abandon_event else None
            ),
            'last_signal_label': _health_age_label(
                last_abandon_event.created_at if last_abandon_event else None,
                now=now,
            ),
            'note': 'آخرین سیگنال رها کردن — مستقل از cron بازیابی',
        },
        'last_dry_run': _run_health_snapshot(last_dry_run, now=now),
        'last_live_run': _run_health_snapshot(last_live_run, now=now),
        'run_pending_recovery': _run_health_snapshot(
            last_live_run or last_dry_run,
            now=now,
        ),
        'daily_sms_guard': {
            **daily_guard,
            'resets_at_label': _format_jalali_datetime(day_end),
        },
        'attribution_health': {
            'pending_30d': pending_attributions,
            'strict_matched_30d': strict_matched_30d,
            'duplicate_strict_30d': duplicate_strict,
            'window_hours': ATTRIBUTION_WINDOW_HOURS,
            'duplicate_ok': duplicate_strict == 0,
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
    attr_map = attribution_map_for_logs([log.pk for log in logs])

    rows = []
    for log in logs:
        attr = attr_map.get(log.pk)
        attr_payload = serialize_attribution_for_explorer(attr)
        status_label = _explorer_status_label(log, attr)
        rows.append({
            'id': log.pk,
            'user_id': log.user_id,
            'order_id': str(log.order_id) if log.order_id else None,
            'masked_phone': log.masked_phone,
            'step_key': log.step_key,
            'step_label': JOURNEY_STEP_LABELS_FA.get(
                log.step_key,
                STEP_LABELS_FA.get(log.step_key, log.step_key),
            ),
            'action': log.action,
            'action_label': ACTION_LABELS_FA.get(log.action, log.action),
            'reason': log.reason,
            'created_at': log.created_at.isoformat(),
            'created_at_jalali': _format_jalali_datetime(log.created_at),
            'product_title': log.product.title if log.product_id else '',
            'is_production_send': is_production_recovery_send(log),
            'status_label': status_label,
            **attr_payload,
        })

    return {
        'rows': rows,
        'total': total,
        'page': page,
        'page_size': page_size,
        'pages': max(1, (total + page_size - 1) // page_size),
    }


def _explorer_status_label(
    log: MarketingAutomationActionLog,
    attr=None,
) -> str:
    if attr and attr.status == RecoveryAttribution.Status.MATCHED:
        model_label = 'Strict' if attr.attribution_model == RecoveryAttribution.AttributionModel.STRICT else 'Assisted'
        return f'بازیابی {model_label}'
    if attr and attr.status == RecoveryAttribution.Status.NO_MATCH:
        return 'بدون انطباق'
    if log.action == MarketingAutomationActionLog.Action.SUPPRESSED:
        return log.reason or 'حذف‌شده'
    if log.action == MarketingAutomationActionLog.Action.FAILED:
        return 'ناموفق'
    if is_production_recovery_send(log):
        if log.order and log.order.status == 'paid':
            return 'پرداخت شده — نسبت‌دهی در انتظار'
        return 'در انتظار پرداخت'
    if log.action == MarketingAutomationActionLog.Action.WOULD_SEND:
        return 'اجرای آزمایشی'
    return ACTION_LABELS_FA.get(log.action, log.get_action_display())


def get_recovery_center_context(*, days: int = 30, page: int = 1) -> dict[str, Any]:
    bounds = period_bounds(days)
    days = bounds['days']
    since = bounds['since']
    now = bounds['now']

    backfill_attributions(since=since)

    attribution_summary = executive_attribution_summary(since=since)
    funnel = build_recovery_funnel(since=since, now=now, attribution_summary=attribution_summary)
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
            'window_hours': ATTRIBUTION_WINDOW_HOURS,
            'strict_rule_version': 'strict_v1',
            'assisted_rule_version': 'assisted_v1',
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
