"""اعلان‌های in-app و ارسال push."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.utils import timezone

from mobile_api.models import MobileNotification
from mobile_api.services.notification_copy import (
    extract_complete as copy_extract_complete,
    extract_schedule_created as copy_extract_schedule_created,
    new_dataset as copy_new_dataset,
    schedule_location_label,
)
from mobile_api.services.push_service import send_push_to_user


NOTIFICATION_TYPES = {
    'reminder_call': 'یادآور تماس',
    'reminder_visit': 'یادآور بازدید',
    'today_digest': 'برنامه امروز',
    'overdue_followup': 'پیگیری معوق',
    'extract_complete': 'پایان استخراج',
    'extract_schedule_due': 'زمان استخراج',
    'extract_schedule_created': 'زمان‌بندی استخراج',
    'new_dataset': 'فایل جدید',
    'customer_match': 'فایل مناسب مشتری',
    'price_drop': 'کاهش قیمت',
    'license_expiry': 'لایسنس',
    'welcome': 'خوش‌آمد',
}


def _notification_to_dict(n: MobileNotification) -> Dict[str, Any]:
    return {
        'id': n.pk,
        'type': n.notification_type,
        'title': n.title,
        'body': n.body,
        'deep_link': n.deep_link,
        'data': n.data or {},
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat() if n.created_at else None,
    }


def list_notifications(user, *, limit: int = 20, page: int = 1, page_size: int = 20) -> List[dict]:
    offset = (page - 1) * page_size
    qs = MobileNotification.objects.filter(user=user).order_by('-created_at')
    return [_notification_to_dict(n) for n in qs[offset:offset + min(limit or page_size, page_size)]]


def list_notifications_paginated(user, *, page: int = 1, page_size: int = 20) -> tuple[List[dict], dict]:
    from django.core.paginator import Paginator
    qs = MobileNotification.objects.filter(user=user).order_by('-created_at')
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    items = [_notification_to_dict(n) for n in page_obj.object_list]
    meta = {'page': page, 'page_size': page_size, 'total': paginator.count}
    return items, meta


def unread_count(user) -> int:
    return MobileNotification.objects.filter(user=user, is_read=False).count()


def mark_read(user, notification_id: int) -> bool:
    updated = MobileNotification.objects.filter(
        user=user, pk=notification_id, is_read=False,
    ).update(is_read=True, read_at=timezone.now())
    return updated > 0


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
    n = MobileNotification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        body=body,
        deep_link=deep_link,
        data=data or {},
    )
    if send_push:
        from mobile_api.services.notification_scheduler import user_push_enabled
        if user_push_enabled(user, notification_type):
            send_push_to_user(
                user,
                title=title,
                body=body or title,
                data={
                    'notification_id': str(n.pk),
                    'type': notification_type,
                    'deep_link': deep_link,
                    **(data or {}),
                },
            )
    return n


def notify_extract_complete(user, dataset_id: str, dataset_name: str, count: int) -> None:
    title, body = copy_extract_complete(dataset_name, count)
    create_notification(
        user,
        notification_type='extract_complete',
        title=title,
        body=body,
        deep_link=f'divarfiling://filing/{dataset_id}',
        data={'dataset_id': dataset_id, 'ingested_count': count},
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


def notify_new_dataset(user, dataset_id: str, dataset_name: str, count: int) -> None:
    title, body = copy_new_dataset(dataset_name, count)
    create_notification(
        user,
        notification_type='new_dataset',
        title=title,
        body=body,
        deep_link=f'divarfiling://filing/{dataset_id}',
        data={'dataset_id': dataset_id},
    )
