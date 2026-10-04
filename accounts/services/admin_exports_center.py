"""مرکز خروجی — کاتالوگ گزارش‌های Excel/CSV."""
from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import urlencode

from django.urls import reverse

from accounts.services.admin_exports import EXPORT_REGISTRY, get_export_catalog

EXPORT_CATEGORIES: Dict[str, str] = {
    'orders': 'سفارش‌ها',
    'users': 'کاربران',
    'licenses': 'لایسنس‌ها',
    'finance': 'مالی',
    'support': 'پشتیبانی',
    'analytics': 'تحلیل',
    'marketing': 'بازاریابی',
}

EXPORT_CATEGORY_FILTERS = (('all', 'همه'),) + tuple(EXPORT_CATEGORIES.items())


def _export_download_url(key: str, *, days: int, supports_days: bool) -> str:
    params = {'format': 'xlsx'}
    if supports_days:
        params['days'] = str(days)
    return reverse('admin_panel_export', args=[key]) + '?' + urlencode(params)


def _build_query_suffix(days: int, category: str | None = None, compare: bool = False) -> str:
    params: Dict[str, str] = {'days': str(days)}
    if category and category != 'all':
        params['category'] = category
    if compare:
        params['compare'] = '1'
    return '?' + urlencode(params)


def _group_catalog(catalog: List[Dict[str, Any]], *, days: int) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    for category_key, category_label in EXPORT_CATEGORIES.items():
        items = [item for item in catalog if item['category'] == category_key]
        if not items:
            continue
        enriched = []
        for item in items:
            enriched.append({
                **item,
                'download_url': _export_download_url(
                    item['key'],
                    days=days,
                    supports_days=item.get('supports_days', False),
                ),
            })
        groups.append({
            'key': category_key,
            'label': category_label,
            'count': sum(i['count'] for i in enriched),
            'items': enriched,
        })
    return groups


def get_exports_center_context(
    *,
    days: int = 30,
    category: str | None = None,
    compare: bool = False,
) -> Dict[str, Any]:
    catalog = get_export_catalog(days=days)
    if category and category != 'all' and category in EXPORT_CATEGORIES:
        catalog = [item for item in catalog if item['category'] == category]

    groups = _group_catalog(catalog, days=days)
    flat_items = [item for group in groups for item in group['items']]

    return {
        'days': days,
        'category': category or 'all',
        'category_filters': EXPORT_CATEGORY_FILTERS,
        'base_query_suffix': _build_query_suffix(days, category=None, compare=compare),
        'export_groups': groups,
        'export_items': flat_items,
        'export_total_count': len(flat_items),
        'export_row_total': sum(item['count'] for item in flat_items),
        'registry_size': len(EXPORT_REGISTRY),
        'category_labels': EXPORT_CATEGORIES,
    }
