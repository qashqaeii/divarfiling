"""ماتریس حرفه‌ای پلن‌ها با smart tags."""
from __future__ import annotations

from typing import Any

from accounts.services.admin_dashboard import (
    PLAN_TYPE_ACCENTS,
    PLAN_TYPE_SHORT_LABELS,
    _plan_short_label,
)
from accounts.services.plan_bi import EMPTY_MSG, pct, safe_div
from shop.models import LicensePlan, Order


def build_plan_matrix(
    *,
    since,
    pricing_views: int,
    checkout_views: int,
    upgrade_stats: dict[str, Any],
) -> list[dict[str, Any]]:
    from django.db.models import Count, Sum

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
        rpv = safe_div(total, pricing_views) if pricing_views else None

        upgrade_rate = None
        upgrade_available = False
        if plan.plan_type == 'daily':
            upgrade_rate = upgrade_stats.get('upgrade_rate')
            upgrade_available = bool(upgrade_stats.get('available'))
        elif plan.plan_type == 'monthly':
            # share of upgrades landing here
            upgrade_rate = upgrade_stats.get('upgrade_rate')
            upgrade_available = bool(upgrade_stats.get('available')) and upgrade_stats.get('upgrade_count', 0) >= 0

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
            'rpv': rpv if rpv is not None else None,
            'rpv_available': pricing_views > 0,
            'funnel_conversion': pct(count, pricing_views, 2) if pricing_views else None,
            'checkout_conversion': pct(count, checkout_views, 2) if checkout_views else None,
            'renewal_rate': None,
            'renewal_available': False,
            'renewal_display': EMPTY_MSG,
            'upgrade_rate': upgrade_rate if upgrade_available else None,
            'upgrade_available': upgrade_available,
            'avg_upgrade_hours': upgrade_stats.get('avg_upgrade_hours') if plan.plan_type in ('daily', 'monthly') else None,
            'ltv': rpu,  # approximate period LTV = revenue per buyer of this plan type
            'tags': [],
        })

    if not rows:
        return rows

    # Smart tags
    by_sales = max(rows, key=lambda r: r['purchases'])
    by_rev = max(rows, key=lambda r: r['revenue'])
    by_ltv = max((r for r in rows if r['buyers'] > 0), key=lambda r: r['ltv'], default=None)
    with_conv = [r for r in rows if r['funnel_conversion'] is not None]
    by_low_conv = min(with_conv, key=lambda r: r['funnel_conversion']) if with_conv else None

    for r in rows:
        tags = []
        if r is by_sales and r['purchases'] > 0:
            tags.append({'key': 'top_seller', 'label': 'پرفروش‌ترین'})
        if r is by_rev and r['revenue'] > 0:
            tags.append({'key': 'top_revenue', 'label': 'بیشترین درآمد'})
        if by_ltv and r is by_ltv and r['ltv'] > 0:
            tags.append({'key': 'highest_ltv', 'label': 'بالاترین LTV'})
        if by_low_conv and r is by_low_conv and r['purchases'] >= 0 and r['funnel_conversion'] is not None:
            if r['purchases'] == 0 or (r['funnel_conversion'] or 0) < 1:
                tags.append({'key': 'lowest_conversion', 'label': 'کمترین نرخ تبدیل'})
        if r['purchases'] == 0:
            tags.append({'key': 'needs_improvement', 'label': 'نیازمند بهبود'})
        elif r['revenue_share'] >= 70:
            tags.append({'key': 'concentration', 'label': 'تمرکز درآمد'})
        r['tags'] = tags

    return rows
