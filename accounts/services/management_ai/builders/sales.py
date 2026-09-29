"""Sales section snapshot."""
from __future__ import annotations

from typing import Any, Dict

from accounts.services.admin_sales_center import get_sales_center_context
from accounts.services.management_ai.builders._helpers import kpi_metrics, trend_summary
from accounts.services.management_ai.facts import build_action_targets, build_facts_for_section
from accounts.services.management_ai.schemas import SNAPSHOT_SCHEMA_VERSION


def build_sales_snapshot(days: int, compare: bool, *, include_facts: bool = True) -> Dict[str, Any]:
    ctx = get_sales_center_context(days=days, compare=compare)
    cards = ctx.get('kpi_cards') or []
    charts = ctx.get('charts') or {}

    metrics = kpi_metrics(
        cards,
        [
            'revenue_range',
            'paid_orders_range',
            'aov',
            'conversion_rate',
            'unique_buyers',
            'revenue_delta',
        ],
        include_comparison=compare,
    )

    snap = ctx.get('snapshot_counts') or {}
    for sk, mk in (
        ('orders_failed', 'failed_payments'),
        ('orders_pending', 'pending_orders'),
        ('pending_card_transfers', 'card_to_card_pending'),
    ):
        if sk in snap:
            metrics[mk] = {'current': snap[sk]}

    plan_sales = ctx.get('plan_sales') or []
    if plan_sales:
        metrics['plan_distribution'] = {
            'current': [
                {'plan': row.get('label') or row.get('plan'), 'count': row.get('count')}
                for row in plan_sales[:8]
            ],
        }

    payment_methods = ctx.get('payment_methods') or []
    if payment_methods:
        metrics['payment_method_distribution'] = {
            'current': [
                {'method': row.get('label') or row.get('key'), 'count': row.get('count')}
                for row in payment_methods[:8]
            ],
        }

    rev_trend = trend_summary(charts, 'revenue_trend')
    ord_trend = trend_summary(charts, 'sales_trend')
    if rev_trend:
        metrics['revenue_trend'] = rev_trend
    if ord_trend:
        metrics['order_trend'] = ord_trend

    facts = build_facts_for_section('sales') if include_facts else []
    return {
        'schema_version': SNAPSHOT_SCHEMA_VERSION,
        'section': 'sales',
        'period': {
            'days': str(days) if days != 0 else 'all',
            'comparison_enabled': bool(compare),
        },
        'metrics': metrics,
        'facts': facts,
        'action_targets': build_action_targets('sales', facts) if include_facts else {},
        'data_quality': {'completeness': None, 'warnings': []},
    }
