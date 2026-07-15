"""اعلان‌های درون‌برنامه‌ای مرکز توسعه."""
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.urls import reverse

from product_hub.models import FeatureFollow, ProductHubNotification

User = get_user_model()


def unread_count(user) -> int:
    if not user or not user.is_authenticated:
        return 0
    return ProductHubNotification.objects.filter(user=user, is_read=False).count()


def mark_all_read(user) -> int:
    return ProductHubNotification.objects.filter(user=user, is_read=False).update(is_read=True)


def mark_read(user, notification_id) -> bool:
    updated = ProductHubNotification.objects.filter(
        id=notification_id, user=user, is_read=False,
    ).update(is_read=True)
    return bool(updated)


def notify_users(*, users, kind, title, body='', link_path='', feature_request=None, bug_report=None):
    """ایجاد اعلان برای مجموعه کاربران (بدون تکرار)."""
    seen = set()
    objs = []
    for user in users:
        if not user or getattr(user, 'id', None) in seen:
            continue
        seen.add(user.id)
        objs.append(ProductHubNotification(
            user=user,
            kind=kind,
            title=title,
            body=body,
            link_path=link_path or '',
            feature_request=feature_request,
            bug_report=bug_report,
        ))
    if objs:
        ProductHubNotification.objects.bulk_create(objs)
    return len(objs)


def notify_feature_shipped(request_obj):
    """اعلان به ثبت‌کننده و دنبال‌کنندگان هنگام تکمیل پیشنهاد."""
    follower_ids = FeatureFollow.objects.filter(
        request=request_obj,
    ).values_list('user_id', flat=True)
    users = list(User.objects.filter(Q(id=request_obj.user_id) | Q(id__in=follower_ids)))
    version = request_obj.released_in.version if request_obj.released_in_id else ''
    title = 'قابلیتی که دنبال می‌کردید منتشر شد'
    if request_obj.release_note:
        body = request_obj.release_note
    elif version:
        body = f'پیشنهاد «{request_obj.title}» در نسخه {version} اضافه شد.'
    else:
        body = f'پیشنهاد «{request_obj.title}» در نسخه جدید اضافه شد.'
    link = reverse('workspace:product_hub:hub') + '?tab=requests'
    return notify_users(
        users=users,
        kind='feature_shipped',
        title=title,
        body=body,
        link_path=link,
        feature_request=request_obj,
    )


def notify_request_status(request_obj, to_status):
    if to_status == 'completed':
        return notify_feature_shipped(request_obj)
    status_fa = request_obj.get_status_display_fa()
    link = reverse('workspace:product_hub:hub') + '?tab=requests'
    return notify_users(
        users=[request_obj.user],
        kind='request_status',
        title='وضعیت پیشنهاد شما به‌روز شد',
        body=f'«{request_obj.title}» اکنون: {status_fa}',
        link_path=link,
        feature_request=request_obj,
    )


def notify_bug_resolved(bug):
    link = reverse('workspace:product_hub:hub') + '?tab=bugs'
    body = bug.resolution_note or f'مشکل «{bug.title}» رفع شد.'
    return notify_users(
        users=[bug.user],
        kind='bug_resolved',
        title='مشکل گزارش‌شده شما رفع شد',
        body=body,
        link_path=link,
        bug_report=bug,
    )
