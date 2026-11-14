"""تیکت پشتیبانی در پرونده ۳۶۰ — جزئیات و عملیات مدیر."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.shortcuts import get_object_or_404

from accounts.services.admin_user_360.common import _jalali
from workspace.models import Ticket, TicketAttachment, TicketMessage
from workspace.support_constants import (
    TICKET_PRIORITY_CHOICES,
    TICKET_STATUS_CHOICES,
)
from workspace.services.support_tickets import (
    add_staff_reply,
    close_ticket,
    mark_ticket_read_by_staff,
    reopen_ticket,
)

VALID_STATUS_KEYS = {key for key, _ in TICKET_STATUS_CHOICES}
VALID_PRIORITY_KEYS = {key for key, _ in TICKET_PRIORITY_CHOICES}


def support_form_options() -> Dict[str, List[Dict[str, str]]]:
    return {
        'status': [{'key': key, 'label': label} for key, label in TICKET_STATUS_CHOICES],
        'priority': [{'key': key, 'label': label} for key, label in TICKET_PRIORITY_CHOICES],
    }


def _author_label(msg: TicketMessage) -> str:
    if not msg.author_id:
        return '—'
    return msg.author.get_full_name() or msg.author.username


def _serialize_attachment(att: TicketAttachment) -> Dict[str, Any]:
    url = ''
    try:
        if att.file:
            url = att.file.url
    except Exception:
        url = ''
    return {
        'id': att.pk,
        'filename': att.original_filename,
        'url': url,
        'size': int(att.file_size or 0),
        'created_jalali': _jalali(att.created_at),
    }


def _serialize_message(
    msg: TicketMessage,
    *,
    attachments_by_msg: Dict[int, list],
) -> Dict[str, Any]:
    body = (msg.body or '').strip()
    return {
        'id': msg.pk,
        'author': _author_label(msg),
        'body': body,
        'body_preview': body[:500],
        'is_staff': bool(msg.is_staff_reply),
        'is_internal': bool(msg.is_internal),
        'created_jalali': _jalali(msg.created_at),
        'attachments': attachments_by_msg.get(msg.pk, []),
    }


def get_user_ticket_or_404(*, user_id: int, ticket_id: int) -> Ticket:
    return get_object_or_404(
        Ticket.objects.select_related('user', 'assigned_to'),
        pk=ticket_id,
        user_id=user_id,
    )


def build_ticket_detail_payload(
    ticket: Ticket,
    *,
    include_internal: bool,
    mark_staff_read: bool = False,
) -> Dict[str, Any]:
    if mark_staff_read:
        mark_ticket_read_by_staff(ticket)

    msgs_qs = TicketMessage.objects.filter(ticket=ticket).select_related('author').order_by('created_at')
    if not include_internal:
        msgs_qs = msgs_qs.filter(is_internal=False)

    message_ids = list(msgs_qs.values_list('pk', flat=True))
    attachments_by_msg: Dict[int, list] = {}
    if message_ids:
        for att in TicketAttachment.objects.filter(message_id__in=message_ids).order_by('created_at'):
            attachments_by_msg.setdefault(att.message_id, []).append(_serialize_attachment(att))

    messages = [_serialize_message(m, attachments_by_msg=attachments_by_msg) for m in msgs_qs]

    assigned = '—'
    if ticket.assigned_to_id:
        assigned = ticket.assigned_to.get_full_name() or ticket.assigned_to.username

    return {
        'ticket_id': ticket.pk,
        'ticket_number': ticket.ticket_number,
        'subject': ticket.subject,
        'description': (ticket.description or '').strip(),
        'category': ticket.get_category_display_fa(),
        'category_key': ticket.category or '',
        'priority': ticket.get_priority_display_fa(),
        'priority_key': ticket.priority or '',
        'status': ticket.get_status_display_fa(),
        'status_key': ticket.status or '',
        'is_closed': bool(ticket.is_closed),
        'assigned_to': assigned,
        'staff_unread': bool(ticket.staff_has_unread),
        'user_unread': bool(ticket.user_has_unread),
        'created_jalali': _jalali(ticket.created_at),
        'updated_jalali': _jalali(ticket.updated_at),
        'last_message_jalali': _jalali(ticket.last_message_at),
        'closed_jalali': _jalali(ticket.closed_at),
        'messages_count': len(messages),
        'messages': messages,
        'form_options': support_form_options(),
    }


def apply_ticket_action(
    *,
    ticket: Ticket,
    staff_user,
    action: str,
    body: str = '',
    is_internal: bool = False,
    status_key: str = '',
    priority_key: str = '',
) -> Dict[str, Any]:
    action = (action or '').strip().lower()

    if action == 'reply':
        if not body.strip():
            raise ValueError('متن پیام الزامی است.')
        if ticket.is_closed and not is_internal:
            raise ValueError('تیکت بسته است؛ برای پاسخ عمومی ابتدا تیکت را باز کنید.')
        new_status = status_key if status_key in VALID_STATUS_KEYS else None
        add_staff_reply(
            ticket=ticket,
            staff_user=staff_user,
            body=body,
            is_internal=is_internal,
            new_status=new_status,
        )
        ticket.refresh_from_db()
        return {'action': action, 'ticket_id': ticket.pk}

    if action == 'close':
        if ticket.is_closed:
            raise ValueError('تیکت از قبل بسته شده است.')
        close_ticket(ticket=ticket, by_user=staff_user, staff=True)
        ticket.refresh_from_db()
        return {'action': action, 'ticket_id': ticket.pk}

    if action == 'reopen':
        if not ticket.is_closed:
            raise ValueError('تیکت باز است.')
        reopen_ticket(ticket=ticket)
        ticket.refresh_from_db()
        return {'action': action, 'ticket_id': ticket.pk}

    if action == 'update_meta':
        updates: list[str] = []
        if status_key:
            if status_key not in VALID_STATUS_KEYS:
                raise ValueError('وضعیت نامعتبر است.')
            ticket.status = status_key
            updates.append('status')
            if status_key == 'closed' and not ticket.closed_at:
                from django.utils import timezone
                ticket.closed_at = timezone.now()
                updates.append('closed_at')
            if status_key != 'closed':
                ticket.closed_at = None
                if 'closed_at' not in updates:
                    updates.append('closed_at')
        if priority_key:
            if priority_key not in VALID_PRIORITY_KEYS:
                raise ValueError('اولویت نامعتبر است.')
            ticket.priority = priority_key
            updates.append('priority')
        if not updates:
            raise ValueError('تغییری برای ذخیره نیست.')
        updates.append('updated_at')
        ticket.save(update_fields=updates)
        return {'action': action, 'ticket_id': ticket.pk}

    if action == 'mark_read':
        mark_ticket_read_by_staff(ticket)
        return {'action': action, 'ticket_id': ticket.pk}

    raise ValueError('عملیات نامعتبر است.')