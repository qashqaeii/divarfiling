"""مرکز اندروید — Funnel نصب/فعال‌سازی/استفاده و جداول عملیاتی."""
from __future__ import annotations

import math
from typing import Any, Dict, List
from urllib.parse import urlencode

from django.urls import reverse

from accounts.services.admin_android_app import (
    ANDROID_FUNNEL_PAGE_SIZE,
    build_android_funnel_steps,
    build_android_range_summary,
    get_android_activations,
    get_android_app_stats,
    get_android_recent_usage,
    get_android_registrations,
    get_android_user_funnel,
    get_android_version_distribution,
)
from accounts.services.admin_dashboard import (
    TABLE_PREVIEW_ROWS,
    _date_range,
    _pct_change,
    _previous_period_bounds,
    _range_label_fa,
)
from shop.services.app_downloads import android_apk_version_info


def _admin_user_url(pk: int) -> str:
    return reverse('admin:accounts_user_change', args=[pk])


def _admin_device_url(pk: int) -> str:
    return reverse('admin:mobile_api_mobiledevice_change', args=[pk])


def _admin_activation_url(pk: int) -> str:
    return reverse('admin:licenses_licenseactivation_change', args=[pk])


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
        item = {
            'user_display': row['user_display'],
            'user_admin_url': _admin_user_url(row['user'].pk),
            'device_count': row.get('device_count', 0),
            'active_device_count': row.get('active_device_count', 0),
            'last_registered_at': row.get('last_registered_at'),
            'last_seen_at': row.get('last_seen_at'),
            'app_version': row.get('app_version', '—'),
            'status_key': row.get('status_key'),
            'status_label': row.get('status_label'),
            'activation_at': activation.activated_at if activation else None,
            'activation_admin_url': _admin_activation_url(activation.pk) if activation else '',
            'plan_label': (
                activation.license.plan.name
                if activation and activation.license_id and activation.license.plan_id
                else '—'
            ),
        }
        serialized.append(item)
    return serialized


def _serialize_registrations(devices) -> List[Dict[str, Any]]:
    rows = []
    for device in devices:
        activation = device.license_activation
        rows.append({
            'user_display': device.user.get_full_name() or device.user.username,
            'user_admin_url': _admin_user_url(device.user_id),
            'device_model': device.device_model or '—',
            'os_version': device.os_version or '—',
            'app_version': device.app_version or '—',
            'is_active': device.is_active,
            'registered_at': device.registered_at,
            'admin_url': _admin_device_url(device.pk),
            'plan_label': (
                activation.license.plan.name
                if activation and activation.license_id and activation.license.plan_id
                else '—'
            ),
        })
    return rows


def _serialize_usage(devices) -> List[Dict[str, Any]]:
    rows = []
    for device in devices:
        rows.append({
            'user_display': device.user.get_full_name() or device.user.username,
            'user_admin_url': _admin_user_url(device.user_id),
            'device_model': device.device_model or '—',
            'app_version': device.app_version or '—',
            'last_seen_at': device.last_seen_at,
            'admin_url': _admin_device_url(device.pk),
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
            'label': act.label or '—',
            'activated_at': act.activated_at,
            'admin_url': _admin_activation_url(act.pk),
        })
    return rows


def get_android_center_context(
    days: int = 30,
    page: int = 1,
    compare: bool = False,
) -> Dict[str, Any]:
    start, end = _date_range(days)
    prev_start, prev_end = _previous_period_bounds(days)
    page = max(1, int(page or 1))

    range_summary = build_android_range_summary(start, end)
    prev_summary = build_android_range_summary(prev_start, prev_end)
    funnel_steps = build_android_funnel_steps(start, end)
    snapshot = get_android_app_stats()
    version_rows = get_android_version_distribution()

    funnel_rows, funnel_total = get_android_user_funnel(
        start=start,
        end=end,
        page=page,
        page_size=ANDROID_FUNNEL_PAGE_SIZE,
    )
    total_pages = max(1, math.ceil(funnel_total / ANDROID_FUNNEL_PAGE_SIZE)) if funnel_total else 1
    page = min(page, total_pages)

    active_conv = _conversion_pct(funnel_steps[1]['count'], funnel_steps[0]['count'])
    usage_conv = _conversion_pct(funnel_steps[2]['count'], funnel_steps[0]['count'])

    version_name, version_code = android_apk_version_info()
    app_version_label = f'{version_name} ({version_code})'

    return {
        'range_label': _range_label_fa(days),
        'days': days,
        'app_version': app_version_label,
        'range_summary': range_summary,
        'range_deltas': {
            'registrations': _pct_change(range_summary['registrations'], prev_summary['registrations']),
            'active_users': _pct_change(range_summary['active_users'], prev_summary['active_users']),
            'activations': _pct_change(range_summary['activations'], prev_summary['activations']),
        },
        'snapshot': snapshot,
        'funnel_steps': funnel_steps,
        'funnel_conversion': {
            'install_to_active': active_conv,
            'install_to_usage': usage_conv,
        },
        'version_rows': version_rows,
        'funnel_rows': _serialize_funnel_rows(funnel_rows),
        'registration_rows': _serialize_registrations(
            get_android_registrations(TABLE_PREVIEW_ROWS, start=start, end=end),
        ),
        'usage_rows': _serialize_usage(
            get_android_recent_usage(TABLE_PREVIEW_ROWS, start=start, end=end),
        ),
        'activation_rows': _serialize_activations(
            get_android_activations(TABLE_PREVIEW_ROWS, start=start, end=end),
        ),
        'table_preview_rows': TABLE_PREVIEW_ROWS,
        'page': page,
        'total_pages': total_pages,
        'funnel_total': funnel_total,
        'page_size': ANDROID_FUNNEL_PAGE_SIZE,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'query_suffix': _build_query_suffix(days, page=page, compare=compare),
        'prev_page_url': _build_query_suffix(days, page=page - 1, compare=compare) if page > 1 else '',
        'next_page_url': _build_query_suffix(days, page=page + 1, compare=compare) if page < total_pages else '',
        'admin_list_urls': {
            'devices': reverse('admin:mobile_api_mobiledevice_changelist'),
            'activations': reverse('admin:licenses_licenseactivation_changelist'),
        },
        'export_urls': {
            'devices': reverse('admin_panel_export', args=['android_devices']) + '?format=xlsx',
            'usage': reverse('admin_panel_export', args=['android_active_devices']) + '?format=xlsx',
        },
    }
