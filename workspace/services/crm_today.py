"""صف کار روزانه CRM — پیگیری‌ها و یادآورهای actionable."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from django.utils import timezone

from workspace.models import Customer, Reminder
from workspace.services.crm_scope import customers_qs, reminders_qs
from workspace.services.crm_property_rental_renewal import sanitize_reminder_note_for_display
from workspace.services.jalali_input import format_jalali_date


URGENCY_ORDER = {'overdue': 0, 'today': 1, 'upcoming': 2}
KIND_ORDER = {'followup': 0, 'reminder': 1}


def _followup_items(user, today) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    active_statuses = ['جدید', 'در حال پیگیری']

    overdue_qs = (
        customers_qs(user).filter(
            next_follow_up__lt=today,
            status__in=active_statuses,
        )
        .order_by('next_follow_up', '-priority')
    )
    for c in overdue_qs:
        items.append(_followup_item(c, 'overdue', today))

    today_qs = (
        customers_qs(user).filter(
            next_follow_up=today,
            status__in=active_statuses,
        )
        .order_by('-priority', 'name')
    )
    for c in today_qs:
        items.append(_followup_item(c, 'today', today))

    return items


def _followup_item(customer: Customer, urgency: str, today) -> Dict[str, Any]:
    fu = customer.next_follow_up
    if urgency == 'overdue':
        subtitle = f'معوق — {format_jalali_date(fu)}'
    else:
        subtitle = 'پیگیری امروز'
    return {
        'kind': 'followup',
        'urgency': urgency,
        'id': f'followup-{customer.pk}',
        'customer_id': customer.pk,
        'customer_name': customer.name,
        'customer_phone': customer.phone,
        'customer_type': customer.customer_type,
        'customer_status': customer.status,
        'customer_priority': customer.priority,
        'title': customer.name,
        'subtitle': subtitle,
        'due_date': fu.isoformat() if fu else '',
        'detail_url_name': 'workspace:crm_detail',
    }


def _reminder_items(user, today, now) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    qs = (
        reminders_qs(user).filter(is_done=False)
        .filter(due_at__date__lte=today)
        .select_related('customer')
        .order_by('due_at')
    )
    for r in qs:
        due_date = timezone.localtime(r.due_at).date()
        if r.due_at < now:
            urgency = 'overdue'
            subtitle = f'معوق — {format_jalali_date(due_date)}'
        elif due_date == today:
            urgency = 'today'
            subtitle = format_jalali_date(due_date)
        else:
            urgency = 'overdue'
            subtitle = format_jalali_date(due_date)

        items.append({
            'kind': 'reminder',
            'urgency': urgency,
            'id': f'reminder-{r.pk}',
            'reminder_id': r.pk,
            'customer_id': r.customer_id,
            'customer_name': r.customer.name if r.customer else '',
            'customer_phone': r.customer.phone if r.customer else '',
            'customer_type': r.customer.customer_type if r.customer else '',
            'customer_status': r.customer.status if r.customer else '',
            'title': r.title,
            'subtitle': subtitle,
            'note': sanitize_reminder_note_for_display(r.note or '')[:120],
            'due_at': r.due_at.isoformat(),
            'detail_url_name': 'workspace:crm_detail' if r.customer_id else 'workspace:crm_reminders',
        })
    return items


def get_today_queue(user) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """لیست مرتب‌شده کارهای امروز + آمار."""
    today = timezone.now().date()
    now = timezone.now()

    items = _followup_items(user, today) + _reminder_items(user, today, now)
    items.sort(key=lambda x: (
        URGENCY_ORDER.get(x['urgency'], 9),
        KIND_ORDER.get(x['kind'], 9),
        x.get('title', ''),
    ))

    stats = {
        'total': len(items),
        'overdue': sum(1 for i in items if i['urgency'] == 'overdue'),
        'today': sum(1 for i in items if i['urgency'] == 'today'),
        'followups': sum(1 for i in items if i['kind'] == 'followup'),
        'reminders': sum(1 for i in items if i['kind'] == 'reminder'),
    }
    return items, stats


def count_today_queue(user) -> int:
    return get_today_queue(user)[1]['total']
