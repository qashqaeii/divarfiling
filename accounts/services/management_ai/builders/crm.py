"""CRM section snapshot."""
from __future__ import annotations

from typing import Any, Dict

from accounts.services.admin_crm_center import get_crm_center_context
from accounts.services.management_ai.builders._helpers import kpi_metrics, trend_summary
from accounts.services.management_ai.facts import build_action_targets, build_facts_for_section
from accounts.services.management_ai.schemas import SNAPSHOT_SCHEMA_VERSION


def build_crm_snapshot(days: int, compare: bool, *, include_facts: bool = True) -> Dict[str, Any]:
    ctx = get_crm_center_context(days=days, compare=compare)
    cards = (ctx.get('range_kpi_cards') or []) + (ctx.get('snapshot_kpi_cards') or [])
    charts = ctx.get('charts') or {}
    adoption = ctx.get('adoption') or {}

    metrics = kpi_metrics(
        cards,
        [
            'customers_new_period',
            'properties_new_period',
            'deals_new_period',
            'deals_won_period',
            'reminders_created_period',
            'crm_active_users_period',
            'contacts_total',
            'properties_total',
            'deals_open',
            'reminders_due',
        ],
        include_comparison=compare,
    )

    if adoption:
        metrics['feature_adoption'] = {'current': adoption}

    pipeline = ctx.get('pipeline_distribution')
    if pipeline:
        metrics['deal_pipeline'] = {'current': pipeline}

    action_counts = ctx.get('action_counts') or {}
    if action_counts.get('overdue_reminders') is not None:
        metrics['overdue_reminders'] = {'current': action_counts['overdue_reminders']}

    deals_trend = trend_summary(charts, 'crm_usage_trend')
    if deals_trend:
        metrics['deals_trend'] = deals_trend

    facts = build_facts_for_section('crm') if include_facts else []
    return {
        'schema_version': SNAPSHOT_SCHEMA_VERSION,
        'section': 'crm',
        'period': {
            'days': str(days) if days != 0 else 'all',
            'comparison_enabled': bool(compare),
        },
        'metrics': metrics,
        'facts': facts,
        'action_targets': build_action_targets('crm', facts) if include_facts else {},
        'data_quality': {'completeness': None, 'warnings': []},
    }
