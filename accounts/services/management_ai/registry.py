"""Section registry for Management AI."""
from __future__ import annotations

from typing import Any, Callable, Dict

from accounts.services.admin_dashboard import ALL_TIME_DAYS, is_all_time_range
from accounts.services.management_ai.builders.crm import build_crm_snapshot
from accounts.services.management_ai.builders.licenses import build_licenses_snapshot
from accounts.services.management_ai.builders.sales import build_sales_snapshot
from accounts.services.management_ai.builders.users import build_users_snapshot
from accounts.services.management_ai.executive import build_executive_snapshot
from accounts.services.management_ai.schemas import PHASE1_SECTIONS

BuilderFn = Callable[[int, bool], Dict[str, Any]]

BUILDERS: Dict[str, BuilderFn] = {
    'users': build_users_snapshot,
    'sales': build_sales_snapshot,
    'licenses': build_licenses_snapshot,
    'crm': build_crm_snapshot,
    'executive': build_executive_snapshot,
}


def normalize_period(days: int, compare: bool) -> tuple[int, bool, str]:
    """Return (days_int, compare_enabled, days_key for storage)."""
    if is_all_time_range(days):
        return ALL_TIME_DAYS, False, 'all'
    compare_enabled = bool(compare)
    return int(days), compare_enabled, str(int(days))


def days_key_to_int(days_key: str) -> int:
    if days_key == 'all':
        return ALL_TIME_DAYS
    try:
        return int(days_key)
    except (TypeError, ValueError):
        return ALL_TIME_DAYS


def build_section_snapshot(section: str, days: int, compare: bool) -> Dict[str, Any]:
    if section not in PHASE1_SECTIONS:
        raise ValueError(f'Unknown management AI section: {section}')
    days_int, compare_enabled, _ = normalize_period(days, compare)
    builder = BUILDERS[section]
    return builder(days_int, compare_enabled)
