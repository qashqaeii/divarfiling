"""Users section snapshot."""
from __future__ import annotations

from typing import Any, Dict

from accounts.services.admin_users_center import get_users_center_context
from accounts.services.management_ai.builders._helpers import kpi_metrics, trend_summary
from accounts.services.management_ai.facts import build_action_targets, build_facts_for_section
from accounts.services.management_ai.metric_semantics import enrich_data_quality
from accounts.services.management_ai.schemas import SNAPSHOT_SCHEMA_VERSION


def build_users_snapshot(days: int, compare: bool, *, include_facts: bool = True) -> Dict[str, Any]:
    ctx = get_users_center_context(days=days, compare=compare)
    include_comparison = compare
    cards = ctx.get('kpi_cards') or []
    charts = ctx.get('charts') or {}

    metrics = kpi_metrics(
        cards,
        [
            'users_new_period',
            'users_active_period',
            'signup_growth_rate',
            'retention_d7',
            'retention_d30',
            'returning_users',
            'users_total',
            'users_active_current',
            'users_without_license',
            'online_today',
            'users_inactive',
            'users_pending_payment',
        ],
        include_comparison=include_comparison,
    )

    reg_trend = trend_summary(charts, 'user_signups')
    active_trend = trend_summary(charts, 'users_active_trend')
    if reg_trend:
        metrics['registration_trend'] = reg_trend
    if active_trend:
        metrics['active_trend'] = active_trend

    facts = build_facts_for_section('users') if include_facts else []
    period = {
        'days': str(days) if days != 0 else 'all',
        'comparison_enabled': bool(compare),
    }
    snapshot = {
        'schema_version': SNAPSHOT_SCHEMA_VERSION,
        'section': 'users',
        'period': period,
        'metrics': metrics,
        'facts': facts,
        'action_targets': build_action_targets('users', facts) if include_facts else {},
        'data_quality': enrich_data_quality('users', metrics, period),
    }
    return snapshot
