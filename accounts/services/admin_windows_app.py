"""داده‌های ردیابی اپ ویندوز برای پنل مدیریت."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q
from django.utils import timezone

from licenses.models import ClientAppEvent, LicenseActivation
from shop.models import DownloadLog

User = get_user_model()
TABLE_FETCH_LIMIT = 20

WINDOWS_ACTIVATION_Q = Q(is_active=True) & ~Q(notes__startswith='device_type=mobile')


def get_windows_app_stats() -> Dict[str, int]:
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    downloads_total = DownloadLog.objects.count()
    downloads_week = DownloadLog.objects.filter(created_at__gte=week_ago).count()
    downloads_month = DownloadLog.objects.filter(created_at__gte=month_ago).count()

    activations_total = LicenseActivation.objects.filter(WINDOWS_ACTIVATION_Q).count()
    activations_week = LicenseActivation.objects.filter(
        WINDOWS_ACTIVATION_Q,
        activated_at__gte=week_ago,
    ).count()

    first_launches_total = ClientAppEvent.objects.filter(
        event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
    ).count()
    first_launches_week = ClientAppEvent.objects.filter(
        event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
        created_at__gte=week_ago,
    ).count()

    return {
        'windows_downloads_total': downloads_total,
        'windows_downloads_week': downloads_week,
        'windows_downloads_month': downloads_month,
        'windows_activations_total': activations_total,
        'windows_activations_week': activations_week,
        'windows_first_launches_total': first_launches_total,
        'windows_first_launches_week': first_launches_week,
    }


def get_windows_download_logs(limit: int = TABLE_FETCH_LIMIT):
    return (
        DownloadLog.objects.select_related(
            'user',
            'order',
            'order__plan',
            'order__product',
        )
        .order_by('-created_at')[:limit]
    )


def get_windows_activations(limit: int = TABLE_FETCH_LIMIT):
    return (
        LicenseActivation.objects.filter(WINDOWS_ACTIVATION_Q)
        .select_related(
            'license',
            'license__order__user',
            'license__plan',
            'license__order__product',
        )
        .order_by('-activated_at')[:limit]
    )


def get_windows_first_launches(limit: int = TABLE_FETCH_LIMIT):
    return (
        ClientAppEvent.objects.filter(event_type=ClientAppEvent.EventType.FIRST_LAUNCH)
        .select_related(
            'user',
            'license',
            'license__plan',
            'license__order__product',
            'activation',
        )
        .order_by('-created_at')[:limit]
    )


def get_windows_user_funnel(limit: int = TABLE_FETCH_LIMIT) -> List[Dict[str, Any]]:
    """کاربرانی که اپ ویندوز را دانلود کرده‌اند + وضعیت فعال‌سازی و اجرا."""
    user_ids = list(
        DownloadLog.objects.order_by('-created_at')
        .values_list('user_id', flat=True)
        .distinct()[:limit]
    )
    if not user_ids:
        return []

    users = {u.pk: u for u in User.objects.filter(pk__in=user_ids)}
    download_stats = {
        row['user_id']: row
        for row in DownloadLog.objects.filter(user_id__in=user_ids)
        .values('user_id')
        .annotate(download_count=Count('id'), last_download_at=Max('created_at'))
    }

    rows: List[Dict[str, Any]] = []
    for user_id in user_ids:
        user = users.get(user_id)
        if not user:
            continue
        stats = download_stats.get(user_id, {})
        activation = (
            LicenseActivation.objects.filter(
                WINDOWS_ACTIVATION_Q,
                license__order__user_id=user_id,
            )
            .select_related('license', 'license__plan')
            .order_by('-activated_at')
            .first()
        )
        first_launch = (
            ClientAppEvent.objects.filter(
                user_id=user_id,
                event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
            )
            .order_by('-created_at')
            .first()
        )
        rows.append({
            'user': user,
            'download_count': stats.get('download_count', 0),
            'last_download_at': stats.get('last_download_at'),
            'activation': activation,
            'first_launch': first_launch,
        })
    return rows
