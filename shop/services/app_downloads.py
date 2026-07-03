"""دانلود عمومی اپ اندروید و متادیتای پلتفرم‌ها."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from django.conf import settings
from django.http import FileResponse, Http404

ANDROID_APK_FILENAME = 'divar-filing-v2.4.6-34-release.apk'
ANDROID_APP_VERSION = '2.4.6'
ANDROID_APP_BUILD = 34
ANDROID_PACKAGE_ID = 'ir.divarfiling.mobile'
ANDROID_MIN_ANDROID = '8.0'

WINDOWS_INSTALLER_FILENAME = 'DivarFilingExtractor_Setup_1.0.0.zip'


def _files_dir() -> str:
    return os.path.join(settings.BASE_DIR, 'files')


def android_apk_path() -> str:
    return os.path.join(_files_dir(), ANDROID_APK_FILENAME)


def android_apk_available() -> bool:
    return os.path.isfile(android_apk_path())


def _human_size(num_bytes: int) -> str:
    if num_bytes < 1024 * 1024:
        return f'{max(1, round(num_bytes / 1024))} KB'
    return f'{num_bytes / (1024 * 1024):.1f} MB'


def android_apk_size_label() -> str:
    path = android_apk_path()
    if not os.path.isfile(path):
        return ''
    return _human_size(os.path.getsize(path))


def resolve_windows_download_for_user(user) -> Optional[Dict[str, Any]]:
    if not user.is_authenticated:
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
    return {
        'android': {
            'available': android_apk_available(),
            'version': ANDROID_APP_VERSION,
            'build': ANDROID_APP_BUILD,
            'version_label': f'v{ANDROID_APP_VERSION} ({ANDROID_APP_BUILD})',
            'size_label': android_apk_size_label(),
            'filename': ANDROID_APK_FILENAME,
            'package_id': ANDROID_PACKAGE_ID,
            'min_android': ANDROID_MIN_ANDROID,
        },
        'windows': {
            'filename': WINDOWS_INSTALLER_FILENAME,
            'requires_license': True,
            'min_os': 'Windows 10 / 11',
        },
        'windows_download': resolve_windows_download_for_user(request.user),
    }


def build_android_apk_response() -> FileResponse:
    path = android_apk_path()
    if not os.path.isfile(path):
        raise Http404('فایل اپ اندروید در سرور موجود نیست.')
    file_handle = open(path, 'rb')
    response = FileResponse(
        file_handle,
        as_attachment=True,
        filename=ANDROID_APK_FILENAME,
    )
    response['Content-Type'] = 'application/vnd.android.package-archive'
    return response
