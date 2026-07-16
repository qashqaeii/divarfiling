"""دانلود فایل نصب پس از پرداخت موفق."""
from __future__ import annotations

import os
from typing import BinaryIO

from django.conf import settings
from django.http import FileResponse, Http404

from shop.models import DownloadLog, Order

SETUP_INSTALLER_FILENAME = 'DivarFilingExtractor_Setup_2.13.0.ZIP'


def get_setup_installer_path() -> str:
    return os.path.join(settings.BASE_DIR, 'files', SETUP_INSTALLER_FILENAME)


def resolve_order_download(order: Order) -> tuple[str, str] | None:
    """مسیر و نام فایل نصب برای سفارش — اولویت با فایل setup در django/files."""
    if order.status != 'paid':
        return None

    setup_path = get_setup_installer_path()
    if os.path.isfile(setup_path):
        return setup_path, SETUP_INSTALLER_FILENAME

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
    return response
