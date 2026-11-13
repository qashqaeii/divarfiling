"""پیش‌نمایش متن پیامک برای پنل — بدون ذخیرهٔ کد OTP خام."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from django.conf import settings

from accounts.models import SmsMessageLog
from accounts.services.admin_user_360.common import sms_purpose_label

_SENSITIVE_ATTR_KEYS = frozenset({
    'code',
    'otp',
    'token',
    'verification-code',
    'verification_code',
    'pin',
})


def _otp_attr_names() -> frozenset[str]:
    raw = getattr(settings, 'FARAZSMS_OTP_ATTR', 'code') or 'code'
    names = {str(raw).strip().lower(), 'code', 'verification-code', 'verification_code'}
    names.discard('')
    return frozenset(names)


def _redact_attributes(attributes: Optional[Mapping[str, Any]]) -> dict[str, str]:
    sensitive = _SENSITIVE_ATTR_KEYS | _otp_attr_names()
    out: dict[str, str] = {}
    for key, value in (attributes or {}).items():
        if value is None:
            continue
        key_s = str(key).strip()
        if not key_s:
            continue
        if key_s.lower() in sensitive:
            out[key_s] = '••••'
        else:
            out[key_s] = str(value)[:120]
    return out


def build_sms_log_preview(
    *,
    purpose: str = '',
    channel: str = '',
    pattern_code: str = '',
    text: str = '',
    attributes: Optional[Mapping[str, Any]] = None,
) -> str:
    body = (text or '').strip()
    if body:
        return body[:500]

    purpose_label = sms_purpose_label(purpose)
    code = (pattern_code or '').strip()
    redacted = _redact_attributes(attributes)

    if channel == SmsMessageLog.Channel.SIMPLE:
        return f'پیامک متنی ({purpose_label})'

    if redacted:
        attr_parts = [f'{k}={v}' for k, v in sorted(redacted.items())]
        prefix = f'پیامک {purpose_label}'
        if code:
            prefix += f' · الگو {code}'
        return f'{prefix} · ' + ' · '.join(attr_parts)[:500]

    if code:
        return f'پیامک الگو ({purpose_label}) · کد الگو: {code}'[:500]

    otp_purposes = frozenset(
        str(p).strip().lower()
        for p in (getattr(settings, 'FARAZSMS_OTP_PURPOSES', ()) or ())
    )
    if (purpose or '').strip().lower() in otp_purposes or (purpose or '').strip().lower() in (
        'login', 'register', 'verify_phone', 'password_reset', 'contract_otp',
    ):
        return f'پیامک {purpose_label} · محتوا از نوع کد یک‌بارمصرف (در لاگ ذخیره نمی‌شود)'

    return f'پیامک {purpose_label}'[:500]


def resolve_sms_log_preview(log: SmsMessageLog) -> str:
    stored = (getattr(log, 'message_preview', None) or '').strip()
    if stored:
        return stored
    if log.error_message and log.status == SmsMessageLog.Status.FAILED:
        return f'ارسال ناموفق: {log.error_message[:400]}'
    return build_sms_log_preview(
        purpose=log.purpose or '',
        channel=log.channel or '',
        pattern_code=log.pattern_code or '',
    )


def sms_log_detail_lines(log: SmsMessageLog) -> list[str]:
    lines = [resolve_sms_log_preview(log)]
    if log.get_channel_display():
        lines.append(f'کانال: {log.get_channel_display()}')
    if (log.pattern_code or '').strip():
        lines.append(f'کد الگو: {log.pattern_code.strip()}')
    if (log.provider or '').strip():
        lines.append(f'ارائه‌دهنده: {log.provider.strip()}')
    if log.status == SmsMessageLog.Status.FAILED and (log.error_message or '').strip():
        lines.append(f'خطا: {log.error_message.strip()[:300]}')
    return lines
