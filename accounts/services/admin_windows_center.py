"""مرکز ویندوز — Funnel نصب/فعال‌سازی/اجرا و جداول عملیاتی."""
from __future__ import annotations

import math
from typing import Any, Dict, List
from urllib.parse import urlencode

from django.urls import reverse

from accounts.services.admin_dashboard import (
    TABLE_PREVIEW_ROWS,
    _date_range,
    _pct_change,
    _previous_period_bounds,
    _range_label_fa,
)
from accounts.services.admin_windows_app import (
    WINDOWS_FUNNEL_PAGE_SIZE,
    build_windows_funnel_steps,
    build_windows_range_summary,
    get_windows_app_stats,
    get_windows_activations,
    get_windows_download_logs,
    get_windows_first_launches,
    get_windows_user_funnel,
)
from shop.services.app_downloads import WINDOWS_APP_VERSION


def _admin_user_url(pk: int) -> str:
    return reverse('admin:accounts_user_change', args=[pk])


def _admin_download_url(pk: int) -> str:
    return reverse('admin:shop_downloadlog_change', args=[pk])


def _admin_activation_url(pk: int) -> str:
    return reverse('admin:licenses_licenseactivation_change', args=[pk])


def _admin_launch_url(pk: int) -> str:
    return reverse('admin:licenses_clientappevent_change', args=[pk])


def _build_query_suffix(days: int, page: int | None = None, compare: bool = False) -> str:
    params: Dict[str, str] = {'days': str(days)}
    if page and page > 1:
        params['page'] = str(page)
    if compare:
        params['compare'] = '1'
    return '?' + urlencode(params)


def _conversion_pct(current: int, base: int) -> int | None:
    if base <= 0:
        return None
    return round((current / base) * 100)


def _serialize_funnel_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    serialized = []
    for row in rows:
        activation = row.get('activation')
        first_launch = row.get('first_launch')
        item = {
            'user_display': row['user_display'],
            'user_admin_url': _admin_user_url(row['user'].pk),
            'download_count': row.get('download_count', 0),
            'last_download_at': row.get('last_download_at'),
            'status_key': row.get('status_key'),
            'status_label': row.get('status_label'),
            'activation_at': activation.activated_at if activation else None,
            'activation_admin_url': _admin_activation_url(activation.pk) if activation else '',
            'first_launch_at': first_launch.created_at if first_launch else None,
            'launch_admin_url': _admin_launch_url(first_launch.pk) if first_launch else '',
            'plan_label': (
                activation.license.plan.name
                if activation and activation.license_id and activation.license.plan_id
                else (
                    first_launch.license.plan.name
                    if first_launch and first_launch.license_id and first_launch.license.plan_id
                    else '—'
                )
            ),
        }
        serialized.append(item)
    return serialized


def _serialize_downloads(logs) -> List[Dict[str, Any]]:
    rows = []
    for log in logs:
        rows.append({
            'user_display': log.user.get_full_name() or log.user.username,
            'user_admin_url': _admin_user_url(log.user_id),
            'plan_label': log.order.plan.name if log.order_id and log.order.plan_id else '—',
            'product_label': log.order.product.title if log.order_id and log.order.product_id else '—',
            'created_at': log.created_at,
            'admin_url': _admin_download_url(log.pk),
        })
    return rows


def _serialize_activations(items) -> List[Dict[str, Any]]:
    rows = []
    for act in items:
        user = act.license.order.user if act.license_id and act.license.order_id else None
        rows.append({
            'user_display': user.get_full_name() or user.username if user else '—',
            'user_admin_url': _admin_user_url(user.pk) if user else '',
            'plan_label': act.license.plan.name if act.license_id and act.license.plan_id else '—',
            'activated_at': act.activated_at,
            'admin_url': _admin_activation_url(act.pk),
        })
    return rows


def _serialize_launches(items) -> List[Dict[str, Any]]:
    rows = []
    for ev in items:
        rows.append({
            'user_display': ev.user.get_full_name() or ev.user.username,
            'user_admin_url': _admin_user_url(ev.user_id),
            'plan_label': ev.license.plan.name if ev.license_id and ev.license.plan_id else '—',
            'app_version': ev.app_version or '—',
            'created_at': ev.created_at,
            'admin_url': _admin_launch_url(ev.pk),
        })
    return rows


def get_windows_center_context(
    days: int = 30,
    page: int = 1,
    compare: bool = False,
) -> Dict[str, Any]:
    start, end = _date_range(days)
    prev_start, prev_end = _previous_period_bounds(days)
    page = max(1, int(page or 1))

    range_summary = build_windows_range_summary(start, end)
    prev_summary = build_windows_range_summary(prev_start, prev_end)
    funnel_steps = build_windows_funnel_steps(start, end)
    snapshot = get_windows_app_stats()

    funnel_rows, funnel_total = get_windows_user_funnel(
        start=start,
        end=end,
        page=page,
        page_size=WINDOWS_FUNNEL_PAGE_SIZE,
    )
    total_pages = max(1, math.ceil(funnel_total / WINDOWS_FUNNEL_PAGE_SIZE)) if funnel_total else 1
    page = min(page, total_pages)

    downloads = _conversion_pct(funnel_steps[1]['count'], funnel_steps[0]['count'])
    launches = _conversion_pct(funnel_steps[2]['count'], funnel_steps[0]['count'])

    return {
        'range_label': _range_label_fa(days),
        'days': days,
        'app_version': WINDOWS_APP_VERSION,
        'range_summary': range_summary,
        'range_deltas': {
            'downloads': _pct_change(range_summary['downloads'], prev_summary['downloads']),
            'activations': _pct_change(range_summary['activations'], prev_summary['activations']),
            'first_launches': _pct_change(range_summary['first_launches'], prev_summary['first_launches']),
        },
        'snapshot': snapshot,
        'funnel_steps': funnel_steps,
        'funnel_conversion': {
            'download_to_activation': downloads,
            'download_to_launch': launches,
        },
        'funnel_rows': _serialize_funnel_rows(funnel_rows),
        'download_rows': _serialize_downloads(
            get_windows_download_logs(TABLE_PREVIEW_ROWS, start=start, end=end),
        ),
        'activation_rows': _serialize_activations(
            get_windows_activations(TABLE_PREVIEW_ROWS, start=start, end=end),
        ),
        'launch_rows': _serialize_launches(
            get_windows_first_launches(TABLE_PREVIEW_ROWS, start=start, end=end),
        ),
        'table_preview_rows': TABLE_PREVIEW_ROWS,
        'page': page,
        'total_pages': total_pages,
        'funnel_total': funnel_total,
        'page_size': WINDOWS_FUNNEL_PAGE_SIZE,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'query_suffix': _build_query_suffix(days, page=page, compare=compare),
        'prev_page_url': _build_query_suffix(days, page=page - 1, compare=compare) if page > 1 else '',
        'next_page_url': _build_query_suffix(days, page=page + 1, compare=compare) if page < total_pages else '',
        'admin_list_urls': {
            'downloads': reverse('admin:shop_downloadlog_changelist'),
            'activations': reverse('admin:licenses_licenseactivation_changelist'),
            'launches': reverse('admin:licenses_clientappevent_changelist'),
        },
        'export_urls': {
            'downloads': reverse('admin_panel_export', args=['windows_downloads']) + '?format=xlsx',
            'launches': reverse('admin_panel_export', args=['windows_first_launches']) + '?format=xlsx',
        },
    }
