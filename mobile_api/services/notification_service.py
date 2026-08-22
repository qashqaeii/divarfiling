"""اعلان‌های in-app و ارسال push."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.utils import timezone

from mobile_api.models import MobileNotification
from mobile_api.services.notification_catalog import (
    ACTIONABLE_TYPES,
    SPECS,
    dedup_key_for,
    get_spec,
    sanitize_deep_link,
)
from mobile_api.services.notification_copy import (
    extract_complete as copy_extract_complete,
    extract_schedule_created as copy_extract_schedule_created,
    schedule_location_label,
    welcome_message,
)
from mobile_api.services.push_service import send_push_to_user


NOTIFICATION_TYPES = {spec.type: spec.title_fa for spec in SPECS.values()}


def _notification_to_dict(n: MobileNotification) -> Dict[str, Any]:
    spec = get_spec(n.notification_type)
    return {
        'id': n.pk,
        'type': n.notification_type,
        'title': n.title,
        'body': n.body,
        'deep_link': n.deep_link,
        'data': n.data or {},
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat() if n.created_at else None,
        'priority': spec.priority,
        'channel': spec.channel,
        'group': spec.group,
        'needs_action': n.notification_type in ACTIONABLE_TYPES and not n.is_read,
    }


def list_notifications(user, *, limit: int = 20, page: int = 1, page_size: int = 20) -> List[dict]:
    offset = (page - 1) * page_size
    qs = MobileNotification.objects.filter(user=user).order_by('-created_at')
    return [_notification_to_dict(n) for n in qs[offset:offset + min(limit or page_size, page_size)]]


def list_notifications_paginated(user, *, page: int = 1, page_size: int = 20) -> tuple[List[dict], dict]:
    from django.core.paginator import Paginator
    dismiss_stale_license_alerts(user)
    qs = MobileNotification.objects.filter(user=user).order_by('-created_at')
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    items = [_notification_to_dict(n) for n in page_obj.object_list]
    meta = {'page': page, 'page_size': page_size, 'total': paginator.count}
    return items, meta


def unread_count(user) -> int:
    return MobileNotification.objects.filter(user=user, is_read=False).count()


def dismiss_stale_license_alerts(user, license_status: Optional[Dict[str, Any]] = None) -> int:
    """پس از تمدید موفق، اعلان انقضای قدیمی را خوانده‌شده می‌کند."""
    status = license_status
    if status is None:
        from mobile_api.services.license_service import license_status_payload
        status = license_status_payload(user)
    if not status.get('valid') or status.get('expiring_soon'):
        return 0
    return MobileNotification.objects.filter(
        user=user,
        notification_type='license_expiry',
        is_read=False,
    ).update(is_read=True, read_at=timezone.now())


def mark_read(user, notification_id: int) -> bool:
    updated = MobileNotification.objects.filter(
        user=user, pk=notification_id, is_read=False,
    ).update(is_read=True, read_at=timezone.now())
    return updated > 0


def mark_all_read(user) -> int:
    return MobileNotification.objects.filter(user=user, is_read=False).update(
        is_read=True,
        read_at=timezone.now(),
    )


def create_notification(
    user,
    *,
    notification_type: str,
    title: str,
    body: str = '',
    deep_link: str = '',
    data: Optional[dict] = None,
    send_push: bool = True,
) -> MobileNotification:
    payload = dict(data or {})
    spec = get_spec(notification_type)
    link = sanitize_deep_link(deep_link or spec.default_deep_link, notification_type)
    key = dedup_key_for(notification_type, payload)
    if key:
        existing = MobileNotification.objects.filter(user=user, dedup_key=key).first()
        if existing:
            return existing
    n = MobileNotification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        body=body,
        deep_link=link,
        data=payload,
        dedup_key=key,
        push_status='pending' if send_push else '',
    )
    if send_push:
        from mobile_api.services.notification_scheduler import user_push_enabled
        if user_push_enabled(user, notification_type):
            accepted = send_push_to_user(
                user,
                title=title,
                body=body or title,
                data={
                    'notification_id': str(n.pk),
                    'type': notification_type,
                    'deep_link': link,
                    'channel': spec.channel,
                    'priority': spec.priority,
                    'notification_key': key or str(n.pk),
                    **payload,
                },
                display_notification=spec.display_fcm_notification,
            )
            n.push_status = 'accepted' if accepted else 'failed'
            n.save(update_fields=['push_status'])
        else:
            n.push_status = 'skipped'
            n.save(update_fields=['push_status'])
    return n


def ensure_local_reminder_inbox(user, reminder_id: int) -> Optional[MobileNotification]:
    """وقتی اعلان محلی روی دستگاه نمایش داده شد، inbox سرور را هم می‌سازد."""
    from workspace.models import Reminder
    from mobile_api.services.notification_copy import reminder_call, reminder_visit
    from mobile_api.services.reminder_push_sync import _reminder_deep_link, _reminder_type

    reminder = Reminder.objects.filter(pk=reminder_id, user=user).select_related('customer').first()
    if not reminder:
        return None
    ntype = _reminder_type(reminder)
    key = dedup_key_for(ntype, {'reminder_id': reminder.pk})
    existing = MobileNotification.objects.filter(user=user, dedup_key=key).first()
    if existing:
        return existing
    contact_name = reminder.customer.name if reminder.customer else ''
    if ntype == 'reminder_visit':
        title, body = reminder_visit(contact_name, reminder.title or '', reminder.note or '')
    else:
        title, body = reminder_call(contact_name, reminder.title or '', reminder.note or '')
    return create_notification(
        user,
        notification_type=ntype,
        title=title,
        body=body,
        deep_link=_reminder_deep_link(reminder),
        data={
            'reminder_id': reminder.pk,
            'contact_id': reminder.customer_id,
            'source': 'local',
        },
        send_push=False,
    )


def maybe_create_welcome(user) -> Optional[MobileNotification]:
    if MobileNotification.objects.filter(user=user, notification_type='welcome').exists():
        return None
    title, body = welcome_message()
    return create_notification(
        user,
        notification_type='welcome',
        title=title,
        body=body,
        deep_link='divarfiling://home',
        data={'source': 'fcm_register'},
        send_push=True,
    )


def notify_extract_complete(
    user,
    dataset_id: str,
    dataset_name: str,
    count: int,
    *,
    genuine_personal_count: int = 0,
    disguised_consultant_count: int = 0,
) -> None:
    title, body = copy_extract_complete(
        dataset_name,
        count,
        genuine_personal_count=genuine_personal_count,
        disguised_consultant_count=disguised_consultant_count,
    )
    create_notification(
        user,
        notification_type='extract_complete',
        title=title,
        body=body,
        deep_link=f'divarfiling://filing/{dataset_id}',
        data={
            'dataset_id': dataset_id,
            'ingested_count': count,
            'genuine_personal_count': genuine_personal_count,
            'disguised_consultant_count': disguised_consultant_count,
        },
    )


def notify_schedule_created(user, schedule) -> None:
    """اعلان in-app هنگام ذخیره زمان‌بندی — push محلی از خود اپ نمایش داده می‌شود."""
    location = schedule_location_label(schedule.filters or {})
    title, body = copy_extract_schedule_created(
        location,
        float(schedule.interval_hours),
        int(schedule.max_items),
    )
    create_notification(
        user,
        notification_type='extract_schedule_created',
        title=title,
        body=body,
        deep_link='divarfiling://extract/schedules',
        data={'schedule_id': schedule.pk},
        send_push=False,
    )
