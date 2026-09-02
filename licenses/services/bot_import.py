"""آپلود خروجی ربات دسکتاپ به workspace کاربر لایسنس."""
from __future__ import annotations

import os
import tempfile

from django.utils import timezone

from licenses.models import License, LicenseActivation
from licenses.services.api import LicenseAPIError, _parse_request
from licenses.services.security import (
    check_rate_limit,
    get_client_ip,
    validate_hardware_fingerprint_format,
    validate_license_key_format,
)
from workspace.constants import SUPPORTED_UPLOAD_EXTENSIONS
from workspace.services.folder_import import is_importable_file, parse_output_relative_path
from workspace.services.importer import import_dataset, import_message


def _request_meta(request) -> dict:
    return getattr(request, 'META', {})


def _resolve_bot_license_user(license_key: str, hardware_fingerprint: str) -> tuple[License, object]:
    if not validate_license_key_format(license_key):
        raise LicenseAPIError('فرمت کلید لایسنس نامعتبر است.', http_status=400)
    if not validate_hardware_fingerprint_format(hardware_fingerprint):
        raise LicenseAPIError('شناسه سخت‌افزاری نامعتبر است.', http_status=400)

    try:
        license_obj = License.objects.select_related('order', 'order__user', 'plan').get(
            license_key=license_key,
        )
    except License.DoesNotExist as exc:
        raise LicenseAPIError('لایسنس یافت نشد.', http_status=404) from exc

    if license_obj.order.status != 'paid':
        raise LicenseAPIError('سفارش لایسنس پرداخت نشده است.', http_status=403)

    if license_obj.status in ('suspended', 'expired'):
        raise LicenseAPIError('لایسنس مسدود یا منقضی شده است.', http_status=403)

    if license_obj.expires_at and license_obj.expires_at < timezone.now():
        raise LicenseAPIError('لایسنس منقضی شده است.', http_status=403)

    activation = LicenseActivation.objects.filter(
        license=license_obj,
        hardware_fingerprint=hardware_fingerprint,
        is_active=True,
    ).first()
    if not activation:
        raise LicenseAPIError('لایسنس روی این سیستم فعال نیست.', http_status=403)

    return license_obj, license_obj.order.user


def import_dataset_for_bot(request) -> dict:
    license_key, hardware_fingerprint = _parse_request(request)
    meta = _request_meta(request)
    client_ip = get_client_ip(meta)

    if not license_key or not hardware_fingerprint:
        raise LicenseAPIError('لایسنس و شناسه سخت‌افزاری الزامی است.', http_status=400)

    check_rate_limit('import', client_ip)

    license_obj, user = _resolve_bot_license_user(license_key, hardware_fingerprint)

    uploaded = request.FILES.get('file')
    if not uploaded:
        raise LicenseAPIError('فایل خروجی الزامی است.', http_status=400)

    relative_path = str(request.data.get('relative_path') or uploaded.name or '').replace('\\', '/')
    if not relative_path:
        relative_path = uploaded.name or 'export.json'

    if not is_importable_file(relative_path):
        raise LicenseAPIError('فرمت فایل برای وارد کردن به پلتفرم پشتیبانی نمی‌شود.', http_status=400)

    ext = os.path.splitext(relative_path)[1].lower()
    if ext not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise LicenseAPIError(f'فرمت {ext} پشتیبانی نمی‌شود.', http_status=400)

    path_info = parse_output_relative_path(relative_path)
    basename = os.path.basename(relative_path)

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        for chunk in uploaded.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        result = import_dataset(
            user=user,
            file_path=tmp_path,
            original_filename=basename,
            path_info=path_info,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    level, msg = import_message(result)
    return {
        'success': True,
        'message': msg,
        'level': level,
        'dataset_id': str(result.dataset.pk),
        'dataset_name': result.dataset.name,
        'added_count': result.added_count,
        'updated_count': result.updated_count,
        'skipped_count': result.skipped_count,
        'suppressed_count': result.suppressed_count,
        'is_update': result.is_update,
        'reactivated': result.reactivated,
        'total_in_file': result.total_in_file,
        'license_key': license_obj.license_key,
    }
