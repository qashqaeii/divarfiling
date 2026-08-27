"""مرکز فعالیت — Timeline رویدادهای مهم سیستم."""
from __future__ import annotations

import math
from collections import OrderedDict
from datetime import timedelta
from typing import Any, Dict, List
from urllib.parse import urlencode

import jdatetime
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_dashboard import (
    _date_range,
    _new_users_between,
    _orders_paid_between,
    _range_label_fa,
    _resolve_activity_type,
    _today,
    collect_activity_events,
)
from shop.models import CardTransferSubmission
from workspace.models import Ticket

ACTIVITY_PAGE_SIZE = 25
ACTIVITY_PER_TYPE_FETCH_CAP = 500

ACTIVITY_FILTERS = (
    ('all', 'همه'),
    ('payment', 'پرداخت'),
    ('signup', 'ثبت‌نام'),
    ('ticket', 'تیکت'),
    ('card_transfer', 'کارت‌به‌کارت'),
)


def _admin_order_url(pk: int) -> str:
    return reverse('admin:shop_order_change', args=[pk])


def _admin_user_url(pk: int) -> str:
    return reverse('admin:accounts_user_change', args=[pk])


def _admin_ticket_url(pk: int) -> str:
    return reverse('admin:workspace_ticket_change', args=[pk])


def _admin_card_url(pk: int) -> str:
    return reverse('admin:shop_cardtransfersubmission_change', args=[pk])


def _detail_url(event: Dict[str, Any]) -> str | None:
    pk = event.get('object_id')
    if not pk:
        return None
    route_map = {
        'order_paid': _admin_order_url,
        'signup': _admin_user_url,
        'ticket': _admin_ticket_url,
        'card_transfer': _admin_card_url,
    }
    builder = route_map.get(event.get('type'))
    return builder(pk) if builder else None


def _activity_summary_counts(start, end) -> Dict[str, int]:
    tickets = Ticket.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()
    card_transfers = CardTransferSubmission.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()
    payments = _orders_paid_between(start, end)
    signups = _new_users_between(start, end)
    return {
        'total': payments + signups + tickets + card_transfers,
        'order_paid': payments,
        'signup': signups,
        'ticket': tickets,
        'card_transfer': card_transfers,
    }


def _filtered_total(counts: Dict[str, int], filter_key: str) -> int:
    event_type = FILTER_TO_EVENT.get(filter_key, None)
    if event_type is None:
        return counts['total']
    return counts.get(event_type, 0)


def _day_group_label(day) -> str:
    today = _today()
    if day == today:
        return 'امروز'
    if day == today - timedelta(days=1):
        return 'دیروز'
    j = jdatetime.date.fromgregorian(date=day)
    from workspace.services.jalali_input import to_persian_digits
    return to_persian_digits(f'{j.year}/{j.month:02d}/{j.day:02d}')


def group_activity_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """گروه‌بندی Timeline بر اساس روز."""
    buckets: OrderedDict[str, List[Dict[str, Any]]] = OrderedDict()
    for event in events:
        at = event.get('at')
        if at is None:
            continue
        day = timezone.localtime(at).date() if timezone.is_aware(at) else at.date()
        label = _day_group_label(day)
        buckets.setdefault(label, []).append(event)
    return [{'label': label, 'events': items} for label, items in buckets.items()]


FILTER_TO_EVENT = {
    'all': None,
    'payment': 'order_paid',
    'signup': 'signup',
    'ticket': 'ticket',
    'card_transfer': 'card_transfer',
}


def _normalize_activity_filter(activity_type: str) -> str:
    raw = (activity_type or 'all').strip() or 'all'
    if raw in FILTER_TO_EVENT:
        return raw
    resolved = _resolve_activity_type(raw)
    for key, event_type in FILTER_TO_EVENT.items():
        if event_type == resolved:
            return key
    return 'all'


def _build_query_suffix(
    days: int,
    activity_type: str | None = None,
    page: int | None = None,
    compare: bool = False,
) -> str:
    params: Dict[str, str] = {'days': str(days)}
    if activity_type and activity_type != 'all':
        params['type'] = activity_type
    if page and page > 1:
        params['page'] = str(page)
    if compare:
        params['compare'] = '1'
    return '?' + urlencode(params)


def enrich_activity_center_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for event in events:
        event['detail_url'] = _detail_url(event)
        event['description'] = event.get('meta') or ''
    return events


def get_activity_center_context(
    days: int = 30,
    activity_type: str = 'all',
    page: int = 1,
    compare: bool = False,
) -> Dict[str, Any]:
    start, end = _date_range(days)
    page = max(1, int(page or 1))
    normalized_type = _normalize_activity_filter(activity_type)

    summary = _activity_summary_counts(start, end)
    total_count = _filtered_total(summary, normalized_type)
    total_pages = max(1, math.ceil(total_count / ACTIVITY_PAGE_SIZE)) if total_count else 1
    page = min(page, total_pages)

    fetch_limit = min(page * ACTIVITY_PAGE_SIZE, ACTIVITY_PER_TYPE_FETCH_CAP)
    raw_events = collect_activity_events(
        start=start,
        end=end,
        activity_type=FILTER_TO_EVENT.get(normalized_type),
        per_type_limit=fetch_limit,
    )
    start_idx = (page - 1) * ACTIVITY_PAGE_SIZE
    end_idx = start_idx + ACTIVITY_PAGE_SIZE
    page_events = enrich_activity_center_events(raw_events[start_idx:end_idx])
    timeline_groups = group_activity_events(page_events)

    return {
        'range_label': _range_label_fa(days),
        'days': days,
        'activity_type': normalized_type,
        'activity_filters': ACTIVITY_FILTERS,
        'summary': summary,
        'timeline_groups': timeline_groups,
        'page': page,
        'total_pages': total_pages,
        'total_count': total_count,
        'page_size': ACTIVITY_PAGE_SIZE,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'query_suffix': _build_query_suffix(days, normalized_type, compare=compare),
        'base_query_suffix': _build_query_suffix(days, compare=compare),
        'prev_page_url': _build_query_suffix(days, normalized_type, page=page - 1, compare=compare) if page > 1 else '',
        'next_page_url': _build_query_suffix(days, normalized_type, page=page + 1, compare=compare) if page < total_pages else '',
    }
