"""داده‌های ردیابی اپ اندروید برای پنل مدیریت."""
from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q
from django.utils import timezone

from licenses.models import LicenseActivation
from mobile_api.models import MobileDevice

User = get_user_model()
TABLE_FETCH_LIMIT = 20
ANDROID_FUNNEL_PAGE_SIZE = 25

MOBILE_ACTIVATION_Q = Q(is_active=True) & Q(notes__startswith='device_type=mobile')


def _safe_user_display(user) -> str:
    return user.get_full_name() or user.username or 'کاربر'


def _registrations_between(start, end) -> int:
    return MobileDevice.objects.filter(
        registered_at__date__gte=start,
        registered_at__date__lte=end,
    ).count()


def _install_users_between(start, end) -> int:
    return (
        MobileDevice.objects.filter(
            registered_at__date__gte=start,
            registered_at__date__lte=end,
        )
        .values('user_id')
        .distinct()
        .count()
    )


def _active_users_between(start, end) -> int:
    return (
        MobileDevice.objects.filter(
            last_seen_at__date__gte=start,
            last_seen_at__date__lte=end,
        )
        .values('user_id')
        .distinct()
        .count()
    )


def _active_devices_between(start, end) -> int:
    return MobileDevice.objects.filter(
        is_active=True,
        last_seen_at__date__gte=start,
        last_seen_at__date__lte=end,
    ).count()


def _activations_between(start, end) -> int:
    return LicenseActivation.objects.filter(
        MOBILE_ACTIVATION_Q,
        activated_at__date__gte=start,
        activated_at__date__lte=end,
    ).count()


def get_android_dau(day=None) -> int:
    day = day or timezone.localdate()
    return (
        MobileDevice.objects.filter(last_seen_at__date=day)
        .values('user_id')
        .distinct()
        .count()
    )


def get_android_wau() -> int:
    since = timezone.now() - timedelta(days=7)
    return (
        MobileDevice.objects.filter(last_seen_at__gte=since)
        .values('user_id')
        .distinct()
        .count()
    )


def get_android_mau() -> int:
    since = timezone.now() - timedelta(days=30)
    return (
        MobileDevice.objects.filter(last_seen_at__gte=since)
        .values('user_id')
        .distinct()
        .count()
    )


def build_android_range_summary(start, end) -> Dict[str, int]:
    """شمارش رویدادهای اندروید در بازه."""
    return {
        'registrations': _registrations_between(start, end),
        'install_users': _install_users_between(start, end),
        'active_users': _active_users_between(start, end),
        'active_devices': _active_devices_between(start, end),
        'activations': _activations_between(start, end),
        'dau_today': get_android_dau(),
    }


def build_android_funnel_steps(start, end) -> List[Dict[str, Any]]:
    """Funnel کاربر-محور: ثبت دستگاه → فعال → استفاده."""
    install_user_ids = list(
        MobileDevice.objects.filter(
            registered_at__date__gte=start,
            registered_at__date__lte=end,
        )
        .values('user_id')
        .annotate(last_registered_at=Max('registered_at'))
        .order_by('-last_registered_at')
        .values_list('user_id', flat=True)
    )
    installs = len(install_user_ids)
    if not installs:
        return [
            {'key': 'install', 'label': 'ثبت دستگاه', 'count': 0, 'accent': 'blue'},
            {'key': 'active', 'label': 'دستگاه فعال', 'count': 0, 'accent': 'violet'},
            {'key': 'usage', 'label': 'استفاده', 'count': 0, 'accent': 'emerald'},
        ]

    active_users = (
        MobileDevice.objects.filter(
            user_id__in=install_user_ids,
            is_active=True,
        )
        .values('user_id')
        .distinct()
        .count()
    )
    usage_users = (
        MobileDevice.objects.filter(
            user_id__in=install_user_ids,
            last_seen_at__date__gte=start,
            last_seen_at__date__lte=end,
        )
        .values('user_id')
        .distinct()
        .count()
    )
    return [
        {'key': 'install', 'label': 'ثبت دستگاه', 'count': installs, 'accent': 'blue'},
        {'key': 'active', 'label': 'دستگاه فعال', 'count': active_users, 'accent': 'violet'},
        {'key': 'usage', 'label': 'استفاده', 'count': usage_users, 'accent': 'emerald'},
    ]


def get_android_version_distribution(*, active_only: bool = True, limit: int = 12) -> List[Dict[str, Any]]:
    qs = MobileDevice.objects.all()
    if active_only:
        qs = qs.filter(is_active=True)
    rows = list(
        qs.values('app_version')
        .annotate(
            device_count=Count('id'),
            user_count=Count('user_id', distinct=True),
        )
        .order_by('-device_count')[:limit]
    )
    total = sum(row['device_count'] for row in rows) or 1
    result = []
    for row in rows:
        version = (row['app_version'] or '').strip() or 'نامشخص'
        device_count = row['device_count']
        result.append({
            'version': version,
            'device_count': device_count,
            'user_count': row['user_count'],
            'pct': round((device_count / total) * 100),
        })
    return result


def get_android_user_funnel(
    limit: int = TABLE_FETCH_LIMIT,
    *,
    start=None,
    end=None,
    page: int = 1,
    page_size: int = ANDROID_FUNNEL_PAGE_SIZE,
) -> Tuple[List[Dict[str, Any]], int]:
    """کاربران با ثبت دستگاه + وضعیت فعال و استفاده."""
    qs = MobileDevice.objects.all()
    if start is not None and end is not None:
        qs = qs.filter(registered_at__date__gte=start, registered_at__date__lte=end)

    ranked = (
        qs.values('user_id')
        .annotate(
            device_count=Count('id'),
            active_device_count=Count('id', filter=Q(is_active=True)),
            last_registered_at=Max('registered_at'),
            last_seen_at=Max('last_seen_at'),
            latest_app_version=Max('app_version'),
        )
        .order_by('-last_registered_at')
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
                MOBILE_ACTIVATION_Q,
                license__order__user_id=user_id,
            )
            .select_related('license', 'license__plan')
            .order_by('-activated_at')
            .first()
        )
        last_seen = row.get('last_seen_at')
        used_in_range = False
        if start is not None and end is not None and last_seen is not None:
            seen_date = timezone.localtime(last_seen).date()
            used_in_range = start <= seen_date <= end

        active_count = int(row.get('active_device_count') or 0)
        if used_in_range:
            status_key = 'usage'
            status_label = 'استفاده'
        elif active_count > 0:
            status_key = 'active'
            status_label = 'دستگاه فعال'
        else:
            status_key = 'install'
            status_label = 'فقط ثبت'

        rows.append({
            'user': user,
            'user_display': _safe_user_display(user),
            'device_count': row.get('device_count', 0),
            'active_device_count': active_count,
            'last_registered_at': row.get('last_registered_at'),
            'last_seen_at': last_seen,
            'app_version': (row.get('latest_app_version') or '').strip() or '—',
            'activation': activation,
            'status_key': status_key,
            'status_label': status_label,
        })
    return rows, total


def get_android_app_stats() -> Dict[str, int]:
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    devices_total = MobileDevice.objects.count()
    devices_active = MobileDevice.objects.filter(is_active=True).count()
    users_total = MobileDevice.objects.values('user_id').distinct().count()
    registrations_week = MobileDevice.objects.filter(registered_at__gte=week_ago).count()
    registrations_month = MobileDevice.objects.filter(registered_at__gte=month_ago).count()
    activations_total = LicenseActivation.objects.filter(MOBILE_ACTIVATION_Q).count()
    activations_week = LicenseActivation.objects.filter(
        MOBILE_ACTIVATION_Q,
        activated_at__gte=week_ago,
    ).count()

    return {
        'android_devices_total': devices_total,
        'android_devices_active': devices_active,
        'android_users_total': users_total,
        'android_registrations_week': registrations_week,
        'android_registrations_month': registrations_month,
        'android_activations_total': activations_total,
        'android_activations_week': activations_week,
        'android_dau': get_android_dau(),
        'android_wau': get_android_wau(),
        'android_mau': get_android_mau(),
    }


def get_android_registrations(limit: int = TABLE_FETCH_LIMIT, *, start=None, end=None):
    qs = (
        MobileDevice.objects.select_related(
            'user',
            'license_activation',
            'license_activation__license',
            'license_activation__license__plan',
        )
        .order_by('-registered_at')
    )
    if start is not None and end is not None:
        qs = qs.filter(registered_at__date__gte=start, registered_at__date__lte=end)
    return qs[:limit]


def get_android_recent_usage(limit: int = TABLE_FETCH_LIMIT, *, start=None, end=None):
    qs = (
        MobileDevice.objects.filter(is_active=True)
        .select_related(
            'user',
            'license_activation',
            'license_activation__license',
            'license_activation__license__plan',
        )
        .order_by('-last_seen_at')
    )
    if start is not None and end is not None:
        qs = qs.filter(last_seen_at__date__gte=start, last_seen_at__date__lte=end)
    return qs[:limit]


def get_android_activations(limit: int = TABLE_FETCH_LIMIT, *, start=None, end=None):
    qs = (
        LicenseActivation.objects.filter(MOBILE_ACTIVATION_Q)
        .select_related(
            'license',
            'license__order__user',
            'license__plan',
        )
        .order_by('-activated_at')
    )
    if start is not None and end is not None:
        qs = qs.filter(activated_at__date__gte=start, activated_at__date__lte=end)
    return qs[:limit]


_VERSION_TUPLE_RE = re.compile(r'(\d+)\.(\d+)\.(\d+)')


def parse_app_version_tuple(version: str) -> Optional[Tuple[int, int, int]]:
    """استخراج نسخه semver از رشته app_version."""
    match = _VERSION_TUPLE_RE.search(version or '')
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def is_android_version_outdated(device_version: str, latest_version: str) -> bool:
    """آیا نسخه دستگاه از آخرین نسخه منتشرشده قدیمی‌تر است."""
    latest = parse_app_version_tuple(latest_version)
    if latest is None:
        return False
    device = parse_app_version_tuple(device_version)
    if device is None:
        return True
    return device < latest


def get_latest_android_version_label() -> Tuple[str, int, str]:
    """version_name، build و برچسب نمایشی آخرین APK."""
    from shop.services.app_downloads import android_apk_version_info

    version_name, version_code = android_apk_version_info()
    return version_name, version_code, f'v{version_name} ({version_code})'


def get_android_download_url() -> str:
    from django.conf import settings
    from django.urls import reverse

    site = (getattr(settings, 'SITE_URL', '') or 'https://divarfiling.ir').rstrip('/')
    return f'{site}{reverse("android_app_download")}'


@dataclass
class OutdatedAndroidUser:
    user: Any
    phone: str
    app_version: str
    latest_version: str
    device_model: str
    last_seen_at: Any


def get_outdated_android_users(*, active_only: bool = True) -> List[OutdatedAndroidUser]:
    """کاربرانی که حداقل یک دستگاه فعال با نسخه قدیمی دارند."""
    latest_name, _, latest_label = get_latest_android_version_label()
    qs = MobileDevice.objects.select_related('user')
    if active_only:
        qs = qs.filter(is_active=True)

    grouped: Dict[int, List[MobileDevice]] = defaultdict(list)
    for device in qs.order_by('-last_seen_at'):
        grouped[device.user_id].append(device)

    rows: List[OutdatedAndroidUser] = []
    for devices in grouped.values():
        outdated_devices = [
            d for d in devices
            if is_android_version_outdated(d.app_version, latest_name)
        ]
        if not outdated_devices:
            continue
        primary = outdated_devices[0]
        user = primary.user
        phone = (getattr(user, 'phone', '') or '').strip()
        if not phone:
            continue
        rows.append(OutdatedAndroidUser(
            user=user,
            phone=phone,
            app_version=(primary.app_version or '').strip() or 'نامشخص',
            latest_version=latest_label,
            device_model=(primary.device_model or '').strip() or '—',
            last_seen_at=primary.last_seen_at,
        ))
    return rows


def count_outdated_android_users(*, active_only: bool = True) -> int:
    return len(get_outdated_android_users(active_only=active_only))
