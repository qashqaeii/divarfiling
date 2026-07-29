"""دانلود فایل نصب پس از پرداخت موفق."""
from __future__ import annotations

import os
import re
from typing import BinaryIO

from django.conf import settings
from django.http import FileResponse, Http404

from shop.models import DownloadLog, Order

# نام ترجیحی؛ اگر نباشد، جدیدترین DivarFilingExtractor_Setup_*.zip|exe از files/ انتخاب می‌شود
SETUP_INSTALLER_FILENAME = 'DivarFilingExtractor_Setup_2.15.0.zip'
_SETUP_NAME_RE = re.compile(
    r'^DivarFilingExtractor_Setup_(\d+)\.(\d+)\.(\d+)\.(zip|exe)$',
    re.IGNORECASE,
)


def _files_dir() -> str:
    return os.path.join(settings.BASE_DIR, 'files')


def _version_key(filename: str) -> tuple[int, int, int, int]:
    match = _SETUP_NAME_RE.match(filename)
    if not match:
        return (0, 0, 0, 0)
    major, minor, patch, ext = match.groups()
    # zip را به exe ترجیح بده اگر نسخه یکسان باشد
    return (int(major), int(minor), int(patch), 1 if ext.lower() == 'zip' else 0)


def get_setup_installer_path() -> str:
    """مسیر فایل نصب ویندوز در django/files — آخرین نسخه موجود."""
    files_dir = _files_dir()
    preferred = os.path.join(files_dir, SETUP_INSTALLER_FILENAME)
    if os.path.isfile(preferred):
        return preferred

    # تطبیق بدون حساسیت به حروف (Linux: .zip vs .ZIP)
    if os.path.isdir(files_dir):
        preferred_lower = SETUP_INSTALLER_FILENAME.lower()
        for name in os.listdir(files_dir):
            if name.lower() == preferred_lower:
                path = os.path.join(files_dir, name)
                if os.path.isfile(path):
                    return path

        candidates: list[str] = []
        for name in os.listdir(files_dir):
            if _SETUP_NAME_RE.match(name):
                path = os.path.join(files_dir, name)
                if os.path.isfile(path) and os.path.getsize(path) >= 1024:
                    candidates.append(path)
        if candidates:
            candidates.sort(
                key=lambda p: (_version_key(os.path.basename(p)), os.path.getmtime(p)),
                reverse=True,
            )
            return candidates[0]

    return preferred


def resolve_order_download(order: Order) -> tuple[str, str] | None:
    """مسیر و نام فایل نصب برای سفارش — اولویت با فایل setup در django/files."""
    if order.status != 'paid':
        return None

    setup_path = get_setup_installer_path()
    if os.path.isfile(setup_path):
        return setup_path, os.path.basename(setup_path)

    product = order.product
    if product.download_file and product.download_file.name:
        filename = os.path.basename(product.download_file.name) or SETUP_INSTALLER_FILENAME
        return product.download_file.path, filename

    return None


def order_can_download(order: Order) -> bool:
    return resolve_order_download(order) is not None


def get_order_download_filename(order: Order) -> str:
    resolved = resolve_order_download(order)
    if not resolved:
        return ''
    return resolved[1]


def log_download(request, order: Order) -> None:
    DownloadLog.objects.create(
        user=request.user,
        order=order,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
    )


def build_download_response(order: Order) -> FileResponse:
    resolved = resolve_order_download(order)
    if not resolved:
        raise Http404('فایل دانلود برای این سفارش موجود نیست.')

    file_path, filename = resolved
    file_handle: BinaryIO = open(file_path, 'rb')
    response = FileResponse(
        file_handle,
        as_attachment=True,
        filename=filename,
    )
    response['Content-Type'] = 'application/zip'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response
