"""داده‌های ردیابی اپ ویندوز برای پنل مدیریت."""
from __future__ import annotations

import math
from datetime import timedelta
from typing import Any, Dict, List, Tuple

from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q
from django.utils import timezone

from licenses.models import ClientAppEvent, LicenseActivation
from shop.models import DownloadLog

User = get_user_model()
TABLE_FETCH_LIMIT = 20
WINDOWS_FUNNEL_PAGE_SIZE = 25

WINDOWS_ACTIVATION_Q = Q(is_active=True) & ~Q(notes__startswith='device_type=mobile')
FIRST_LAUNCH = ClientAppEvent.EventType.FIRST_LAUNCH


def _safe_user_display(user) -> str:
    return user.get_full_name() or user.username or 'کاربر'


def _downloads_between(start, end) -> int:
    return DownloadLog.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def _download_users_between(start, end) -> int:
    return (
        DownloadLog.objects.filter(
            created_at__date__gte=start,
            created_at__date__lte=end,
        )
        .values('user_id')
        .distinct()
        .count()
    )


def _activations_between(start, end) -> int:
    return LicenseActivation.objects.filter(
        WINDOWS_ACTIVATION_Q,
        activated_at__date__gte=start,
        activated_at__date__lte=end,
    ).count()


def _first_launches_between(start, end) -> int:
    return ClientAppEvent.objects.filter(
        event_type=FIRST_LAUNCH,
        created_at__date__gte=start,
        created_at__date__lte=end,
    ).count()


def build_windows_range_summary(start, end) -> Dict[str, int]:
    """شمارش رویدادهای ویندوز در بازه — بدون load کل history."""
    return {
        'downloads': _downloads_between(start, end),
        'download_users': _download_users_between(start, end),
        'activations': _activations_between(start, end),
        'first_launches': _first_launches_between(start, end),
    }


def build_windows_funnel_steps(start, end) -> List[Dict[str, Any]]:
    """Funnel کاربر-محور: دانلود → فعال‌سازی → اولین اجرا."""
    download_user_ids = list(
        DownloadLog.objects.filter(
            created_at__date__gte=start,
            created_at__date__lte=end,
        )
        .values('user_id')
        .annotate(last_download_at=Max('created_at'))
        .order_by('-last_download_at')
        .values_list('user_id', flat=True)
    )
    downloads = len(download_user_ids)
    if not downloads:
        return [
            {'key': 'download', 'label': 'دانلود', 'count': 0, 'accent': 'blue'},
            {'key': 'activation', 'label': 'فعال‌سازی', 'count': 0, 'accent': 'violet'},
            {'key': 'first_launch', 'label': 'اولین اجرا', 'count': 0, 'accent': 'emerald'},
        ]

    activated_users = (
        LicenseActivation.objects.filter(
            WINDOWS_ACTIVATION_Q,
            license__order__user_id__in=download_user_ids,
        )
        .values('license__order__user_id')
        .distinct()
        .count()
    )
    launched_users = (
        ClientAppEvent.objects.filter(
            event_type=FIRST_LAUNCH,
            user_id__in=download_user_ids,
        )
        .values('user_id')
        .distinct()
        .count()
    )
    return [
        {'key': 'download', 'label': 'دانلود', 'count': downloads, 'accent': 'blue'},
        {'key': 'activation', 'label': 'فعال‌سازی', 'count': activated_users, 'accent': 'violet'},
        {'key': 'first_launch', 'label': 'اولین اجرا', 'count': launched_users, 'accent': 'emerald'},
    ]


def get_windows_user_funnel(
    limit: int = TABLE_FETCH_LIMIT,
    *,
    start=None,
    end=None,
    page: int = 1,
    page_size: int = WINDOWS_FUNNEL_PAGE_SIZE,
) -> Tuple[List[Dict[str, Any]], int]:
    """کاربران دانلودکننده + وضعیت فعال‌سازی و اجرا."""
    qs = DownloadLog.objects.all()
    if start is not None and end is not None:
        qs = qs.filter(created_at__date__gte=start, created_at__date__lte=end)

    ranked = (
        qs.values('user_id')
        .annotate(download_count=Count('id'), last_download_at=Max('created_at'))
        .order_by('-last_download_at')
    )

    if start is not None and end is not None:
        total = ranked.count()
        page = max(1, int(page or 1))
        total_pages = max(1, math.ceil(total / page_size)) if total else 1
        page = min(page, total_pages)
        offset = (page - 1) * page_size
        user_rows = list(ranked[offset:offset + page_size])
    else:
        total = ranked.count()
        user_rows = list(ranked[:limit])

    user_ids = [row['user_id'] for row in user_rows if row.get('user_id')]
    if not user_ids:
        return [], total

    users = {u.pk: u for u in User.objects.filter(pk__in=user_ids)}
    rows: List[Dict[str, Any]] = []
    for row in user_rows:
        user_id = row.get('user_id')
        user = users.get(user_id)
        if not user:
            continue
        activation = (
            LicenseActivation.objects.filter(
                WINDOWS_ACTIVATION_Q,
                license__order__user_id=user_id,
            )
            .select_related('license', 'license__plan', 'license__order__product')
            .order_by('-activated_at')
            .first()
        )
        first_launch = (
            ClientAppEvent.objects.filter(
                user_id=user_id,
                event_type=FIRST_LAUNCH,
            )
            .select_related('license', 'license__plan')
            .order_by('-created_at')
            .first()
        )
        if first_launch:
            status_key = 'first_launch'
            status_label = 'اولین اجرا'
        elif activation:
            status_key = 'activation'
            status_label = 'فعال‌سازی'
        else:
            status_key = 'download'
            status_label = 'فقط دانلود'
        rows.append({
            'user': user,
            'user_display': _safe_user_display(user),
            'download_count': row.get('download_count', 0),
            'last_download_at': row.get('last_download_at'),
            'activation': activation,
            'first_launch': first_launch,
            'status_key': status_key,
            'status_label': status_label,
        })
    return rows, total


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
        event_type=FIRST_LAUNCH,
    ).count()
    first_launches_week = ClientAppEvent.objects.filter(
        event_type=FIRST_LAUNCH,
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


def get_windows_download_logs(limit: int = TABLE_FETCH_LIMIT, *, start=None, end=None):
    qs = (
        DownloadLog.objects.select_related(
            'user',
            'order',
            'order__plan',
            'order__product',
        )
        .order_by('-created_at')
    )
    if start is not None and end is not None:
        qs = qs.filter(created_at__date__gte=start, created_at__date__lte=end)
    return qs[:limit]


def get_windows_activations(limit: int = TABLE_FETCH_LIMIT, *, start=None, end=None):
    qs = (
        LicenseActivation.objects.filter(WINDOWS_ACTIVATION_Q)
        .select_related(
            'license',
            'license__order__user',
            'license__plan',
            'license__order__product',
        )
        .order_by('-activated_at')
    )
    if start is not None and end is not None:
        qs = qs.filter(activated_at__date__gte=start, activated_at__date__lte=end)
    return qs[:limit]


def get_windows_first_launches(limit: int = TABLE_FETCH_LIMIT, *, start=None, end=None):
    qs = (
        ClientAppEvent.objects.filter(event_type=FIRST_LAUNCH)
        .select_related(
            'user',
            'license',
            'license__plan',
            'license__order__product',
            'activation',
        )
        .order_by('-created_at')
    )
    if start is not None and end is not None:
        qs = qs.filter(created_at__date__gte=start, created_at__date__lte=end)
    return qs[:limit]
