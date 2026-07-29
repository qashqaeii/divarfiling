"""دانلود عمومی اپ اندروید و متادیتای پلتفرم‌ها / آپدیت داخلی."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import reverse

ANDROID_APK_FILENAME = 'divar-filing-v2.5.3-38-release.apk'
ANDROID_APP_VERSION = '2.5.3'
ANDROID_APP_BUILD = 38
ANDROID_PACKAGE_ID = 'ir.divarfiling.mobile'
ANDROID_MIN_ANDROID = '8.0'
# اگر کاربر نسخهٔ قدیمی‌تر از این داشته باشد، آپدیت اجباری است
ANDROID_MIN_SUPPORTED_BUILD = 30
ANDROID_FORCE_UPDATE = False
ANDROID_RELEASE_NOTES = (
    'تیم آژانس داخل اپ، هوش مصنوعی کاربردی، فیلتر حرفه‌ای فایلینگ، '
    'تقویم و یادآور، تیکت پشتیبانی کامل، ویرایش مخاطب/آگهی و ظاهر یکدست‌تر.'
)
# در صورت تنظیم، کلاینت صحت فایل را بعد از دانلود بررسی می‌کند
ANDROID_APK_SHA256 = ''
WINDOWS_APP_VERSION = '2.15.0'
WINDOWS_INSTALLER_FILENAME = 'DivarFilingExtractor_Setup_2.15.0.zip'


def _files_dir() -> str:
    return os.path.join(settings.BASE_DIR, 'files')


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
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


def android_apk_filename_resolved() -> str:
    path = android_apk_path()
    return os.path.basename(path) if os.path.isfile(path) else ANDROID_APK_FILENAME


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


def build_app_download_context(request) -> Dict[str, Any]:
    user = getattr(request, 'user', None)
    return {
        'android': {
            'available': android_apk_available(),
            'version': ANDROID_APP_VERSION,
            'build': ANDROID_APP_BUILD,
            'version_label': f'v{ANDROID_APP_VERSION} ({ANDROID_APP_BUILD})',
            'size_label': android_apk_size_label(),
            'filename': ANDROID_APK_FILENAME if not android_apk_available() else android_apk_filename_resolved(),
            'package_id': ANDROID_PACKAGE_ID,
            'min_android': ANDROID_MIN_ANDROID,
        },
        'windows': {
            'filename': WINDOWS_INSTALLER_FILENAME,
            'version': WINDOWS_APP_VERSION,
            'version_label': f'v{WINDOWS_APP_VERSION}',
            'requires_license': True,
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
    version_code = int(ANDROID_APP_BUILD)
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
        'version_name': ANDROID_APP_VERSION,
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
        raise Http404('فایل اپ اندروید در سرور موجود نیست.')
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
        return response
    except Exception:
        file_handle.close()
        raise
