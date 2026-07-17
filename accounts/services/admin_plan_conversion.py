"""آنالیز نرخ تبدیل پلن‌ها — Orchestrator BI داشبورد."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import jdatetime
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from accounts.services.admin_dashboard import (
    PLAN_CHART_COLORS,
    PLAN_TYPE_SHORT_LABELS,
    get_plan_sales_breakdown,
)
from accounts.services.plan_bi import (
    clamp_days,
    count_daily_to_monthly_upgrades,
    funnel_events_since,
    jalali_day_label,
    jalali_iso,
    load_period_buyers,
    paid_orders_qs,
    pct,
    period_bounds,
)
from accounts.services.plan_bi.activation_funnel import build_activation_funnel
from accounts.services.plan_bi.behavior import build_behavior_analytics
from accounts.services.plan_bi.cohorts import build_rich_cohorts
from accounts.services.plan_bi.insights import (
    build_decision_cards,
    build_executive_insights,
    build_predictive_scores,
    build_recommendations,
)
from accounts.services.plan_bi.plan_matrix import build_plan_matrix
from accounts.services.plan_bi.time_series import build_time_intelligence
from shop.models import Order
from workspace.services.jalali_input import to_persian_digits

# Re-export for tests
UPGRADE_WINDOW_DAYS = 7


def _funnel_daily_series(*, since, days: int) -> dict[str, list]:
    end = timezone.localdate()
    start = end - timedelta(days=days - 1)

    def lookup(qs, field: str) -> dict:
        rows = (
            qs.annotate(day=TruncDate(field))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        return {r['day']: int(r['count'] or 0) for r in rows if r['day']}

    pricing_map = lookup(funnel_events_since(since, 'pricing_view'), 'created_at')
    checkout_map = lookup(funnel_events_since(since, 'checkout_view'), 'created_at')
    purchase_map = lookup(paid_orders_qs(since=since), 'effective_paid')
    failed_map = lookup(
        Order.objects.filter(status='failed', created_at__gte=since),
        'created_at',
    )

    labels, labels_full, iso_days = [], [], []
    pricing_counts, checkout_counts, purchase_counts, failed_counts = [], [], [], []
    current = start
    while current <= end:
        labels.append(jalali_day_label(current, compact=True))
        labels_full.append(jalali_iso(current))
        iso_days.append(current.isoformat())
        pricing_counts.append(pricing_map.get(current, 0))
        checkout_counts.append(checkout_map.get(current, 0))
        purchase_counts.append(purchase_map.get(current, 0))
        failed_counts.append(failed_map.get(current, 0))
        current += timedelta(days=1)

    return {
        'labels': labels,
        'labels_full': labels_full,
        'iso_days': iso_days,
        'pricing_counts': pricing_counts,
        'checkout_counts': checkout_counts,
        'purchase_counts': purchase_counts,
        'failed_counts': failed_counts,
        'pricing_labels': labels,
        'checkout_labels': labels,
        'purchase_labels': labels,
    }


def _period_summary(*, since, until=None, days: int) -> dict[str, Any]:
    buyers = load_period_buyers(since=since, until=until)
    pricing_views = funnel_events_since(since, 'pricing_view')
    if until:
        pricing_views = pricing_views.filter(created_at__lt=until)
    pricing_count = pricing_views.count()
    pricing_unique = (
        pricing_views.exclude(session_key='')
        .values('session_key')
        .distinct()
        .count()
    )
    checkout_qs = funnel_events_since(since, 'checkout_view')
    if until:
        checkout_qs = checkout_qs.filter(created_at__lt=until)
    checkout_views = checkout_qs.count()

    failed_qs = Order.objects.filter(status='failed', created_at__gte=since)
    pending_qs = Order.objects.filter(
        status__in=('pending', 'pending_verification'),
        created_at__gte=since,
    )
    if until:
        failed_qs = failed_qs.filter(created_at__lt=until)
        pending_qs = pending_qs.filter(created_at__lt=until)

    failed_payments = failed_qs.count()
    pending_orders = pending_qs.count()
    discount_orders = sum(1 for o in buyers['orders'] if o.discount_code_id)

    paid_count = buyers['paid_count']
    paid_revenue = buyers['paid_revenue']
    daily_purchases = sum(1 for o in buyers['orders'] if o.plan and o.plan.plan_type == 'daily')
    monthly_purchases = sum(1 for o in buyers['orders'] if o.plan and o.plan.plan_type == 'monthly')
    quarterly_purchases = sum(1 for o in buyers['orders'] if o.plan and o.plan.plan_type == 'quarterly')
    yearly_purchases = sum(1 for o in buyers['orders'] if o.plan and o.plan.plan_type == 'yearly')

    upgrade_stats = count_daily_to_monthly_upgrades(since=since)

    return {
        'buyers': buyers,
        'pricing_views': pricing_count,
        'pricing_unique': pricing_unique,
        'checkout_views': checkout_views,
        'failed_payments': failed_payments,
        'pending_orders': pending_orders,
        'discount_orders': discount_orders,
        'discount_rate': pct(discount_orders, paid_count, 1) if paid_count else 0.0,
        'paid_count': paid_count,
        'paid_revenue': paid_revenue,
        'daily_purchases': daily_purchases,
        'monthly_purchases': monthly_purchases,
        'quarterly_purchases': quarterly_purchases,
        'yearly_purchases': yearly_purchases,
        'unique_buyers': buyers['unique_buyers'],
        'aov': int(round(paid_revenue / paid_count)) if paid_count else 0,
        'overall_conversion': pct(paid_count, pricing_count, 2) if pricing_count else 0.0,
        'unique_conversion': pct(paid_count, pricing_unique, 2) if pricing_unique else 0.0,
        'checkout_conversion': pct(paid_count, checkout_views, 2) if checkout_views else 0.0,
        'upgrade_count': upgrade_stats['upgrade_count'],
        'upgrade_rate': upgrade_stats['upgrade_rate'],
        'daily_buyers_for_upgrade': upgrade_stats['daily_buyers'],
        'upgrade_window_days': upgrade_stats['window_days'],
        'upgrade_stats': upgrade_stats,
        'funnel_stages': {
            'pricing_to_checkout': pct(checkout_views, pricing_count, 1) if pricing_count else 0.0,
            'checkout_to_paid': pct(paid_count, checkout_views, 1) if checkout_views else 0.0,
            'pricing_to_paid': pct(paid_count, pricing_count, 2) if pricing_count else 0.0,
        },
        'dropoffs': {
            'pricing_to_checkout': pct(max(pricing_count - checkout_views, 0), pricing_count, 1) if pricing_count else 0.0,
            'checkout_to_paid': pct(max(checkout_views - paid_count, 0), checkout_views, 1) if checkout_views else 0.0,
        },
        'data_quality': {
            'pricing_tracking': pricing_count > 0,
            'has_paid_orders': paid_count > 0,
            'renewal_reliable': False,
            'market_analysis_events': False,
            'user_sms_campaign_events': False,
        },
    }


def build_plan_conversion_chart_payload(
    *,
    plan_rows: list[dict[str, Any]],
    weekly_series: list[dict[str, Any]],
    funnel_series: dict[str, list],
    cohorts: list[dict[str, Any]],
    time_intel: dict[str, Any],
) -> dict[str, Any]:
    colors = [PLAN_CHART_COLORS[i % len(PLAN_CHART_COLORS)] for i in range(len(plan_rows))]
    return {
        'funnel_daily': funnel_series,
        'plan_share': {
            'labels': [row['short_label'] for row in plan_rows],
            'full_labels': [row.get('full_label') or row['label'] for row in plan_rows],
            'values': [row['revenue_share'] for row in plan_rows],
            'order_share': [row['order_share'] for row in plan_rows],
            'revenue': [row['revenue'] for row in plan_rows],
            'purchases': [row['purchases'] for row in plan_rows],
            'aov': [row.get('aov', 0) for row in plan_rows],
            'colors': colors,
        },
        'plan_conversion': {
            'labels': [row['short_label'] for row in plan_rows],
            'funnel_rates': [row.get('funnel_conversion') or 0 for row in plan_rows],
            'checkout_rates': [row.get('checkout_conversion') or 0 for row in plan_rows],
            'purchases': [row['purchases'] for row in plan_rows],
            'accents': [row['accent'] for row in plan_rows],
            'colors': colors,
        },
        'weekly_purchases': {
            'labels': [row['week_label'] for row in weekly_series],
            'labels_short': [row['week_jalali'] for row in weekly_series],
            'iso_weeks': [row['week'] for row in weekly_series],
            'total': [row['total'] for row in weekly_series],
            'daily': [row['daily'] for row in weekly_series],
            'monthly': [row['monthly'] for row in weekly_series],
            'quarterly': [row.get('quarterly', 0) for row in weekly_series],
            'yearly': [row.get('yearly', 0) for row in weekly_series],
            'revenue': [row['revenue'] for row in weekly_series],
            'moving_avg_orders': time_intel.get('moving_avg_orders') or [],
            'moving_avg_revenue': time_intel.get('moving_avg_revenue') or [],
        },
        'cohort': {
            'labels': [c['week_label'] for c in cohorts],
            'labels_jalali': [c['week_jalali'] for c in cohorts],
            'users': [c['users'] for c in cohorts],
            'repeat_7d_rate': [c['repeat_7d_rate'] for c in cohorts],
            'repeat_30d_rate': [c['repeat_30d_rate'] for c in cohorts],
            'upgrade_rate': [c['upgrade_rate'] for c in cohorts],
            'avg_ltv': [c['avg_ltv'] for c in cohorts],
            'active_7d_rate': [c.get('active_7d_rate', 0) for c in cohorts],
            'active_30d_rate': [c.get('active_30d_rate', 0) for c in cohorts],
            'crm_7d_rate': [c.get('crm_7d_rate', 0) for c in cohorts],
            'dataset_7d_rate': [c.get('dataset_7d_rate', 0) for c in cohorts],
        },
    }


def get_plan_conversion_context(*, days: int = 30) -> dict[str, Any]:
    bounds = period_bounds(days)
    days = bounds['days']
    since = bounds['since']
    now = bounds['now']

    current = _period_summary(since=since, days=days)
    previous = _period_summary(since=bounds['prev_since'], until=bounds['prev_until'], days=days)

    buyers = current['buyers']
    upgrade_stats = current['upgrade_stats']

    plan_rows = build_plan_matrix(
        since=since,
        pricing_views=current['pricing_views'],
        checkout_views=current['checkout_views'],
        upgrade_stats=upgrade_stats,
    )
    time_intel = build_time_intelligence(since=since)
    weekly_series = time_intel.get('series') or []
    cohorts = build_rich_cohorts(limit=12)
    funnel_series = _funnel_daily_series(since=since, days=days)

    activation_funnel = build_activation_funnel(
        buyers=buyers,
        pricing_views=current['pricing_views'],
        checkout_views=current['checkout_views'],
        failed_payments=current['failed_payments'],
        pending_orders=current['pending_orders'],
    )
    behavior = build_behavior_analytics(buyers=buyers)

    summary = {
        **{k: v for k, v in current.items() if k not in ('buyers', 'upgrade_stats')},
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
    }

    prev_summary = {
        k: v for k, v in previous.items() if k not in ('buyers', 'upgrade_stats')
    }

    insights = build_executive_insights(
        summary=summary,
        prev_summary=prev_summary,
        plan_rows=plan_rows,
        activation_funnel=activation_funnel,
        upgrade_stats=upgrade_stats,
    )
    decision_cards = build_decision_cards(
        summary=summary,
        prev_summary=prev_summary,
        plan_rows=plan_rows,
        activation_funnel=activation_funnel,
        upgrade_stats=upgrade_stats,
        buyers=buyers,
    )
    recommendations = build_recommendations(
        summary=summary,
        plan_rows=plan_rows,
        activation_funnel=activation_funnel,
        upgrade_stats=upgrade_stats,
        behavior=behavior,
        decision_cards=decision_cards,
    )
    predictive = build_predictive_scores(
        summary=summary,
        buyers=buyers,
        behavior=behavior,
        upgrade_stats=upgrade_stats,
    )

    charts = build_plan_conversion_chart_payload(
        plan_rows=plan_rows,
        weekly_series=weekly_series,
        funnel_series=funnel_series,
        cohorts=cohorts,
        time_intel=time_intel,
    )

    return {
        'days': days,
        'summary': summary,
        'prev_summary': prev_summary,
        'plan_rows': plan_rows,
        'weekly_series': weekly_series,
        'cohorts': cohorts,
        'plan_sales_all_time': get_plan_sales_breakdown(),
        'plan_type_labels': PLAN_TYPE_SHORT_LABELS,
        'charts': charts,
        'insights': insights,
        'decision_cards': decision_cards,
        'activation_funnel': activation_funnel,
        'time_intelligence': time_intel,
        'behavior': behavior,
        'recommendations': recommendations,
        'predictive': predictive,
        'upgrade_stats': upgrade_stats,
    }


def build_plan_conversion_json(*, days: int = 30) -> dict[str, Any]:
    ctx = get_plan_conversion_context(days=days)
    return {
        'ok': True,
        'meta': {
            'days': ctx['days'],
            'period_start': ctx['summary']['period_start'],
            'period_end': ctx['summary']['period_end'],
            'period_start_jalali': ctx['summary']['period_start_jalali'],
            'period_end_jalali': ctx['summary']['period_end_jalali'],
            'generated_at': ctx['summary']['generated_at'],
            'generated_at_jalali': ctx['summary']['generated_at_jalali'],
            'source': 'admin_panel_plan_conversion',
            'version': '2.0-bi',
        },
        'summary': ctx['summary'],
        'prev_summary': ctx['prev_summary'],
        'insights': ctx['insights'],
        'decision_cards': ctx['decision_cards'],
        'activation_funnel': ctx['activation_funnel'],
        'plans': ctx['plan_rows'],
        'weekly': ctx['weekly_series'],
        'time_intelligence': ctx['time_intelligence'],
        'cohorts': ctx['cohorts'],
        'behavior': ctx['behavior'],
        'recommendations': ctx['recommendations'],
        'predictive': ctx['predictive'],
        'charts': ctx['charts'],
        'plan_sales_all_time': ctx['plan_sales_all_time'],
    }
