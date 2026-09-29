"""Licenses section snapshot."""
from __future__ import annotations

from typing import Any, Dict

from accounts.services.admin_licenses_center import get_licenses_center_context
from accounts.services.management_ai.builders._helpers import kpi_metrics, trend_summary
from accounts.services.management_ai.facts import build_action_targets, build_facts_for_section
from accounts.services.management_ai.schemas import SNAPSHOT_SCHEMA_VERSION


def build_licenses_snapshot(days: int, compare: bool, *, include_facts: bool = True) -> Dict[str, Any]:
    ctx = get_licenses_center_context(days=days, compare=compare)
    cards = ctx.get('kpi_cards') or []
    charts = ctx.get('charts') or {}

    metrics = kpi_metrics(
        cards,
        [
            'licenses_new_period',
            'renewals_period',
            'renewal_revenue',
            'renewal_rate_period',
            'licenses_active',
            'licenses_expiring_7d',
            'licenses_expired',
            'active_devices',
            'users_without_license',
        ],
        include_comparison=compare,
    )

    renewal_breakdown = ctx.get('renewal_breakdown') or {}
    if renewal_breakdown:
        metrics['renewal_breakdown'] = {
            'current': {
                'formal_renewals': renewal_breakdown.get('formal_renewals_range'),
                'new_key_repurchase': renewal_breakdown.get('new_key_repurchase_range'),
                'renewal_revenue': renewal_breakdown.get('renewal_revenue_range'),
            },
        }

    lic_trend = trend_summary(charts, 'licenses_activity')
    if lic_trend:
        metrics['activation_trend'] = lic_trend

    facts = build_facts_for_section('licenses') if include_facts else []
    return {
        'schema_version': SNAPSHOT_SCHEMA_VERSION,
        'section': 'licenses',
        'period': {
            'days': str(days) if days != 0 else 'all',
            'comparison_enabled': bool(compare),
        },
        'metrics': metrics,
        'facts': facts,
        'action_targets': build_action_targets('licenses', facts) if include_facts else {},
        'data_quality': {'completeness': None, 'warnings': []},
    }
