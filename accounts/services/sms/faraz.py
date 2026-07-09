"""کلاینت REST فراز اس‌ام‌اس / ایران‌پیامک — مستندات: https://docs.iranpayamak.com/"""
from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

from .base import SmsConfigurationError, SmsResult, SmsSendError

logger = logging.getLogger(__name__)


def _api_key() -> str:
    key = (getattr(settings, 'FARAZSMS_API_KEY', '') or '').strip()
    if not key:
        raise SmsConfigurationError(
            'FARAZSMS_API_KEY در فایل .env تنظیم نشده است.'
        )
    return key


def _line_number() -> str:
    line = (getattr(settings, 'FARAZSMS_LINE_NUMBER', '') or '').strip()
    if not line:
        raise SmsConfigurationError(
            'FARAZSMS_LINE_NUMBER در فایل .env تنظیم نشده است.'
        )
    return line


def _base_url() -> str:
    return (getattr(settings, 'FARAZSMS_BASE_URL', '') or 'https://api.iranpayamak.com').rstrip('/')


def _timeout() -> int:
    return int(getattr(settings, 'FARAZSMS_TIMEOUT', 15) or 15)


def _headers() -> dict[str, str]:
    return {
        'Api-Key': _api_key(),
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }


def _mask_phone(phone: str) -> str:
    if len(phone) < 7:
        return '***'
    return f'{phone[:4]}***{phone[-2:]}'


def _parse_response(payload: Any, http_status: int) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SmsSendError(
            'پاسخ نامعتبر از پنل پیامک دریافت شد.',
            code='sms_invalid_response',
            http_status=http_status,
        )
    return payload


def _ensure_success(payload: dict[str, Any], http_status: int) -> Any:
    status = str(payload.get('status') or '').lower()
    if status == 'success' or http_status in (200, 201):
        if status == 'error':
            message = (
                payload.get('message')
                or payload.get('messages')
                or 'ارسال پیامک توسط پنل رد شد.'
            )
            if isinstance(message, list):
                message = ' '.join(str(m) for m in message)
            raise SmsSendError(
                str(message),
                code='sms_provider_error',
                provider_status=status,
                http_status=http_status,
            )
        return payload.get('data')
    message = payload.get('message') or payload.get('messages') or 'ارسال پیامک ناموفق بود.'
    if isinstance(message, list):
        message = ' '.join(str(m) for m in message)
    raise SmsSendError(
        str(message),
        code='sms_provider_error',
        provider_status=status or None,
        http_status=http_status,
    )


def _extract_message_id(data: Any) -> str:
    if data is None:
        return ''
    if isinstance(data, (int, float)):
        return str(int(data))
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ('id', 'message_id', 'send_request_id', 'uid'):
            if data.get(key) is not None:
                return str(data[key])
    return ''


def _request(method: str, path: str, *, json_body: dict | None = None) -> dict[str, Any]:
    url = f'{_base_url()}{path}'
    try:
        response = requests.request(
            method,
            url,
            headers=_headers(),
            json=json_body,
            timeout=_timeout(),
        )
    except requests.Timeout as exc:
        logger.warning('FarazSMS timeout path=%s', path)
        raise SmsSendError(
            'زمان ارتباط با پنل پیامک به پایان رسید. لطفاً دوباره تلاش کنید.',
            code='sms_timeout',
        ) from exc
    except requests.RequestException as exc:
        logger.warning('FarazSMS connection error path=%s err=%s', path, type(exc).__name__)
        raise SmsSendError(
            'ارتباط با پنل پیامک برقرار نشد.',
            code='sms_unreachable',
        ) from exc

    try:
        payload = response.json() if response.content else {}
    except ValueError:
        payload = {}

    if response.status_code >= 500:
        logger.warning(
            'FarazSMS server error status=%s path=%s',
            response.status_code,
            path,
        )
        raise SmsSendError(
            'سرویس پیامک موقتاً در دسترس نیست.',
            code='sms_unavailable',
            http_status=response.status_code,
        )

    if response.status_code in (401, 403):
        raise SmsSendError(
            'احراز هویت پنل پیامک ناموفق بود. Api-Key را بررسی کنید.',
            code='sms_auth_failed',
            http_status=response.status_code,
        )

    parsed = _parse_response(payload, response.status_code)
    if response.status_code >= 400 and str(parsed.get('status') or '').lower() != 'success':
        message = parsed.get('message') or parsed.get('messages') or 'خطای پنل پیامک.'
        if isinstance(message, list):
            message = ' '.join(str(m) for m in message)
        raise SmsSendError(
            str(message),
            code='sms_provider_error',
            provider_status=str(parsed.get('status') or ''),
            http_status=response.status_code,
        )
    return parsed


def send_pattern(
    *,
    phone: str,
    pattern_code: str,
    attributes: dict[str, str] | None = None,
    line_number: str | None = None,
) -> SmsResult:
    """ارسال پیامک الگو‌محور (مناسب OTP و اعلان‌های مهم)."""
    if not pattern_code:
        raise SmsConfigurationError('کد الگوی پیامک تنظیم نشده است.')

    body = {
        'code': pattern_code,
        'recipient': phone,
        'attributes': attributes or {},
        'line_number': line_number or _line_number(),
        'number_format': 'english',
    }
    logger.info(
        'FarazSMS pattern send phone=%s pattern=%s',
        _mask_phone(phone),
        pattern_code,
    )
    payload = _request('POST', '/ws/v1/sms/pattern', json_body=body)
    data = _ensure_success(payload, 201)
    return SmsResult(
        success=True,
        provider='faraz',
        phone=phone,
        message_id=_extract_message_id(data),
        status='sent',
        raw={'status': payload.get('status')},
    )


def send_simple(
    *,
    phone: str,
    text: str,
    line_number: str | None = None,
) -> SmsResult:
    """ارسال پیامک متنی ساده."""
    if not (text or '').strip():
        raise SmsSendError('متن پیامک خالی است.', code='sms_empty_text')

    body = {
        'text': text,
        'recipients': [phone],
        'line_number': line_number or _line_number(),
        'number_format': 'english',
    }
    logger.info('FarazSMS simple send phone=%s', _mask_phone(phone))
    payload = _request('POST', '/ws/v1/sms/simple', json_body=body)
    data = _ensure_success(payload, 201)
    return SmsResult(
        success=True,
        provider='faraz',
        phone=phone,
        message_id=_extract_message_id(data),
        status='sent',
        raw={'status': payload.get('status')},
    )


def get_balance() -> Any:
    """بررسی موجودی — روش رایگان برای تست Api-Key."""
    payload = _request('GET', '/ws/v1/account/balance')
    return _ensure_success(payload, 200)
