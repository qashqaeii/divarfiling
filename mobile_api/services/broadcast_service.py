"""ارسال اعلان گروهی از Django Admin."""
from __future__ import annotations

import logging
import threading
from datetime import timedelta
from typing import List

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from mobile_api.models import MobileDevice, MobileNotificationBroadcast
from mobile_api.services.notification_catalog import (
    BROADCAST_TYPES,
    sanitize_deep_link,
)
from mobile_api.services.notification_service import create_notification
from mobile_api.services.push_service import send_push_to_tokens

logger = logging.getLogger(__name__)
User = get_user_model()
EXPIRING_DAYS = 14
BATCH_SIZE = 80


def target_users(broadcast: MobileNotificationBroadcast) -> List:
    qs = User.objects.filter(is_active=True, mobile_devices__isnull=False).distinct()
    if broadcast.target == MobileNotificationBroadcast.TARGET_SELECTED:
        return list(broadcast.selected_users.filter(is_active=True))
    if broadcast.target == MobileNotificationBroadcast.TARGET_LICENSED:
        licensed_ids = _users_with_active_license()
        return list(qs.filter(pk__in=licensed_ids))
    if broadcast.target == MobileNotificationBroadcast.TARGET_UNLICENSED:
        licensed_ids = _users_with_active_license()
        return list(qs.exclude(pk__in=licensed_ids))
    if broadcast.target == MobileNotificationBroadcast.TARGET_EXPIRING:
        return list(qs.filter(pk__in=_users_with_expiring_license()))
    return list(qs)


def _users_with_active_license() -> List[int]:
    now = timezone.now()
    from licenses.models import License
    return list(
        License.objects.filter(status='active', order__status='paid')
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .values_list('order__user_id', flat=True)
        .distinct()
    )


def _users_with_expiring_license() -> List[int]:
    now = timezone.now()
    until = now + timedelta(days=EXPIRING_DAYS)
    from licenses.models import License
    return list(
        License.objects.filter(
            status='active',
            order__status='paid',
            expires_at__isnull=False,
            expires_at__gt=now,
            expires_at__lte=until,
        ).values_list('order__user_id', flat=True).distinct()
    )


def queue_broadcast(broadcast: MobileNotificationBroadcast, *, immediate: bool) -> None:
    now = timezone.now()
    if broadcast.status in (
        MobileNotificationBroadcast.STATUS_SENDING,
        MobileNotificationBroadcast.STATUS_SENT,
        MobileNotificationBroadcast.STATUS_PARTIAL,
    ):
        return
    if not immediate and broadcast.scheduled_at and broadcast.scheduled_at > now:
        if broadcast.status != MobileNotificationBroadcast.STATUS_SCHEDULED:
            broadcast.status = MobileNotificationBroadcast.STATUS_SCHEDULED
            broadcast.save(update_fields=['status'])
        return
    transaction.on_commit(lambda pk=broadcast.pk: _start_thread(pk))


def _start_thread(broadcast_id: int) -> None:
    thread = threading.Thread(
        target=_run_broadcast_job,
        args=(broadcast_id,),
        daemon=True,
        name=f'mobile-broadcast-{broadcast_id}',
    )
    thread.start()


def _run_broadcast_job(broadcast_id: int) -> None:
    from django.db import close_old_connections
    close_old_connections()
    try:
        process_broadcast(broadcast_id)
    except Exception:
        logger.exception('broadcast job failed id=%s', broadcast_id)
    finally:
        close_old_connections()


def process_due_broadcasts() -> int:
    now = timezone.now()
    ids = list(
        MobileNotificationBroadcast.objects.filter(
            status=MobileNotificationBroadcast.STATUS_SCHEDULED,
            scheduled_at__lte=now,
        ).values_list('pk', flat=True)
    )
    sent = 0
    for pk in ids:
        if process_broadcast(pk):
            sent += 1
    return sent


def process_broadcast(broadcast_id: int) -> bool:
    with transaction.atomic():
        broadcast = (
            MobileNotificationBroadcast.objects.select_for_update()
            .filter(pk=broadcast_id)
            .first()
        )
        if not broadcast:
            return False
        if broadcast.status in (
            MobileNotificationBroadcast.STATUS_SENDING,
            MobileNotificationBroadcast.STATUS_SENT,
            MobileNotificationBroadcast.STATUS_PARTIAL,
        ):
            return False
        broadcast.status = MobileNotificationBroadcast.STATUS_SENDING
        broadcast.save(update_fields=['status'])

    ntype = broadcast.notification_type if broadcast.notification_type in BROADCAST_TYPES else 'announcement'
    deep_link = sanitize_deep_link(broadcast.deep_link, ntype)
    users = target_users(broadcast)
    tokens = list(
        MobileDevice.objects.filter(user__in=users, is_active=True)
        .exclude(fcm_token='')
        .values_list('fcm_token', flat=True)
        .distinct()
    )
    broadcast.target_user_count = len(users)
    broadcast.target_device_count = len(tokens)
    broadcast.save(update_fields=['target_user_count', 'target_device_count'])

    inbox_ok = 0
    for user in users:
        create_notification(
            user,
            notification_type=ntype,
            title=broadcast.title,
            body=broadcast.body,
            deep_link=deep_link,
            data={'broadcast_id': broadcast.pk},
            send_push=False,
        )
        inbox_ok += 1

    success = 0
    failure = 0
    for i in range(0, len(tokens), BATCH_SIZE):
        batch = tokens[i:i + BATCH_SIZE]
        stats = send_push_to_tokens(
            batch,
            title=broadcast.title,
            body=broadcast.body,
            data={
                'type': ntype,
                'deep_link': deep_link,
                'broadcast_id': str(broadcast.pk),
            },
            display_notification=True,
        )
        success += stats['success']
        failure += stats['failure']

    if success and not failure:
        status = MobileNotificationBroadcast.STATUS_SENT
    elif success:
        status = MobileNotificationBroadcast.STATUS_PARTIAL
    else:
        status = MobileNotificationBroadcast.STATUS_FAILED
    broadcast.status = status
    broadcast.success_count = success
    broadcast.fail_count = failure
    broadcast.sent_at = timezone.now()
    if not tokens:
        broadcast.last_error = 'دستگاه فعالی برای مخاطبان یافت نشد.' if users else 'مخاطبی یافت نشد.'
    broadcast.save(update_fields=[
        'status', 'success_count', 'fail_count', 'sent_at', 'last_error',
    ])
    logger.info(
        'broadcast id=%s status=%s users=%s devices=%s fcm_ok=%s fcm_fail=%s inbox=%s',
        broadcast.pk, status, len(users), len(tokens), success, failure, inbox_ok,
    )
    return status in (
        MobileNotificationBroadcast.STATUS_SENT,
        MobileNotificationBroadcast.STATUS_PARTIAL,
    )
