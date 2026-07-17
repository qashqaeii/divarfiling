"""ماتریس حرفه‌ای پلن‌ها با smart tags."""
from __future__ import annotations

from typing import Any

from django.db.models import Count

from accounts.services.admin_dashboard import (
    PLAN_TYPE_ACCENTS,
    _plan_short_label,
)
from accounts.services.plan_bi import EMPTY_MSG, conversion_rate, pct, safe_div
from shop.models import LicensePlan, PlanFunnelEvent


def build_plan_matrix(
    *,
    since,
    upgrade_stats: dict[str, Any],
) -> list[dict[str, Any]]:
    from django.db.models import Sum

    from accounts.services.plan_bi import paid_orders_qs

    sales_rows = (
        paid_orders_qs(since=since)
        .filter(plan_id__isnull=False)
        .values('plan__product_id', 'plan__plan_type')
        .annotate(count=Count('id'), total=Sum('amount'), buyers=Count('user_id', distinct=True))
    )
    sales: dict[tuple, dict] = {}
    for row in sales_rows:
        key = (row['plan__product_id'], row['plan__plan_type'] or '')
        sales[key] = {
            'count': int(row['count'] or 0),
            'total': int(row['total'] or 0),
            'buyers': int(row['buyers'] or 0),
        }

    # بازدید یکتای هر پلن (session) — فقط اگر plan روی Event ست شده باشد
    plan_view_rows = (
        PlanFunnelEvent.objects.filter(
            created_at__gte=since,
            event_type__in=('pricing_view', 'checkout_view'),
            plan_id__isnull=False,
        )
        .exclude(session_key='')
        .values('plan__product_id', 'plan__plan_type')
        .annotate(visitors=Count('session_key', distinct=True))
    )
    plan_visitors: dict[tuple, int] = {}
    for row in plan_view_rows:
        key = (row['plan__product_id'], row['plan__plan_type'] or '')
        plan_visitors[key] = int(row['visitors'] or 0)

    total_count = sum(v['count'] for v in sales.values())
    total_revenue = sum(v['total'] for v in sales.values())

    plans = (
        LicensePlan.objects.filter(is_active=True)
        .select_related('product')
        .order_by('order', 'price', 'id')
    )
    seen: set[tuple] = set()
    rows: list[dict[str, Any]] = []

    for plan in plans:
        key = (plan.product_id, plan.plan_type or '')
        if key in seen:
            continue
        seen.add(key)
        s = sales.get(key, {'count': 0, 'total': 0, 'buyers': 0})
        count, total, buyers = s['count'], s['total'], s['buyers']
        aov = safe_div(total, count)
        rpu = safe_div(total, buyers) if buyers else 0

        visitors = plan_visitors.get(key, 0)
        # RPV = Revenue / Unique Pricing Visitors برای همان پلن
        if visitors > 0:
            rpv = safe_div(total, visitors)
            rpv_available = True
        else:
            rpv = None
            rpv_available = False

        # Conversion فقط با view همان پلن
        funnel_conversion = conversion_rate(count, visitors, 2) if visitors else None
        conversion_available = funnel_conversion is not None

        upgrade_rate = None
        upgrade_available = False
        if plan.plan_type == 'daily':
            upgrade_rate = upgrade_stats.get('upgrade_rate')
            upgrade_available = bool(upgrade_stats.get('available'))
        elif plan.plan_type == 'monthly':
            upgrade_rate = upgrade_stats.get('upgrade_rate')
            upgrade_available = bool(upgrade_stats.get('available'))

        observed_value = rpu  # ارزش محقق‌شده در دوره — نه LTV

        rows.append({
            'plan_id': plan.id,
            'product_id': plan.product_id,
            'product_title': plan.product.title,
            'plan_type': plan.plan_type,
            'label': plan.name,
            'full_label': f'{plan.product.title} — {plan.name}',
            'short_label': _plan_short_label(plan),
            'accent': PLAN_TYPE_ACCENTS.get(plan.plan_type, 'violet'),
            'price': int(plan.price or 0),
            'purchases': count,
            'revenue': total,
            'buyers': buyers,
            'order_share': pct(count, total_count, 1),
            'revenue_share': pct(total, total_revenue, 1),
            'aov': aov,
            'rpu': rpu,
            'rpv': rpv,
            'rpv_available': rpv_available,
            'rpv_display': f'{rpv:,}' if rpv_available and rpv is not None else EMPTY_MSG,
            'plan_visitors': visitors,
            'funnel_conversion': funnel_conversion,
            'checkout_conversion': None,
            'conversion_available': conversion_available,
            'conversion_display': f'{funnel_conversion}٪' if conversion_available else EMPTY_MSG,
            'renewal_rate': None,
            'renewal_available': False,
            'renewal_display': EMPTY_MSG,
            'upgrade_rate': upgrade_rate if upgrade_available else None,
            'upgrade_available': upgrade_available,
            'avg_upgrade_hours': upgrade_stats.get('avg_upgrade_hours') if plan.plan_type in ('daily', 'monthly') else None,
            'observed_customer_value': observed_value,
            'ltv': observed_value,  # backward compat alias — معنا: ارزش محقق‌شده
            'tags': [],
        })

    if not rows:
        return rows

    by_sales = max(rows, key=lambda r: r['purchases'])
    by_rev = max(rows, key=lambda r: r['revenue'])
    by_value = max((r for r in rows if r['buyers'] > 0), key=lambda r: r['observed_customer_value'], default=None)
    with_conv = [r for r in rows if r.get('conversion_available') and r['funnel_conversion'] is not None]
    by_low_conv = min(with_conv, key=lambda r: r['funnel_conversion']) if with_conv else None

    for r in rows:
        tags = []
        if r is by_sales and r['purchases'] > 0:
            tags.append({'key': 'top_seller', 'label': 'پرفروش‌ترین'})
        if r is by_rev and r['revenue'] > 0:
            tags.append({'key': 'top_revenue', 'label': 'بیشترین درآمد'})
        if by_value and r is by_value and r['observed_customer_value'] > 0:
            tags.append({'key': 'highest_value', 'label': 'بیشترین ارزش محقق‌شده'})
        # کمترین نرخ تبدیل فقط وقتی conversion واقعاً موجود است
        if by_low_conv and r is by_low_conv and r['conversion_available']:
            tags.append({'key': 'lowest_conversion', 'label': 'کمترین نرخ تبدیل'})
        if r['purchases'] == 0:
            tags.append({'key': 'no_sales', 'label': 'بدون فروش در دوره'})
        elif r['revenue_share'] >= 70:
            tags.append({'key': 'concentration', 'label': 'تمرکز درآمد'})
        r['tags'] = tags

    return rows
