"""دانلود عمومی اپ اندروید و متادیتای پلتفرم‌ها / آپدیت داخلی."""
from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import reverse

from shop.services.downloads import (
    public_setup_installer_filename,
    setup_installer_available,
)

# مقادیر پیش‌فرض وقتی فایل APK روی سرور نیست یا نام فایل قابل parse نیست
ANDROID_APK_FILENAME = 'divar-filing-v2.6.3-43-direct-release.apk'
ANDROID_APP_VERSION = '2.6.3'
ANDROID_APP_BUILD = 43
ANDROID_PACKAGE_ID = 'ir.divarfiling.mobile'
ANDROID_MIN_ANDROID = '8.0'
# اگر کاربر نسخهٔ قدیمی‌تر از این داشته باشد، آپدیت اجباری است
ANDROID_MIN_SUPPORTED_BUILD = 30
ANDROID_FORCE_UPDATE = False
ANDROID_RELEASE_NOTES = (
    'رفع خطای محاسبه امکانات اطراف، بهبود معاملات و فایل‌های شخصی، '
    'و پایداری بیشتر صفحهٔ معاملات.'
)
# در صورت تنظیم، کلاینت صحت فایل را بعد از دانلود بررسی می‌کند
ANDROID_APK_SHA256 = ''
WINDOWS_APP_VERSION = '2.15.0'
WINDOWS_INSTALLER_FILENAME = 'DivarFilingExtractor_Setup_2.15.0.zip'

_APK_VERSION_RE = re.compile(
    r'divar-filing-v(?P<version>\d+\.\d+\.\d+)-(?P<build>\d+)',
    re.IGNORECASE,
)


def _files_dir() -> str:
    return os.path.join(settings.BASE_DIR, 'files')


def parse_apk_version_from_filename(filename: str) -> Optional[Tuple[str, int]]:
    """استخراج version_name و version_code از نام فایل APK."""
    match = _APK_VERSION_RE.search(filename or '')
    if not match:
        return None
    try:
        build = int(match.group('build'))
    except (TypeError, ValueError):
        return None
    version = match.group('version')
    if not version:
        return None
    return version, build


def _apk_build_sort_key(path: str) -> Tuple[int, float]:
    filename = os.path.basename(path)
    parsed = parse_apk_version_from_filename(filename)
    build = parsed[1] if parsed else 0
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0.0
    return build, mtime


def android_apk_path() -> str:
    preferred = os.path.join(_files_dir(), ANDROID_APK_FILENAME)
    if os.path.isfile(preferred):
        return preferred
    files_dir = _files_dir()
    if not os.path.isdir(files_dir):
        return preferred
    candidates = [
        os.path.join(files_dir, name)
        for name in os.listdir(files_dir)
        if name.lower().startswith('divar-filing-') and name.lower().endswith('.apk')
    ]
    if not candidates:
        return preferred
    candidates.sort(key=_apk_build_sort_key, reverse=True)
    return candidates[0]


def android_apk_filename_resolved() -> str:
    path = android_apk_path()
    return os.path.basename(path) if os.path.isfile(path) else ANDROID_APK_FILENAME


def android_apk_version_info() -> Tuple[str, int]:
    """version_name و version_code — اول از نام فایل APK، سپس از ثابت‌ها."""
    filename = android_apk_filename_resolved()
    parsed = parse_apk_version_from_filename(filename)
    if parsed:
        return parsed[0], parsed[1]
    return ANDROID_APP_VERSION, int(ANDROID_APP_BUILD)


def android_apk_available() -> bool:
    return os.path.isfile(android_apk_path())


def _human_size(num_bytes: int) -> str:
    if num_bytes < 1024 * 1024:
        return f'{max(1, round(num_bytes / 1024))} KB'
    return f'{num_bytes / (1024 * 1024):.1f} MB'


def android_apk_size_bytes() -> int:
    path = android_apk_path()
    if not os.path.isfile(path):
        return 0
    try:
        return int(os.path.getsize(path))
    except OSError:
        return 0


def android_apk_size_label() -> str:
    size = android_apk_size_bytes()
    return _human_size(size) if size > 0 else ''


def android_apk_sha256() -> str:
    """هش از ثابت پیکربندی؛ برای جلوگیری از هش‌کردن سنگین در هر درخواست."""
    return (ANDROID_APK_SHA256 or '').strip().lower()


def absolute_android_apk_url(request=None) -> str:
    path = reverse('android_app_download')
    if request is not None:
        try:
            return request.build_absolute_uri(path)
        except Exception:
            pass
    site = getattr(settings, 'SITE_URL', 'https://divarfiling.ir').rstrip('/')
    return f'{site}{path}'


def resolve_windows_download_for_user(user) -> Optional[Dict[str, Any]]:
    if user is None or not getattr(user, 'is_authenticated', False):
        return None
    from shop.models import Order
    from shop.services.downloads import get_order_download_filename, order_can_download
    from workspace.services.access import _user_bot_license

    order = None
    lic = _user_bot_license(user)
    if lic is not None and lic.order_id:
        order = lic.order
    if order is None:
        order = (
            Order.objects.filter(user=user, status='paid')
            .select_related('product')
            .order_by('-paid_at', '-created_at')
            .first()
        )
    if not order or not order_can_download(order):
        return None
    return {
        'order_id': str(order.pk),
        'filename': get_order_download_filename(order),
    }


def _windows_version_from_filename(filename: str) -> str:
    match = re.match(
        r'^DivarFilingExtractor_Setup_(\d+)\.(\d+)\.(\d+)\.',
        filename or '',
        re.IGNORECASE,
    )
    if match:
        return f'{match.group(1)}.{match.group(2)}.{match.group(3)}'
    return WINDOWS_APP_VERSION


def windows_setup_version_info() -> Tuple[str, str]:
    """version و version_label برای نصب‌کننده ویندوز روی سرور."""
    if setup_installer_available():
        filename = public_setup_installer_filename()
        version = _windows_version_from_filename(filename)
        return version, f'v{version}'
    return WINDOWS_APP_VERSION, f'v{WINDOWS_APP_VERSION}'


def build_app_download_context(request) -> Dict[str, Any]:
    user = getattr(request, 'user', None)
    version_name, version_code = android_apk_version_info()
    win_version, win_version_label = windows_setup_version_info()
    win_available = setup_installer_available()
    win_filename = public_setup_installer_filename() if win_available else WINDOWS_INSTALLER_FILENAME
    return {
        'android': {
            'available': android_apk_available(),
            'version': version_name,
            'build': version_code,
            'version_label': f'v{version_name} ({version_code})',
            'size_label': android_apk_size_label(),
            'filename': ANDROID_APK_FILENAME if not android_apk_available() else android_apk_filename_resolved(),
            'package_id': ANDROID_PACKAGE_ID,
            'min_android': ANDROID_MIN_ANDROID,
        },
        'windows': {
            'available': win_available,
            'filename': win_filename,
            'version': win_version,
            'version_label': win_version_label,
            'requires_license_for_extraction': True,
            'min_os': 'Windows 10 / 11',
        },
        'windows_download': resolve_windows_download_for_user(user),
    }


def build_android_update_payload(
    *,
    request=None,
    current_build: Optional[int] = None,
) -> Dict[str, Any]:
    """متادیتای نسخه برای آپدیت داخل اپ اندروید."""
    available = android_apk_available()
    version_name, version_code = android_apk_version_info()
    min_supported = int(ANDROID_MIN_SUPPORTED_BUILD)
    force = bool(ANDROID_FORCE_UPDATE)
    update_available = False
    below_min = False
    if current_build is not None:
        try:
            current = int(current_build)
        except (TypeError, ValueError):
            current = 0
        update_available = version_code > current and available
        below_min = current < min_supported
        if below_min and available:
            force = True
            update_available = True

    return {
        'package_id': ANDROID_PACKAGE_ID,
        'version_name': version_name,
        'version_code': version_code,
        'min_supported_version_code': min_supported,
        'force_update': force,
        'available': available,
        'update_available': update_available,
        'apk_url': absolute_android_apk_url(request),
        'apk_filename': android_apk_filename_resolved() if available else ANDROID_APK_FILENAME,
        'apk_size_bytes': android_apk_size_bytes() if available else 0,
        'apk_size_label': android_apk_size_label() if available else '',
        'apk_sha256': android_apk_sha256() if available else '',
        'release_notes': ANDROID_RELEASE_NOTES,
        'min_android': ANDROID_MIN_ANDROID,
        'store_url': 'https://cafebazaar.ir/app/ir.divarfiling.mobile',
        'website_url': absolute_android_apk_url(request),
    }


def build_android_apk_response() -> FileResponse:
    path = android_apk_path()
    if not os.path.isfile(path):
        raise Http404('فайل اپ اندروید در سرور موجود نیست.')
    try:
        file_handle = open(path, 'rb')
    except OSError as exc:
        raise Http404('فایل اپ اندروید در سرور موجود نیست.') from exc
    try:
        response = FileResponse(
            file_handle,
            as_attachment=True,
            filename=os.path.basename(path),
        )
        response['Content-Type'] = 'application/vnd.android.package-archive'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    except Exception:
        file_handle.close()
        raise
