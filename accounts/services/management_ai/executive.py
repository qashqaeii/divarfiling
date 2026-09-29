"""Executive snapshot — key metrics from Phase 1 sections only."""
from __future__ import annotations

from typing import Any, Dict

from accounts.services.management_ai.builders.crm import build_crm_snapshot
from accounts.services.management_ai.builders.licenses import build_licenses_snapshot
from accounts.services.management_ai.builders.sales import build_sales_snapshot
from accounts.services.management_ai.builders.users import build_users_snapshot
from accounts.services.management_ai.facts import build_action_targets, build_facts_for_section
from accounts.services.management_ai.schemas import SNAPSHOT_SCHEMA_VERSION


def _pick_metrics(snapshot: Dict[str, Any], keys: list) -> Dict[str, Any]:
    metrics = snapshot.get('metrics') or {}
    return {k: metrics[k] for k in keys if k in metrics}


def build_executive_snapshot(days: int, compare: bool) -> Dict[str, Any]:
    users = build_users_snapshot(days, compare, include_facts=False)
    sales = build_sales_snapshot(days, compare, include_facts=False)
    licenses = build_licenses_snapshot(days, compare, include_facts=False)
    crm = build_crm_snapshot(days, compare, include_facts=False)

    facts = build_facts_for_section('executive')

    return {
        'schema_version': SNAPSHOT_SCHEMA_VERSION,
        'section': 'executive',
        'period': {
            'days': str(days) if days != 0 else 'all',
            'comparison_enabled': bool(compare),
        },
        'metrics': {
            'users': _pick_metrics(users, [
                'users_new_period',
                'users_active_current',
                'users_without_license',
                'retention_d30',
                'online_today',
            ]),
            'sales': _pick_metrics(sales, [
                'revenue_range',
                'paid_orders_range',
                'unique_buyers',
                'conversion_rate',
                'aov',
            ]),
            'licenses': _pick_metrics(licenses, [
                'licenses_active',
                'licenses_expiring_7d',
                'renewal_rate_period',
                'renewals_period',
            ]),
            'crm': _pick_metrics(crm, [
                'crm_active_users_period',
                'contacts_total',
                'deals_open',
                'deals_won_period',
                'feature_adoption',
            ]),
        },
        'facts': facts,
        'action_targets': build_action_targets('executive', facts),
        'data_quality': {'completeness': None, 'warnings': []},
    }
