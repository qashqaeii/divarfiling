"""بک‌اند جعلی/کنسول برای توسعه و تست بدون ارسال واقعی."""
from __future__ import annotations

import logging
import sys
import uuid
from typing import Any

from .base import SmsResult

logger = logging.getLogger(__name__)


def _mask_phone(phone: str) -> str:
    if len(phone) < 7:
        return '***'
    return f'{phone[:4]}***{phone[-2:]}'


def _safe_print(message: str) -> None:
    """چاپ امن روی ویندوز (cp1252) بدون شکست روی متن فارسی."""
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
        sys.stdout.buffer.write((message + '\n').encode(encoding, errors='replace'))
        sys.stdout.flush()


def send_pattern(
    *,
    phone: str,
    pattern_code: str,
    attributes: dict[str, str] | None = None,
    line_number: str | None = None,
) -> SmsResult:
    attrs = attributes or {}
    # کد خام فقط در stdout برای توسعه‌دهنده — در لاگر سیستم ثبت نمی‌شود
    _safe_print(
        f'[SMS:console] pattern={pattern_code} phone={phone} '
        f'line={line_number or "-"} attributes={attrs}'
    )
    logger.info(
        'Console SMS pattern phone=%s pattern=%s attrs_keys=%s',
        _mask_phone(phone),
        pattern_code,
        sorted(attrs.keys()),
    )
    return SmsResult(
        success=True,
        provider='console',
        phone=phone,
        message_id=f'console-{uuid.uuid4().hex[:12]}',
        status='fake',
        raw={'pattern_code': pattern_code, 'attribute_keys': list(attrs.keys())},
    )


def send_simple(
    *,
    phone: str,
    text: str,
    line_number: str | None = None,
) -> SmsResult:
    _safe_print(
        f'[SMS:console] simple phone={phone} line={line_number or "-"} text={text}'
    )
    logger.info('Console SMS simple phone=%s', _mask_phone(phone))
    return SmsResult(
        success=True,
        provider='console',
        phone=phone,
        message_id=f'console-{uuid.uuid4().hex[:12]}',
        status='fake',
        raw={},
    )


def get_balance() -> Any:
    return {'balance': 0, 'provider': 'console'}
