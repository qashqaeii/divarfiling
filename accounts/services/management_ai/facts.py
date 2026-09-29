"""Rule-based facts for Management AI — no LLM."""
from __future__ import annotations

from typing import Any, Dict, List

from django.urls import reverse

from accounts.services.admin_management_assistant import build_management_insights

SECTION_CATEGORIES = {
    'users': {'users'},
    'sales': {'sales'},
    'licenses': {'license'},
    'crm': {'crm'},
    'executive': {'users', 'sales', 'license', 'crm', 'operations', 'marketing'},
}


def build_facts_for_section(section: str) -> List[Dict[str, Any]]:
    categories = SECTION_CATEGORIES.get(section, set())
    facts: List[Dict[str, Any]] = []
    for ins in build_management_insights():
        if ins.category not in categories:
            continue
        facts.append({
            'key': ins.key,
            'count': ins.count,
            'severity': ins.severity,
            'category': ins.category,
            'title': ins.title,
            'what_happened': ins.what_happened,
            'recommendation_rule': ins.recommendation,
        })
    return facts


def build_action_targets(section: str, facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Map fact keys to internal admin URLs (backend-controlled)."""
    targets: Dict[str, Any] = {}
    key_urls = {
        'users_without_license_7d': reverse('admin_panel_users') + '?days=7',
        'users_without_license': reverse('admin_panel_users') + '?days=30',
        'pending_orders': reverse('admin_panel_recovery_center') + '?days=7',
        'failed_payments_today': reverse('admin_panel_sales') + '?days=1',
        'expired_not_renewed': reverse('admin_panel_licenses') + '?days=30',
        'license_expiring_3d': reverse('admin_panel_licenses') + '?days=30',
        'crm_not_started': reverse('admin_panel_crm') + '?days=30',
        'unread_tickets': reverse('admin_panel_support') + '?days=7',
    }
    for fact in facts:
        fk = fact.get('key') or ''
        if fk in key_urls:
            targets[fk] = {
                'type': 'internal_url',
                'url': key_urls[fk],
            }
    if section == 'users':
        targets.setdefault('users_without_license', {
            'type': 'internal_url',
            'url': reverse('admin_panel_users') + '?days=30#ecc-users',
        })
    elif section == 'sales':
        targets.setdefault('orders_pending', {
            'type': 'internal_url',
            'url': reverse('admin_panel_sales') + '#sales-actions',
        })
    elif section == 'crm':
        targets.setdefault('crm_overview', {
            'type': 'internal_url',
            'url': reverse('admin_panel_crm'),
        })
    return targets
