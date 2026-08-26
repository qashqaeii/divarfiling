"""سریالایزر و نوتیفیکیشن تیکت برای API موبایل."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.services.support_tickets import mark_ticket_read_by_user


def ticket_attachment_to_dict(att, *, request=None) -> Dict[str, Any]:
    url = ''
    if att.file:
        try:
            url = request.build_absolute_uri(att.file.url) if request else att.file.url
        except Exception:
            url = getattr(att.file, 'url', '') or ''
    return {
        'id': att.pk,
        'original_filename': att.original_filename or '',
        'file_size': att.file_size or 0,
        'url': url,
    }


def ticket_message_to_dict(msg, *, request=None) -> Dict[str, Any]:
    attachments = [
        ticket_attachment_to_dict(a, request=request)
        for a in msg.attachments.all()
    ]
    return {
        'id': msg.pk,
        'body': msg.body or '',
        'is_staff_reply': bool(msg.is_staff_reply),
        'created_at': msg.created_at.isoformat() if msg.created_at else None,
        'author_name': (
            (msg.author.get_full_name() or msg.author.get_username())
            if msg.author_id else ''
        ),
        'attachments': attachments,
    }


def ticket_to_dict(ticket, *, request=None, include_messages: bool = False) -> Dict[str, Any]:
    data = {
        'id': ticket.pk,
        'ticket_number': ticket.ticket_number,
        'subject': ticket.subject,
        'status': ticket.status,
        'priority': ticket.priority,
        'category': ticket.category,
        'user_has_unread': ticket.user_has_unread,
        'created_at': ticket.created_at.isoformat() if ticket.created_at else None,
        'updated_at': ticket.updated_at.isoformat() if ticket.updated_at else None,
        'last_message_at': ticket.last_message_at.isoformat() if ticket.last_message_at else None,
        'closed_at': ticket.closed_at.isoformat() if ticket.closed_at else None,
        'description': (ticket.description or '').strip(),
    }
    if include_messages:
        messages = (
            ticket.messages.filter(is_internal=False)
            .select_related('author')
            .prefetch_related('attachments')
            .order_by('created_at')
        )
        data['messages'] = [ticket_message_to_dict(m, request=request) for m in messages]
        data['description'] = ticket.description or ''
    return data


def get_user_ticket(user, ticket_id: int):
    from workspace.models import Ticket

    return (
        Ticket.objects.filter(user=user, pk=ticket_id)
        .prefetch_related('messages__attachments', 'messages__author')
        .first()
    )


def ticket_detail_payload(user, ticket_id: int, *, request=None) -> Optional[Dict[str, Any]]:
    ticket = get_user_ticket(user, ticket_id)
    if not ticket:
        return None
    mark_ticket_read_by_user(ticket)
    return ticket_to_dict(ticket, request=request, include_messages=True)


def notify_ticket_staff_reply(ticket, message_body: str = '') -> None:
    """Push + inbox برای پاسخ پشتیبانی."""
    try:
        from mobile_api.services.notification_service import create_notification

        preview = (message_body or '').strip()
        if len(preview) > 120:
            preview = preview[:117] + '…'
        create_notification(
            ticket.user,
            notification_type='support_reply',
            title=f'پاسخ پشتیبانی — {ticket.ticket_number}',
            body=preview or f'تیکت «{ticket.subject}» پاسخ جدید دارد.',
            deep_link=f'divarfiling://support/{ticket.pk}',
            data={
                'ticket_id': ticket.pk,
                'ticket_number': ticket.ticket_number,
            },
        )
    except Exception:
        # نوتیفیکیشن نباید جریان تیکت را بشکند
        pass
