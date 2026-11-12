"""صف‌های اقدام مرکز فرمان — queryset و لینک فیلترشده مشترک."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from django.db.models import QuerySet
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_dashboard import _today
from accounts.services.pending_orders import PENDING_ORDER_STATUSES
from affiliates.models import Withdrawal
from shop.models import CardTransferSubmission, Order
from shop.services.order_fulfillment_recovery import orders_needing_fulfillment_reconcile_qs
from workspace.models import Ticket

QueueBuilder = Callable[[], QuerySet]


def _age_label(dt) -> str:
    if not dt:
        return 'سن نامشخص'
    now = timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    delta = now - dt
    days = delta.days
    if days >= 1:
        return f'قدیمی‌ترین: {days} روز'
    hours = max(1, delta.seconds // 3600)
    return f'قدیمی‌ترین: {hours} ساعت'


def _queue_stats(qs: QuerySet, *, oldest_field: str) -> Dict[str, Any]:
    count = qs.count()
    oldest = None
    if count:
        oldest = qs.order_by(oldest_field).values_list(oldest_field, flat=True).first()
    return {
        'count': count,
        'oldest_at': oldest,
        'oldest_label': _age_label(oldest) if count else '',
    }


def qs_fulfillment_incomplete() -> QuerySet:
    return orders_needing_fulfillment_reconcile_qs()


def qs_orders_failed_today() -> QuerySet:
    today = _today()
    return Order.objects.filter(status='failed', created_at__date=today).order_by('-created_at')


def qs_orders_pending() -> QuerySet:
    return (
        Order.objects.filter(status__in=PENDING_ORDER_STATUSES)
        .select_related('user', 'product', 'plan')
        .order_by('-created_at')
    )


def qs_unread_tickets() -> QuerySet:
    return (
        Ticket.objects.filter(staff_has_unread=True)
        .exclude(status='closed')
        .select_related('user')
        .order_by('-last_message_at', '-created_at')
    )


def qs_pending_card_transfers() -> QuerySet:
    return (
        CardTransferSubmission.objects.filter(status='pending')
        .select_related('order', 'order__user', 'order__product')
        .order_by('-created_at')
    )


def qs_pending_withdrawals() -> QuerySet:
    return (
        Withdrawal.objects.filter(status='pending')
        .select_related('wallet', 'wallet__user')
        .order_by('-created_at')
    )


def qs_users_pending_payment() -> QuerySet:
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return (
        User.objects.filter(orders__status__in=PENDING_ORDER_STATUSES)
        .distinct()
        .order_by('-date_joined')
    )


COMMAND_QUEUE_SPECS: List[Dict[str, Any]] = [
    {
        'key': 'fulfillment_incomplete',
        'priority': 'critical',
        'title': 'پرداخت موفق · صدور/تمدید ناقص',
        'icon': 'fa-key',
        'accent': 'rose',
        'cta': 'رفع',
        'oldest_field': 'paid_at',
        'queue': qs_fulfillment_incomplete,
        'href': lambda: reverse('admin_panel_sales') + '?focus=fulfillment_incomplete#sales-queue-fulfillment',
    },
    {
        'key': 'orders_failed_today',
        'priority': 'critical',
        'title': 'پرداخت ناموفق امروز',
        'icon': 'fa-circle-xmark',
        'accent': 'rose',
        'cta': 'بررسی',
        'oldest_field': 'created_at',
        'queue': qs_orders_failed_today,
        'href': lambda: reverse('admin_panel_sales') + '?focus=failed_today#sales-table-failed',
    },
    {
        'key': 'unread_tickets',
        'priority': 'critical',
        'title': 'تیکت خوانده‌نشده',
        'icon': 'fa-headset',
        'accent': 'rose',
        'cta': 'مشاهده',
        'oldest_field': 'last_message_at',
        'queue': qs_unread_tickets,
        'href': lambda: reverse('admin_panel_support') + '?focus=unread_tickets#support-table-tickets',
    },
    {
        'key': 'orders_pending',
        'priority': 'high',
        'title': 'سفارش پرداخت‌نشده',
        'icon': 'fa-clock',
        'accent': 'violet',
        'cta': 'صف سفارش',
        'oldest_field': 'created_at',
        'queue': qs_orders_pending,
        'href': lambda: reverse('admin_panel_sales') + '?focus=pending#sales-table-pending',
    },
    {
        'key': 'pending_card_transfers',
        'priority': 'high',
        'title': 'کارت‌به‌کارت معلق',
        'icon': 'fa-money-check',
        'accent': 'cyan',
        'cta': 'بررسی',
        'oldest_field': 'created_at',
        'queue': qs_pending_card_transfers,
        'href': lambda: reverse('admin_panel_sales') + '#sales-card-transfers',
    },
    {
        'key': 'pending_withdrawals',
        'priority': 'medium',
        'title': 'برداشت همکار',
        'icon': 'fa-wallet',
        'accent': 'emerald',
        'cta': 'تأیید',
        'oldest_field': 'created_at',
        'queue': qs_pending_withdrawals,
        'href': lambda: reverse('admin_panel_affiliates') + '#affiliate-withdrawals',
    },
]


def get_command_queue_spec(queue_key: str) -> Optional[Dict[str, Any]]:
    for spec in COMMAND_QUEUE_SPECS:
        if spec['key'] == queue_key:
            return spec
    return None


def build_command_action_items(
    *,
    sms_balance: Dict[str, Any],
    stats: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """صف فشرده — شمارش و سن از همان queryset لینک مقصد."""
    del stats
    priority_rank = {'critical': 0, 'high': 1, 'medium': 2, 'opportunity': 3}
    items: List[Dict[str, Any]] = []

    if sms_balance.get('is_low') and sms_balance.get('ok'):
        credit = int(sms_balance.get('credit') or 0)
        items.append({
            'key': 'sms_low',
            'priority': 'critical',
            'title': 'موجودی SMS کم',
            'count': credit,
            'oldest_label': f'{credit:,} تومان باقی‌مانده',
            'icon': 'fa-comment-sms',
            'accent': 'amber',
            'cta': 'شارژ',
            'href': reverse('admin_panel_marketing'),
        })

    for spec in COMMAND_QUEUE_SPECS:
        qs = spec['queue']()
        meta = _queue_stats(qs, oldest_field=spec['oldest_field'])
        if meta['count'] <= 0:
            continue
        items.append({
            'key': spec['key'],
            'priority': spec['priority'],
            'title': spec['title'],
            'count': meta['count'],
            'oldest_label': meta['oldest_label'],
            'icon': spec['icon'],
            'accent': spec['accent'],
            'cta': spec['cta'],
            'href': spec['href'](),
        })

    items.sort(key=lambda row: (priority_rank.get(row['priority'], 9), -int(row['count'] or 0)))
    return items


def count_fulfillment_incomplete() -> int:
    return qs_fulfillment_incomplete().count()


def fulfillment_incomplete_orders(*, limit: int = 20) -> List[Order]:
    return list(qs_fulfillment_incomplete()[:limit])


def orders_for_queue_focus(focus: str, *, limit: int = 20) -> List[Any]:
    spec = get_command_queue_spec(focus)
    if not spec:
        return []
    return list(spec['queue']()[:limit])
