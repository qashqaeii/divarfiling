"""Context سبک برای Shell مشترک پنل ادمین."""
from __future__ import annotations

from typing import Any, Dict, Tuple

from django.utils import timezone

from accounts.services.admin_dashboard import ALL_TIME_DAYS, _range_label_fa, effective_range_days
from accounts.services.admin_management_assistant import build_management_insights
from accounts.services.admin_action_permissions import can_review_card_transfer, can_send_admin_sms, can_view_user_management
from accounts.services.admin_export_permissions import can_export_report
from accounts.services.admin_exports import EXPORT_REGISTRY
from accounts.services.pending_orders import PENDING_ORDER_STATUSES
from affiliates.models import Withdrawal
from shop.models import Order
from workspace.models import Ticket

ADMIN_PANEL_RANGE_ALL = 'all'
COMMAND_CENTER_RANGES: Tuple[int, ...] = (1, 7, 30, 90)
EXTENDED_PANEL_RANGES: Tuple[int, ...] = (1, 7, 30, 90, 365)


def parse_admin_panel_range(request) -> Tuple[int, str]:
    """بازه مجاز پنل — پیش‌فرض «کل بازه»؛ days=1 یعنی «امروز»."""
    raw = (request.GET.get('days') or ADMIN_PANEL_RANGE_ALL).strip().lower()
    if raw == ADMIN_PANEL_RANGE_ALL:
        return ALL_TIME_DAYS, ADMIN_PANEL_RANGE_ALL
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return ALL_TIME_DAYS, ADMIN_PANEL_RANGE_ALL
    if days not in EXTENDED_PANEL_RANGES:
        return ALL_TIME_DAYS, ADMIN_PANEL_RANGE_ALL
    return days, str(days)


def get_admin_panel_days(request) -> int:
    days, _ = parse_admin_panel_range(request)
    return days


def get_admin_panel_range_key(request) -> str:
    _, range_key = parse_admin_panel_range(request)
    return range_key


def format_admin_panel_days_param(days: int) -> str:
    """مقدار querystring بازه — برای خروجی و لینک‌ها (۰ → all)."""
    if days == ALL_TIME_DAYS:
        return ADMIN_PANEL_RANGE_ALL
    return str(days)


def get_admin_panel_nav_badges() -> Dict[str, int]:
    """Badgeهای Sidebar — فقط شمارش سبک."""
    from django.db import DatabaseError, InterfaceError

    try:
        assistant_insights = len(build_management_insights())
    except Exception:
        assistant_insights = 0
    try:
        return {
            'orders_pending': Order.objects.filter(status__in=PENDING_ORDER_STATUSES).count(),
            'unread_tickets': Ticket.objects.filter(staff_has_unread=True).exclude(status='closed').count(),
            'pending_withdrawals': Withdrawal.objects.filter(status='pending').count(),
            'assistant_insights': assistant_insights,
        }
    except (DatabaseError, InterfaceError):
        return {
            'orders_pending': 0,
            'unread_tickets': 0,
            'pending_withdrawals': 0,
            'assistant_insights': assistant_insights,
        }


def resolve_admin_panel_nav_active(path: str) -> str:
    """شناسه آیتم فعال Sidebar از مسیر URL."""
    path = (path or '').rstrip('/') + '/'
    mapping = (
        ('/accounts/admin-panel/assistant/', 'assistant'),
        ('/accounts/admin-panel/marketing/growth/', 'growth'),
        ('/accounts/admin-panel/marketing/leads/', 'leads'),
        ('/accounts/admin-panel/marketing/lists/', 'leads'),
        ('/accounts/admin-panel/marketing/campaigns/', 'leads'),
        ('/accounts/admin-panel/marketing/attribution/', 'leads'),
        ('/accounts/admin-panel/marketing/automation/', 'leads'),
        ('/accounts/admin-panel/marketing/lead-campaigns/', 'leads'),
        ('/accounts/admin-panel/marketing/', 'marketing'),
        ('/accounts/admin-panel/recovery-center/', 'recovery'),
        ('/accounts/admin-panel/sales/', 'sales'),
        ('/accounts/admin-panel/users/', 'users'),
        ('/accounts/admin-panel/licenses/', 'licenses'),
        ('/accounts/admin-panel/operations/', 'operations'),
        ('/accounts/admin-panel/support/', 'support'),
        ('/accounts/admin-panel/activity/', 'activity'),
        ('/accounts/admin-panel/windows/', 'windows'),
        ('/accounts/admin-panel/android/', 'android'),
        ('/accounts/admin-panel/ai/', 'ai'),
        ('/accounts/admin-panel/crm/', 'crm'),
        ('/accounts/admin-panel/affiliates/', 'affiliates'),
        ('/accounts/admin-panel/exports/', 'exports'),
        ('/accounts/admin-panel/plan-conversion/', 'plan_conversion'),
        ('/accounts/admin-panel/forum/', 'forum'),
        ('/accounts/admin-panel/blog/systematic/', 'blog_systematic'),
        ('/accounts/admin-panel/blog/', 'blog'),
        ('/accounts/admin-panel/academy/', 'academy'),
        ('/accounts/admin-panel/', 'command'),
    )
    for prefix, nav_id in mapping:
        if path.startswith(prefix):
            return nav_id
    return ''


def build_admin_panel_shell_context(request) -> Dict[str, Any]:
    badges = get_admin_panel_nav_badges()
    alert_count = sum(1 for key in ('orders_pending', 'unread_tickets') if badges.get(key, 0) > 0)
    days, range_key = parse_admin_panel_range(request)
    query_suffix = f'?days={range_key}'
    if request.GET.get('compare') == '1' and range_key != ADMIN_PANEL_RANGE_ALL:
        query_suffix += '&compare=1'
    from accounts.services.management_ai.service import is_management_ai_enabled

    return {
        'admin_panel_shell': True,
        'admin_can_review_card_transfers': can_review_card_transfer(request.user),
        'admin_can_send_sms': can_send_admin_sms(request.user),
        'admin_can_view_user_management': can_view_user_management(request.user),
        'admin_export_allowed_keys': tuple(
            key for key in EXPORT_REGISTRY if can_export_report(request.user, key)
        ),
        'admin_management_ai_enabled': is_management_ai_enabled(),
        'chart_days': days,
        'chart_days_effective': effective_range_days(days),
        'admin_panel_range_key': range_key,
        'admin_panel_compare': request.GET.get('compare') == '1' and range_key != ADMIN_PANEL_RANGE_ALL,
        'admin_panel_nav_active': resolve_admin_panel_nav_active(request.path),
        'admin_panel_updated_at': timezone.now(),
        'admin_panel_nav_badges': badges,
        'admin_panel_alert_count': alert_count,
        'admin_panel_query_suffix': query_suffix,
        'admin_panel_range_label_fa': _range_label_fa(days),
    }
