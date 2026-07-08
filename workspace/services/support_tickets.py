"""منطق کسب‌وکار سیستم تیکت پشتیبانی."""
from __future__ import annotations

import os
import uuid

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from workspace.support_constants import (
    TICKET_ATTACHMENT_ALLOWED_EXTENSIONS,
    TICKET_ATTACHMENT_MAX_BYTES,
    TICKET_STATUS_ANSWERED,
    TICKET_STATUS_CLOSED,
    TICKET_STATUS_IN_REVIEW,
    TICKET_STATUS_OPEN,
    TICKET_STATUS_WAITING_USER,
)


def generate_ticket_number() -> str:
    from workspace.models import Ticket

    year = timezone.now().year
    prefix = f'DF-{year}-'
    last = (
        Ticket.objects.filter(ticket_number__startswith=prefix)
        .aggregate(Max('ticket_number'))
        .get('ticket_number__max')
    )
    if last:
        try:
            seq = int(last.rsplit('-', 1)[-1]) + 1
        except (TypeError, ValueError):
            seq = 1
    else:
        seq = 1
    return f'{prefix}{seq:06d}'


def validate_attachment_file(uploaded_file):
    """اعتبارسنجی فایل پیوست — None یا پیام خطا."""
    if not uploaded_file:
        return None
    name = getattr(uploaded_file, 'name', '') or ''
    ext = os.path.splitext(name)[1].lower()
    if ext not in TICKET_ATTACHMENT_ALLOWED_EXTENSIONS:
        allowed = ', '.join(sorted(ext.lstrip('.') for ext in TICKET_ATTACHMENT_ALLOWED_EXTENSIONS))
        return f'فرمت فایل مجاز نیست. پسوندهای مجاز: {allowed}'
    size = getattr(uploaded_file, 'size', 0) or 0
    if size > TICKET_ATTACHMENT_MAX_BYTES:
        mb = TICKET_ATTACHMENT_MAX_BYTES // (1024 * 1024)
        return f'حجم فایل نباید بیشتر از {mb} مگابایت باشد.'
    return None


def _attachment_upload_path(ticket_id: int, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return f'workspace/support/attachments/{ticket_id}/{uuid.uuid4().hex}{ext}'


def save_attachment(*, ticket, message=None, uploaded_file, uploaded_by):
    from workspace.models import TicketAttachment

    path = _attachment_upload_path(ticket.pk, uploaded_file.name)
    saved = default_storage.save(path, uploaded_file)
    return TicketAttachment.objects.create(
        ticket=ticket,
        message=message,
        file=saved,
        original_filename=os.path.basename(uploaded_file.name),
        file_size=getattr(uploaded_file, 'size', 0) or 0,
        uploaded_by=uploaded_by,
    )


@transaction.atomic
def create_ticket(*, user, subject, category, priority, body, attachment=None):
    from workspace.models import Ticket, TicketMessage

    ticket = Ticket.objects.create(
        user=user,
        ticket_number=generate_ticket_number(),
        subject=subject.strip(),
        description=body.strip(),
        category=category,
        priority=priority,
        status=TICKET_STATUS_OPEN,
        last_message_at=timezone.now(),
    )
    message = TicketMessage.objects.create(
        ticket=ticket,
        author=user,
        body=body.strip(),
        is_staff_reply=False,
        is_internal=False,
    )
    if attachment:
        save_attachment(ticket=ticket, message=message, uploaded_file=attachment, uploaded_by=user)
    ticket.staff_has_unread = True
    ticket.save(update_fields=['staff_has_unread', 'updated_at'])
    return ticket


@transaction.atomic
def add_user_reply(*, ticket, user, body, attachment=None):
    from workspace.models import TicketMessage

    if ticket.status == TICKET_STATUS_CLOSED:
        raise ValueError('تیکت بسته شده است.')
    message = TicketMessage.objects.create(
        ticket=ticket,
        author=user,
        body=body.strip(),
        is_staff_reply=False,
        is_internal=False,
    )
    if attachment:
        save_attachment(ticket=ticket, message=message, uploaded_file=attachment, uploaded_by=user)
    ticket.status = TICKET_STATUS_OPEN if ticket.status == TICKET_STATUS_WAITING_USER else ticket.status
    if ticket.status not in (TICKET_STATUS_OPEN, TICKET_STATUS_IN_REVIEW):
        ticket.status = TICKET_STATUS_OPEN
    ticket.last_message_at = timezone.now()
    ticket.staff_has_unread = True
    ticket.user_has_unread = False
    ticket.save(update_fields=['status', 'last_message_at', 'staff_has_unread', 'user_has_unread', 'updated_at'])
    return message


@transaction.atomic
def add_staff_reply(*, ticket, staff_user, body, attachment=None, is_internal=False, new_status=None):
    from workspace.models import TicketMessage

    message = TicketMessage.objects.create(
        ticket=ticket,
        author=staff_user,
        body=body.strip(),
        is_staff_reply=True,
        is_internal=is_internal,
    )
    if attachment and not is_internal:
        save_attachment(ticket=ticket, message=message, uploaded_file=attachment, uploaded_by=staff_user)
    if not is_internal:
        ticket.last_message_at = timezone.now()
        ticket.user_has_unread = True
        ticket.staff_has_unread = False
        if new_status:
            ticket.status = new_status
        elif ticket.status in (TICKET_STATUS_OPEN, TICKET_STATUS_IN_REVIEW):
            ticket.status = TICKET_STATUS_ANSWERED
        ticket.save(update_fields=[
            'status', 'last_message_at', 'user_has_unread', 'staff_has_unread', 'updated_at',
        ])
    return message


@transaction.atomic
def close_ticket(*, ticket, by_user, staff=False):
    ticket.status = TICKET_STATUS_CLOSED
    ticket.closed_at = timezone.now()
    if staff:
        ticket.staff_has_unread = False
    else:
        ticket.user_has_unread = False
    ticket.save(update_fields=['status', 'closed_at', 'user_has_unread', 'staff_has_unread', 'updated_at'])


@transaction.atomic
def reopen_ticket(*, ticket):
    ticket.status = TICKET_STATUS_OPEN
    ticket.closed_at = None
    ticket.staff_has_unread = True
    ticket.user_has_unread = False
    ticket.save(update_fields=['status', 'closed_at', 'staff_has_unread', 'user_has_unread', 'updated_at'])


def mark_ticket_read_by_user(ticket):
    if not ticket.user_has_unread:
        return
    ticket.user_has_unread = False
    ticket.save(update_fields=['user_has_unread', 'updated_at'])
    ticket.messages.filter(is_staff_reply=True, is_internal=False).update(is_read=True)


def get_user_ticket_stats(user):
    from workspace.models import Ticket
    from workspace.support_constants import TICKET_STATUS_CLOSED, TICKET_STATUS_WAITING_USER

    qs = Ticket.objects.filter(user=user)
    open_qs = qs.exclude(status=TICKET_STATUS_CLOSED)
    return {
        'total': qs.count(),
        'open': open_qs.count(),
        'waiting_user': qs.filter(status=TICKET_STATUS_WAITING_USER).count(),
        'closed': qs.filter(status=TICKET_STATUS_CLOSED).count(),
        'unread_replies': qs.filter(user_has_unread=True).count(),
    }


def filter_user_tickets(user, *, status='', priority='', q=''):
    from workspace.models import Ticket

    qs = Ticket.objects.filter(user=user).select_related('assigned_to')
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    if q:
        qs = qs.filter(
            Q(subject__icontains=q)
            | Q(ticket_number__icontains=q)
            | Q(description__icontains=q),
        )
    return qs.order_by('-last_message_at', '-created_at')
