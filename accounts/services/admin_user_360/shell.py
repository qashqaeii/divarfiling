"""هدر و KPI صفحه پرونده."""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.services.admin_user_360.common import (
    TAB_ICONS,
    TAB_KEYS,
    TAB_LABELS,
    resolve_panel_activity_days,
    user_summary_row,
)
from accounts.services.admin_user_360.insights import build_customer_insights
from accounts.services.admin_user_360.tabs import tab_overview
from accounts.services.admin_users_management import get_user_management_detail
from workspace.models import Ticket


KPI_ICONS = {
    'revenue': 'fa-coins',
    'paid_count': 'fa-bag-shopping',
    'pending': 'fa-hourglass-half',
    'license': 'fa-key',
    'devices': 'fa-mobile-screen',
    'datasets': 'fa-layer-group',
    'crm': 'fa-address-book',
    'deals': 'fa-handshake',
    'tickets': 'fa-life-ring',
    'member_days': 'fa-calendar-check',
    'sub_days': 'fa-hourglass-end',
    'last_login': 'fa-right-to-bracket',
}


def _days_remaining(expires_iso: Optional[str]) -> Optional[int]:
    if not expires_iso:
        return None
    from django.utils.dateparse import parse_datetime

    exp = parse_datetime(expires_iso)
    if not exp:
        return None
    if timezone.is_naive(exp):
        exp = timezone.make_aware(exp)
    return max(0, (exp.date() - timezone.now().date()).days)


def build_kpi_strip(summary: Dict[str, Any], user) -> list[Dict[str, Any]]:
    usage = get_user_management_detail(user.id)
    usage = (usage or {}).get('usage') or {}
    tickets_open = Ticket.objects.filter(user=user).exclude(status='closed').count()
    active_devices = (
        summary.get('android', {}).get('devices_count', 0)
    )
    days_left = _days_remaining(summary.get('license_expires_at'))

    last_activity = summary.get('last_login_jalali') or '—'
    if usage.get('days_since_login') is not None:
        last_activity = summary.get('last_login_jalali')

    kpis = [
        {'key': 'revenue', 'label': 'مجموع پرداخت موفق', 'value': int(summary.get('total_spent') or 0), 'unit': 'تومان', 'anchor': 'commerce'},
        {'key': 'paid_count', 'label': 'خریدهای موفق', 'value': int(summary.get('paid_orders_count') or 0), 'anchor': 'commerce'},
        {'key': 'pending', 'label': 'سفارش معلق', 'value': int(summary.get('pending_orders_count') or 0), 'anchor': 'commerce'},
        {'key': 'license', 'label': 'دسترسی ربات', 'value_text': summary.get('license_access_label') or 'ندارد', 'anchor': 'licenses'},
        {'key': 'devices', 'label': 'دستگاه اندروید', 'value': active_devices, 'anchor': 'devices'},
        {'key': 'datasets', 'label': 'فایل / آگهی', 'value_text': f"{summary.get('datasets_count', 0)} / {summary.get('listings_total', 0)}", 'anchor': 'workspace'},
        {'key': 'crm', 'label': 'مخاطب CRM', 'value': int(summary.get('crm_contacts_count') or 0), 'anchor': 'workspace'},
        {'key': 'deals', 'label': 'معاملات', 'value': int(summary.get('crm_deals_count') or 0), 'anchor': 'workspace'},
        {'key': 'tickets', 'label': 'تیکت باز', 'value': tickets_open, 'anchor': 'support'},
        {'key': 'member_days', 'label': 'روز از عضویت', 'value': usage.get('days_since_join', 0), 'anchor': 'account'},
        {'key': 'sub_days', 'label': 'روز تا انقضا', 'value_text': str(days_left) if days_left is not None else '—', 'anchor': 'licenses'},
        {'key': 'last_login', 'label': 'آخرین ورود', 'value_text': last_activity, 'anchor': 'activity'},
    ]
    for kpi in kpis:
        kpi['icon'] = KPI_ICONS.get(kpi['key'], 'fa-chart-simple')
    return kpis


def build_user_360_shell(user, *, request) -> Dict[str, Any]:
    summary = user_summary_row(user)
    detail = get_user_management_detail(user.id) or summary
    insights = build_customer_insights(user, detail)
    overview = tab_overview(user, summary, days=request.GET.get('days'))

    return_url = (request.GET.get('return') or '').strip()
    if return_url and not url_has_allowed_host_and_scheme(
        return_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return_url = ''

    return {
        'user_id': user.id,
        'summary': summary,
        'header': {
            'name': summary.get('name'),
            'display_name': (summary.get('name') or '').strip() or summary.get('username'),
            'phone': summary.get('phone'),
            'email': summary.get('email'),
            'username': summary.get('username'),
            'user_id': user.id,
            'date_joined_jalali': summary.get('date_joined_jalali'),
            'last_login_jalali': summary.get('last_login_jalali'),
            'phone_verified': summary.get('phone_verified'),
            'is_active': summary.get('is_active'),
            'license_plan': summary.get('license_plan'),
            'license_expires_jalali': summary.get('license_expires_jalali'),
            'license_access_label': summary.get('license_access_label'),
            'has_active_license': summary.get('has_active_license'),
        },
        'kpis': build_kpi_strip(summary, user),
        'insights': insights,
        'overview_embedded': overview,
        'panel_range_key': (request.GET.get('days') or 'all').strip().lower(),
        'activity_days': resolve_panel_activity_days(request.GET.get('days')),
        'tabs': [
            {'key': k, 'label': TAB_LABELS[k], 'icon': TAB_ICONS.get(k, 'fa-circle')}
            for k in TAB_KEYS
        ],
        'return_url': return_url or reverse('admin_panel_users'),
        'sales_center_url': reverse('admin_panel_sales'),
        'user_360_id': user.id,
        'permissions': {
            'can_reveal_national_id': bool(request.user.is_superuser),
            'can_view_internal_tickets': bool(
                request.user.is_superuser or request.user.has_perm('workspace.view_ticketmessage')
            ),
        },
    }
