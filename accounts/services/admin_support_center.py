"""مرکز پشتیبانی — تیکت، کارت‌به‌کارت و برداشت (Action-oriented)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db.models import Count, Min
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_command_queues import qs_unread_tickets
from accounts.services.admin_dashboard import (
    TABLE_PREVIEW_ROWS,
    _date_range,
    _fill_daily_series,
    _pct_change,
    _previous_period_bounds,
    _range_label_fa,
    get_open_tickets,
    get_pending_card_transfers,
    get_pending_withdrawals,
)
from affiliates.models import Withdrawal
from shop.models import CardTransferSubmission
from workspace.models import Ticket, TicketMessage


def _age_label(dt) -> Optional[str]:
    if not dt:
        return None
    now = timezone.now()
    if timezone.is_aware(dt) and timezone.is_naive(now):
        now = timezone.make_aware(now)
    delta = now - dt
    days = delta.days
    if days <= 0:
        hours = max(1, delta.seconds // 3600)
        return f'{hours} ساعت'
    return f'{days} روز'


def _snapshot_counts() -> Dict[str, int]:
    open_qs = Ticket.objects.exclude(status='closed')
    return {
        'open_tickets': open_qs.count(),
        'unread_tickets': open_qs.filter(staff_has_unread=True).count(),
        'pending_card_transfers': CardTransferSubmission.objects.filter(status='pending').count(),
        'pending_withdrawals': Withdrawal.objects.filter(status='pending').count(),
    }


def _tickets_created_between(start, end) -> int:
    return Ticket.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _tickets_closed_between(start, end) -> int:
    return Ticket.objects.filter(
        closed_at__isnull=False,
        closed_at__date__gte=start,
        closed_at__date__lte=end,
    ).count()


def _card_transfers_between(start, end) -> int:
    return CardTransferSubmission.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _withdrawals_between(start, end) -> int:
    return Withdrawal.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _ticket_created_series(days: int) -> Dict[str, List]:
    start, end = _date_range(days)
    rows = (
        Ticket.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, days=days)
    return {'labels': labels, 'values': values}


def _ticket_closed_series(days: int) -> Dict[str, List]:
    start, end = _date_range(days)
    rows = (
        Ticket.objects.filter(
            closed_at__isnull=False,
            closed_at__date__gte=start,
            closed_at__date__lte=end,
        )
        .annotate(day=TruncDate('closed_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    labels, values = _fill_daily_series(start, end, rows, days=days)
    return {'labels': labels, 'values': values}


def _series_has_data(*series: Dict[str, List]) -> bool:
    return any(sum(s.get('values') or []) > 0 for s in series)


def _build_charts(days: int) -> Dict[str, Any]:
    created = _ticket_created_series(days)
    closed = _ticket_closed_series(days)
    if not _series_has_data(created, closed):
        return {}
    return {
        'tickets_flow': {
            'type': 'combo',
            'labels': created['labels'],
            'datasets': [
                {
                    'label': 'ایجاد شده',
                    'data': created['values'],
                    'type': 'bar',
                    'backgroundColor': 'rgba(59, 130, 246, 0.75)',
                    'borderRadius': 6,
                    'yAxisID': 'y',
                },
                {
                    'label': 'بسته شده',
                    'data': closed['values'],
                    'type': 'line',
                    'borderColor': 'rgba(16, 185, 129, 1)',
                    'backgroundColor': 'rgba(16, 185, 129, 0.12)',
                    'fill': True,
                    'tension': 0.35,
                    'yAxisID': 'y',
                },
            ],
            'axis': 'count',
        },
    }


def _avg_first_response_minutes() -> Optional[float]:
    """میانگین زمان تا اولین پاسخ staff — فقط اگر نمونه کافی باشد."""
    ticket_ids = (
        TicketMessage.objects.filter(is_staff_reply=True, is_internal=False)
        .values_list('ticket_id', flat=True)
        .distinct()[:300]
    )
    deltas: List[float] = []
    for tid in ticket_ids:
        ticket = Ticket.objects.filter(pk=tid).values('created_at').first()
        if not ticket:
            continue
        first_reply = (
            TicketMessage.objects.filter(ticket_id=tid, is_staff_reply=True, is_internal=False)
            .order_by('created_at')
            .values_list('created_at', flat=True)
            .first()
        )
        if not first_reply:
            continue
        minutes = (first_reply - ticket['created_at']).total_seconds() / 60
        if minutes >= 0:
            deltas.append(minutes)
    if len(deltas) < 3:
        return None
    return round(sum(deltas) / len(deltas), 1)


def _ticket_intelligence(*, days: int, start, end) -> Dict[str, Any]:
    open_qs = Ticket.objects.exclude(status='closed')
    oldest_open = open_qs.aggregate(oldest=Min('created_at'))['oldest']
    awaiting_staff = open_qs.filter(staff_has_unread=True).count()
    created_period = _tickets_created_between(start, end)
    avg_response = _avg_first_response_minutes()
    intel: Dict[str, Any] = {
        'oldest_open_age': _age_label(oldest_open),
        'oldest_open_at': oldest_open,
        'awaiting_staff': awaiting_staff,
        'tickets_created_period': created_period,
        'avg_first_response_minutes': avg_response,
    }
    return intel


def _admin_ticket_url(ticket_id: int) -> str:
    return reverse('admin:workspace_ticket_change', args=[ticket_id])


def _admin_card_url(pk: int) -> str:
    return reverse('admin:shop_cardtransfersubmission_change', args=[pk])


def _admin_withdrawal_url(pk: int) -> str:
    return reverse('admin:affiliates_withdrawal_change', args=[pk])


def _build_snapshot_kpi_cards(snapshot: Dict[str, int]) -> List[Dict[str, Any]]:
    return [
        {
            'key': 'open_tickets',
            'label': 'تیکت باز',
            'value': snapshot['open_tickets'],
            'format': 'count',
            'delta': None,
            'delta_label': 'وضعیت فعلی',
            'sublabel': 'پشتیبانی',
            'sparkline': [],
            'icon': 'fa-headset',
            'accent': 'blue',
            'status': 'warn' if snapshot['open_tickets'] else 'ok',
        },
        {
            'key': 'unread_tickets',
            'label': 'خوانده‌نشده',
            'value': snapshot['unread_tickets'],
            'format': 'count',
            'delta': None,
            'delta_label': 'وضعیت فعلی',
            'sublabel': 'نیاز به پاسخ',
            'sparkline': [],
            'icon': 'fa-envelope',
            'accent': 'rose',
            'status': 'warn' if snapshot['unread_tickets'] else 'ok',
        },
        {
            'key': 'pending_card_transfers',
            'label': 'کارت‌به‌کارت معلق',
            'value': snapshot['pending_card_transfers'],
            'format': 'count',
            'delta': None,
            'delta_label': 'وضعیت فعلی',
            'sublabel': 'مالی',
            'sparkline': [],
            'icon': 'fa-money-check',
            'accent': 'amber',
            'status': 'warn' if snapshot['pending_card_transfers'] else 'ok',
        },
        {
            'key': 'pending_withdrawals',
            'label': 'برداشت معلق',
            'value': snapshot['pending_withdrawals'],
            'format': 'count',
            'delta': None,
            'delta_label': 'وضعیت فعلی',
            'sublabel': 'همکار فروش',
            'sparkline': [],
            'icon': 'fa-wallet',
            'accent': 'violet',
            'status': 'warn' if snapshot['pending_withdrawals'] else 'ok',
        },
    ]


def _build_range_kpi_cards(
    *,
    days: int,
    range_label: str,
    tickets_created: int,
    prev_tickets_created: int,
    tickets_closed: int,
    prev_tickets_closed: int,
    card_transfers: int,
    prev_card_transfers: int,
    withdrawals: int,
    prev_withdrawals: int,
) -> List[Dict[str, Any]]:
    return [
        {
            'key': 'tickets_created_period',
            'label': 'تیکت جدید',
            'value': tickets_created,
            'format': 'count',
            'delta': _pct_change(tickets_created, prev_tickets_created),
            'delta_label': range_label,
            'sublabel': 'ایجاد شده',
            'sparkline': _ticket_created_series(days)['values'][-7:],
            'icon': 'fa-plus-circle',
            'accent': 'blue',
            'status': 'ok',
        },
        {
            'key': 'tickets_closed_period',
            'label': 'تیکت بسته‌شده',
            'value': tickets_closed,
            'format': 'count',
            'delta': _pct_change(tickets_closed, prev_tickets_closed),
            'delta_label': range_label,
            'sublabel': 'closed_at',
            'sparkline': _ticket_closed_series(days)['values'][-7:],
            'icon': 'fa-check-circle',
            'accent': 'emerald',
            'status': 'ok',
        },
        {
            'key': 'card_transfers_period',
            'label': 'کارت‌به‌کارت ثبت‌شده',
            'value': card_transfers,
            'format': 'count',
            'delta': _pct_change(card_transfers, prev_card_transfers),
            'delta_label': range_label,
            'sublabel': 'درخواست',
            'sparkline': [],
            'icon': 'fa-money-check',
            'accent': 'amber',
            'status': 'ok',
        },
        {
            'key': 'withdrawals_period',
            'label': 'درخواست برداشت',
            'value': withdrawals,
            'format': 'count',
            'delta': _pct_change(withdrawals, prev_withdrawals),
            'delta_label': range_label,
            'sublabel': 'ثبت شده',
            'sparkline': [],
            'icon': 'fa-wallet',
            'accent': 'violet',
            'status': 'ok',
        },
    ]


def build_support_center_pulse(
    snapshot: Dict[str, int],
    ticket_intel: Dict[str, Any],
) -> List[Dict[str, Any]]:
    focus_href = reverse('admin_panel_support') + '?focus=unread_tickets#support-table-tickets'
    oldest = ticket_intel.get('oldest_open_age') or ''
    return [
        {
            'label': 'تیکت خوانده‌نشده',
            'value': snapshot.get('unread_tickets', 0),
            'format': 'count',
            'href': focus_href,
            'hint': f'قدیمی‌ترین باز: {oldest}' if oldest else '',
        },
        {
            'label': 'تیکت باز',
            'value': snapshot.get('open_tickets', 0),
            'format': 'count',
            'href': '#support-table-tickets',
        },
        {
            'label': 'پیام خوانده‌نشده (نوبت staff)',
            'value': ticket_intel.get('awaiting_staff', 0),
            'format': 'count',
            'href': focus_href,
        },
        {
            'label': 'کارت‌به‌کارت معلق',
            'value': snapshot.get('pending_card_transfers', 0),
            'format': 'count',
            'href': '#support-table-card',
        },
    ]


def build_support_action_items(snapshot: Dict[str, int]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    open_qs = Ticket.objects.exclude(status='closed')
    unread_qs = open_qs.filter(staff_has_unread=True)
    card_qs = CardTransferSubmission.objects.filter(status='pending')
    withdrawal_qs = Withdrawal.objects.filter(status='pending')

    unread = snapshot.get('unread_tickets', 0)
    if unread:
        oldest = unread_qs.aggregate(oldest=Min('last_message_at'), oldest_created=Min('created_at'))
        dt = oldest['oldest'] or oldest['oldest_created']
        detail = f'{unread} تیکت'
        if age := _age_label(dt):
            detail += f' · قدیمی‌ترین {age}'
        items.append({
            'key': 'unread_tickets',
            'priority': 'critical',
            'title': 'تیکت خوانده‌نشده',
            'count': unread,
            'detail': detail,
            'icon': 'fa-headset',
            'accent': 'rose',
            'cta': 'مشاهده',
            'href': reverse('admin_panel_support') + '?focus=unread_tickets#support-table-tickets',
            'oldest_label': _age_label(dt) if dt else '',
        })

    open_count = snapshot.get('open_tickets', 0)
    if open_count and open_count != unread:
        oldest_open = open_qs.aggregate(oldest=Min('created_at'))['oldest']
        detail = f'{open_count} تیکت باز'
        if age := _age_label(oldest_open):
            detail += f' · قدیمی‌ترین {age}'
        items.append({
            'key': 'open_tickets',
            'priority': 'high',
            'title': 'تیکت باز',
            'count': open_count,
            'detail': detail,
            'icon': 'fa-inbox',
            'accent': 'blue',
            'cta': 'مشاهده',
            'href': '#support-table-tickets',
        })
    elif open_count and not unread:
        oldest_open = open_qs.aggregate(oldest=Min('created_at'))['oldest']
        detail = f'{open_count} تیکت'
        if age := _age_label(oldest_open):
            detail += f' · قدیمی‌ترین {age}'
        items.append({
            'key': 'open_tickets',
            'priority': 'medium',
            'title': 'تیکت باز',
            'count': open_count,
            'detail': detail,
            'icon': 'fa-inbox',
            'accent': 'blue',
            'cta': 'مشاهده',
            'href': '#support-table-tickets',
        })

    card_pending = snapshot.get('pending_card_transfers', 0)
    if card_pending:
        oldest_card = card_qs.aggregate(oldest=Min('created_at'))['oldest']
        detail = f'{card_pending} واریز'
        if age := _age_label(oldest_card):
            detail += f' · قدیمی‌ترین {age}'
        items.append({
            'key': 'pending_card_transfers',
            'priority': 'high',
            'title': 'کارت‌به‌کارت در انتظار',
            'count': card_pending,
            'detail': detail,
            'icon': 'fa-money-check',
            'accent': 'amber',
            'cta': 'بررسی',
            'href': reverse('admin_panel_sales') + '#sales-card-transfers',
        })

    withdrawals_pending = snapshot.get('pending_withdrawals', 0)
    if withdrawals_pending:
        oldest_w = withdrawal_qs.aggregate(oldest=Min('created_at'))['oldest']
        detail = f'{withdrawals_pending} درخواست'
        if age := _age_label(oldest_w):
            detail += f' · قدیمی‌ترین {age}'
        items.append({
            'key': 'pending_withdrawals',
            'priority': 'high',
            'title': 'برداشت در انتظار تأیید',
            'count': withdrawals_pending,
            'detail': detail,
            'icon': 'fa-wallet',
            'accent': 'violet',
            'cta': 'تأیید',
            'href': '#support-table-withdrawals',
        })

    priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    items.sort(key=lambda i: (priority_order.get(i['priority'], 9), -int(i.get('count') or 0)))
    return items


def _serialize_tickets(tickets) -> List[Dict[str, Any]]:
    rows = []
    for t in tickets:
        rows.append({
            'id': t.pk,
            'ticket_number': t.ticket_number,
            'subject': t.subject,
            'user_display': t.user.get_full_name() or t.user.username,
            'status': t.status,
            'status_label': t.get_status_display_fa(),
            'priority_label': t.get_priority_display_fa(),
            'staff_unread': t.staff_has_unread,
            'created_at': t.created_at,
            'admin_url': _admin_ticket_url(t.pk),
        })
    return rows


def _serialize_card_transfers(items) -> List[Dict[str, Any]]:
    from shop.services.card_transfer_workflow import serialize_card_transfer_row

    return [serialize_card_transfer_row(ct) for ct in items]


def _serialize_withdrawals(items) -> List[Dict[str, Any]]:
    rows = []
    for w in items:
        rows.append({
            'id': w.pk,
            'user_display': w.wallet.user.get_full_name() or w.wallet.user.username,
            'amount': int(w.amount),
            'bank_name': w.bank_name,
            'status_label': w.get_status_display(),
            'created_at': w.created_at,
            'admin_url': _admin_withdrawal_url(w.pk),
        })
    return rows


def get_support_center_context(
    *,
    days: int = 30,
    compare: bool = False,
    focus: str | None = None,
) -> Dict[str, Any]:
    del compare

    start, end = _date_range(days)
    prev_start, prev_end = _previous_period_bounds(days)
    range_label = _range_label_fa(days)
    snapshot = _snapshot_counts()

    tickets_created = _tickets_created_between(start, end)
    prev_tickets_created = _tickets_created_between(prev_start, prev_end)
    tickets_closed = _tickets_closed_between(start, end)
    prev_tickets_closed = _tickets_closed_between(prev_start, prev_end)
    card_transfers = _card_transfers_between(start, end)
    prev_card_transfers = _card_transfers_between(prev_start, prev_end)
    withdrawals = _withdrawals_between(start, end)
    prev_withdrawals = _withdrawals_between(prev_start, prev_end)

    charts = _build_charts(days)
    ticket_intel = _ticket_intelligence(days=days, start=start, end=end)
    center_pulse = build_support_center_pulse(snapshot, ticket_intel)

    return {
        'center_pulse': center_pulse,
        'chart_days': days,
        'range_label': range_label,
        'snapshot_kpi_cards': _build_snapshot_kpi_cards(snapshot),
        'range_kpi_cards': _build_range_kpi_cards(
            days=days,
            range_label=range_label,
            tickets_created=tickets_created,
            prev_tickets_created=prev_tickets_created,
            tickets_closed=tickets_closed,
            prev_tickets_closed=prev_tickets_closed,
            card_transfers=card_transfers,
            prev_card_transfers=prev_card_transfers,
            withdrawals=withdrawals,
            prev_withdrawals=prev_withdrawals,
        ),
        'action_items': build_support_action_items(snapshot),
        'ticket_intelligence': ticket_intel,
        'charts': charts,
        'charts_enabled': bool(charts),
        'open_tickets_rows': _serialize_tickets(
            qs_unread_tickets()[:TABLE_PREVIEW_ROWS]
            if focus == 'unread_tickets'
            else get_open_tickets(limit=TABLE_PREVIEW_ROWS)
        ),
        'ticket_list_focus': focus or '',
        'card_transfer_rows': _serialize_card_transfers(get_pending_card_transfers(limit=TABLE_PREVIEW_ROWS)),
        'withdrawal_rows': _serialize_withdrawals(get_pending_withdrawals(limit=TABLE_PREVIEW_ROWS)),
        'snapshot_counts': snapshot,
        'table_preview_rows': TABLE_PREVIEW_ROWS,
        'admin_list_urls': {
            'tickets': reverse('admin:workspace_ticket_changelist') + '?status__exact=open',
            'card_transfers': reverse('admin:shop_cardtransfersubmission_changelist') + '?status__exact=pending',
            'withdrawals': reverse('admin:affiliates_withdrawal_changelist') + '?status__exact=pending',
        },
        'export_urls': {
            'open_tickets': reverse('admin_panel_export', args=['open_tickets']) + '?format=xlsx',
            'card_transfers': reverse('admin_panel_export', args=['card_transfers_pending']) + '?format=xlsx',
            'withdrawals': reverse('admin_panel_export', args=['pending_withdrawals']) + '?format=xlsx',
        },
    }
