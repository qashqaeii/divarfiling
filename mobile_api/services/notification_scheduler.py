"""زمان‌بندی اعلان‌های push موبایل — یادآور، کارهای امروز، پیگیری معوق."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Iterable

from django.contrib.auth import get_user_model
from django.utils import timezone

from mobile_api.models import DEFAULT_NOTIFICATION_PREFS, MobileDevice, MobileNotification
from mobile_api.services.notification_catalog import TYPE_TO_PREF, sanitize_deep_link
from mobile_api.services.notification_service import create_notification
from mobile_api.services.notification_copy import (
    extract_schedule_due as copy_extract_schedule_due,
    license_expiry as copy_license_expiry,
    overdue_followup as copy_overdue_followup,
    reminder_call as copy_reminder_call,
    reminder_visit as copy_reminder_visit,
    today_digest as copy_today_digest,
)
from workspace.models import Reminder
from workspace.services.crm_today import get_today_queue

User = get_user_model()
logger = logging.getLogger(__name__)

LICENSE_EXPIRY_THRESHOLDS = (14, 7, 3, 1, 0)


def user_push_enabled(user, notification_type: str) -> bool:
    """اگر هیچ دستگاهی ترجیح نداشته باشد، پیش‌فرض فعال."""
    pref_key = TYPE_TO_PREF.get(notification_type)
    if not pref_key:
        return True
    devices = MobileDevice.objects.filter(user=user).only('notification_prefs')
    if not devices.exists():
        return True
    for dev in devices:
        prefs = {**DEFAULT_NOTIFICATION_PREFS, **(dev.notification_prefs or {})}
        if prefs.get(pref_key, True):
            return True
    return False


def _user_digest_hour(user) -> int:
    hour = DEFAULT_NOTIFICATION_PREFS['digest_hour']
    for dev in MobileDevice.objects.filter(user=user).only('notification_prefs'):
        prefs = {**DEFAULT_NOTIFICATION_PREFS, **(dev.notification_prefs or {})}
        try:
            hour = int(prefs.get('digest_hour', hour))
        except (TypeError, ValueError):
            pass
    return max(0, min(23, hour))


def _sent_today(user, notification_type: str, *, data_key: str = '', data_value=None) -> bool:
    today_start = timezone.localtime(timezone.now()).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    qs = MobileNotification.objects.filter(
        user=user,
        notification_type=notification_type,
        created_at__gte=today_start,
    )
    if data_key and data_value is not None:
        qs = qs.filter(**{f'data__{data_key}': data_value})
    return qs.exists()


def _reminder_notified(reminder: Reminder) -> bool:
    return MobileNotification.objects.filter(
        user_id=reminder.user_id,
        notification_type__in=('reminder_call', 'reminder_visit'),
        data__reminder_id=reminder.pk,
    ).exists()


def _reminder_deep_link(reminder: Reminder) -> str:
    return sanitize_deep_link(
        f'divarfiling://crm/contacts/{reminder.customer_id}' if reminder.customer_id else 'divarfiling://calendar',
        'reminder_call',
    )


def _reminder_notification_type(reminder: Reminder) -> str:
    title = (reminder.title or '').strip()
    if 'بازدید' in title:
        return 'reminder_visit'
    return 'reminder_call'


def process_due_reminders(*, window_minutes: int = 90) -> int:
    """اعلان یادآورهای سررسیدشده که هنوز اعلان نشده‌اند."""
    now = timezone.now()
    window_start = now - timedelta(minutes=window_minutes)
    reminders = (
        Reminder.objects.filter(
            is_done=False,
            due_at__lte=now,
            due_at__gte=window_start,
        )
        .select_related('customer')
        .order_by('due_at')
    )
    sent = 0
    for reminder in reminders:
        if _reminder_notified(reminder):
            continue
        user = User.objects.filter(pk=reminder.user_id).first()
        if not user:
            continue
        ntype = _reminder_notification_type(reminder)
        if not user_push_enabled(user, ntype):
            continue
        contact_name = reminder.customer.name if reminder.customer else ''
        reminder_title = (reminder.title or '').strip()
        note = (reminder.note or '').strip()
        if ntype == 'reminder_visit':
            title, body = copy_reminder_visit(contact_name, reminder_title, note)
        else:
            title, body = copy_reminder_call(contact_name, reminder_title, note)
        create_notification(
            user,
            notification_type=ntype,
            title=title,
            body=body,
            deep_link=_reminder_deep_link(reminder),
            data={
                'reminder_id': reminder.pk,
                'contact_id': reminder.customer_id,
                'source': 'server_fallback',
            },
            send_push=True,
        )
        sent += 1
    return sent


def process_today_digest(*, force: bool = False) -> int:
    """خلاصه کارهای امروز — یک‌بار در ساعت digest_hour."""
    now = timezone.localtime(timezone.now())
    sent = 0
    for user in _users_with_mobile_devices():
        if not force and now.hour != _user_digest_hour(user):
            continue
        if _sent_today(user, 'today_digest'):
            continue
        if not user_push_enabled(user, 'today_digest'):
            continue
        items, stats = get_today_queue(user)
        total = stats.get('total', 0)
        if total <= 0:
            continue
        overdue = stats.get('overdue', 0)
        today_key = now.date().isoformat()
        title, body = copy_today_digest(total, overdue)
        create_notification(
            user,
            notification_type='today_digest',
            title=title,
            body=body,
            deep_link='divarfiling://crm/today',
            data={'total': total, 'overdue': overdue, 'day': today_key},
            send_push=True,
        )
        sent += 1
    return sent


def process_overdue_followups(*, digest_hour_only: bool = True) -> int:
    """یادآوری پیگیری‌های معوق — یک‌بار در روز."""
    now = timezone.localtime(timezone.now())
    sent = 0
    for user in _users_with_mobile_devices():
        if digest_hour_only and now.hour != _user_digest_hour(user):
            continue
        if _sent_today(user, 'overdue_followup'):
            continue
        if not user_push_enabled(user, 'overdue_followup'):
            continue
        items, stats = get_today_queue(user)
        overdue = stats.get('overdue', 0)
        if overdue <= 0:
            continue
        today_key = now.date().isoformat()
        title, body = copy_overdue_followup(overdue)
        create_notification(
            user,
            notification_type='overdue_followup',
            title=title,
            body=body,
            deep_link='divarfiling://crm/today',
            data={'overdue': overdue, 'day': today_key},
            send_push=True,
        )
        sent += 1
    return sent


def process_license_expiry() -> int:
    """هشدار انقضای لایسنس در آستانه‌های ۱۴، ۷، ۳، ۱ و ۰ روز."""
    from workspace.services.access import _paid_license_qs

    now = timezone.now()
    sent = 0
    for user in _users_with_mobile_devices():
        if not user_push_enabled(user, 'license_expiry'):
            continue
        lic = (
            _paid_license_qs(user)
            .filter(status='active', expires_at__isnull=False)
            .order_by('-expires_at')
            .first()
        )
        if not lic:
            continue
        end_date = timezone.localtime(lic.expires_at).date()
        today = timezone.localtime(now).date()
        days = (end_date - today).days
        threshold = None
        for t in LICENSE_EXPIRY_THRESHOLDS:
            if days == t:
                threshold = t
                break
        if threshold is None:
            continue
        if MobileNotification.objects.filter(
            user=user,
            notification_type='license_expiry',
            data__license_id=lic.pk,
            data__threshold=threshold,
        ).exists():
            continue
        plan_label = lic.plan.name if lic.plan_id else 'پلن شما'
        title, body = copy_license_expiry(threshold, plan_label)
        create_notification(
            user,
            notification_type='license_expiry',
            title=title,
            body=body,
            deep_link='divarfiling://plans',
            data={'license_id': lic.pk, 'threshold': threshold, 'days_remaining': days},
            send_push=True,
        )
        sent += 1
    return sent


def process_due_extraction_schedules() -> int:
    """اعلان FCM برای زمان‌بندی‌های استخراج سررسید‌شده."""
    from mobile_api.services.schedule_service import list_due_schedules_global

    sent = 0
    for schedule in list_due_schedules_global():
        if not user_push_enabled(schedule.user, 'extract_schedule_due'):
            continue
        if _sent_today(schedule.user, 'extract_schedule_due', data_key='schedule_id', data_value=schedule.pk):
            continue
        today_key = timezone.localtime(timezone.now()).date().isoformat()
        title, body = copy_extract_schedule_due(schedule.title)
        create_notification(
            schedule.user,
            notification_type='extract_schedule_due',
            title=title,
            body=body,
            deep_link='divarfiling://extract/schedules',
            data={
                'schedule_id': schedule.pk,
                'action': 'run_schedule',
                'day': today_key,
            },
            send_push=True,
        )
        schedule.last_status = 'queued'
        schedule.save(update_fields=['last_status', 'updated_at'])
        sent += 1
    return sent


def run_all_scheduled(*, force_digest: bool = False) -> dict:
    started = timezone.now()
    result = {
        'reminders': process_due_reminders(),
        'today_digest': process_today_digest(force=force_digest),
        'overdue_followup': process_overdue_followups(digest_hour_only=not force_digest),
        'license_expiry': process_license_expiry(),
        'extraction_schedules': process_due_extraction_schedules(),
        'customer_matches': _process_customer_matches_safe(),
        'broadcasts': _process_due_broadcasts_safe(),
    }
    duration_ms = int((timezone.now() - started).total_seconds() * 1000)
    result['duration_ms'] = duration_ms
    logger.info(
        'mobile notifications job finished duration_ms=%s counts=%s',
        duration_ms,
        {k: v for k, v in result.items() if k != 'duration_ms'},
    )
    return result


def _process_due_broadcasts_safe() -> int:
    try:
        from mobile_api.services.broadcast_service import process_due_broadcasts
        return process_due_broadcasts()
    except Exception:
        logger.exception('broadcast notification job failed')
        return 0


def _process_customer_matches_safe() -> int:
    try:
        from workspace.services.crm_match_notifications import process_customer_matches
        return process_customer_matches()
    except Exception:
        logger.exception('customer match notification job failed')
        return 0


def _users_with_mobile_devices() -> Iterable:
    user_ids = (
        MobileDevice.objects.filter(is_active=True)
        .exclude(fcm_token='')
        .values_list('user_id', flat=True)
        .distinct()
    )
    return User.objects.filter(pk__in=user_ids, is_active=True)
