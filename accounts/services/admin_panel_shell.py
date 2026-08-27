"""Context سبک برای Shell مشترک پنل ادمین."""
from __future__ import annotations

from typing import Any, Dict, Tuple

from django.utils import timezone

from accounts.services.admin_management_assistant import build_management_insights
from accounts.services.pending_orders import PENDING_ORDER_STATUSES
from affiliates.models import Withdrawal
from shop.models import Order
from workspace.models import Ticket

COMMAND_CENTER_RANGES: Tuple[int, ...] = (1, 7, 30, 90)


def parse_admin_panel_range(request) -> Tuple[int, str]:
    """بازه مجاز Command Center — days=1 یعنی «امروز»."""
    raw = request.GET.get('days', '30')
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = 30
    if days not in COMMAND_CENTER_RANGES:
        days = 30
    return days, str(days)


def get_admin_panel_days(request) -> int:
    days, _ = parse_admin_panel_range(request)
    return days


def get_admin_panel_range_key(request) -> str:
    _, range_key = parse_admin_panel_range(request)
    return range_key


def get_admin_panel_nav_badges() -> Dict[str, int]:
    """Badgeهای Sidebar — فقط شمارش سبک."""
    try:
        assistant_insights = len(build_management_insights())
    except Exception:
        assistant_insights = 0
    return {
        'orders_pending': Order.objects.filter(status__in=PENDING_ORDER_STATUSES).count(),
        'unread_tickets': Ticket.objects.filter(staff_has_unread=True).exclude(status='closed').count(),
        'pending_withdrawals': Withdrawal.objects.filter(status='pending').count(),
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
        ('/accounts/admin-panel/crm/', 'crm'),
        ('/accounts/admin-panel/affiliates/', 'affiliates'),
        ('/accounts/admin-panel/exports/', 'exports'),
        ('/accounts/admin-panel/plan-conversion/', 'plan_conversion'),
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
    if request.GET.get('compare') == '1':
        query_suffix += '&compare=1'
    return {
        'admin_panel_shell': True,
        'chart_days': days,
        'admin_panel_range_key': range_key,
        'admin_panel_compare': request.GET.get('compare') == '1',
        'admin_panel_nav_active': resolve_admin_panel_nav_active(request.path),
        'admin_panel_updated_at': timezone.now(),
        'admin_panel_nav_badges': badges,
        'admin_panel_alert_count': alert_count,
        'admin_panel_query_suffix': query_suffix,
    }
