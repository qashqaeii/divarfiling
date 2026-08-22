"""هماهنگ‌سازی زمان‌بندی محلی یادآور روی دستگاه‌های موبایل."""
from __future__ import annotations

import logging

from django.utils import timezone

from mobile_api.services.notification_catalog import sanitize_deep_link
from mobile_api.services.notification_copy import reminder_call, reminder_visit
from mobile_api.services.push_service import send_push_to_user

logger = logging.getLogger(__name__)


def _reminder_type(reminder) -> str:
    title = (reminder.title or '').strip()
    if 'بازدید' in title:
        return 'reminder_visit'
    return 'reminder_call'


def _reminder_deep_link(reminder) -> str:
    if reminder.customer_id:
        return sanitize_deep_link(
            f'divarfiling://crm/contacts/{reminder.customer_id}',
            'reminder_call',
        )
    return 'divarfiling://calendar'


def _reminder_copy(reminder) -> tuple[str, str]:
    contact_name = reminder.customer.name if reminder.customer_id and reminder.customer else ''
    ntype = _reminder_type(reminder)
    if ntype == 'reminder_visit':
        return reminder_visit(contact_name, reminder.title or '', reminder.note or '')
    return reminder_call(contact_name, reminder.title or '', reminder.note or '')


def sync_reminder_local_schedule(reminder) -> int:
    """FCM data برای schedule/cancel محلی — بدون ساخت inbox."""
    from mobile_api.models import MobileDevice

    if not reminder.user_id:
        return 0
    if not MobileDevice.objects.filter(user_id=reminder.user_id, is_active=True).exclude(fcm_token='').exists():
        return 0
    action = 'cancel_reminder'
    title, body = _reminder_copy(reminder)
    ntype = _reminder_type(reminder)
    due_at = ''
    if not reminder.is_done and reminder.due_at and reminder.due_at > timezone.now():
        action = 'schedule_reminder'
        due_at = reminder.due_at.isoformat()
    data = {
        'action': action,
        'type': ntype,
        'reminder_id': str(reminder.pk),
        'due_at': due_at,
        'deep_link': _reminder_deep_link(reminder),
        'contact_id': str(reminder.customer_id or ''),
        'title': title,
        'body': body,
        'source': 'reminder_sync',
    }
    try:
        return send_push_to_user(
            reminder.user,
            title=title,
            body=body,
            data=data,
            display_notification=False,
        )
    except Exception:
        logger.exception('reminder local-schedule push failed reminder_id=%s', reminder.pk)
        return 0


def cancel_reminder_local_schedule(user, reminder_id: int) -> int:
    try:
        return send_push_to_user(
            user,
            title='یادآور',
            body='',
            data={
                'action': 'cancel_reminder',
                'type': 'reminder_call',
                'reminder_id': str(reminder_id),
                'source': 'reminder_sync',
            },
            display_notification=False,
        )
    except Exception:
        logger.exception('reminder cancel push failed reminder_id=%s', reminder_id)
        return 0
