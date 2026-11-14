"""پیش‌نمایش متن پیامک برای پنل — بدون ذخیرهٔ کد OTP خام."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from django.conf import settings

from accounts.models import SmsMessageLog
from accounts.services.admin_user_360.common import sms_purpose_label

_GENERIC_SMS_PREVIEW_PREFIXES = (
    'پیامک متنی (',
    'پیامک الگو (',
)

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


def _is_generic_sms_preview(text: str) -> bool:
    t = (text or '').strip()
    if not t:
        return True
    if any(t.startswith(prefix) for prefix in _GENERIC_SMS_PREVIEW_PREFIXES):
        return True
    if 'کد یک‌بارمصرف' in t and t.startswith('پیامک '):
        return True
    return False


def _message_from_campaign_recipient(log: SmsMessageLog) -> str:
    from accounts.models import MarketingCampaignRecipient

    recipient = (
        MarketingCampaignRecipient.objects.filter(sms_log_id=log.pk)
        .select_related('campaign')
        .first()
    )
    if not recipient:
        return ''
    template = (getattr(recipient.campaign, 'message_template', None) or '').strip()
    ctx = dict(recipient.context_json or {})
    if template:
        from accounts.services.admin_marketing import render_message

        try:
            return (render_message(template, ctx) or '').strip()[:500]
        except Exception:
            pass
    for key in ('rendered_message', 'message', 'body', 'text', 'sms_body'):
        val = (ctx.get(key) or '').strip()
        if val:
            return val[:500]
    return ''


def resolve_sms_message_body(log: SmsMessageLog) -> str:
    """متن واقعی پیامک برای نمایش در پرونده — در صورت امکان از لاگ یا کمپین."""
    stored = (getattr(log, 'message_preview', None) or '').strip()
    if stored and not _is_generic_sms_preview(stored):
        return stored[:500]
    from_campaign = _message_from_campaign_recipient(log)
    if from_campaign:
        return from_campaign
    return ''


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
        for key in ('message', 'Message', 'body', 'text'):
            msg = (redacted.get(key) or '').strip()
            if msg and msg != '••••':
                return msg[:500]
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
    body = resolve_sms_message_body(log)
    if body:
        return body
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
    lines: list[str] = []
    body = resolve_sms_message_body(log)
    if not body:
        lines.append(resolve_sms_log_preview(log))
    if log.get_channel_display():
        lines.append(f'کانال: {log.get_channel_display()}')
    if (log.pattern_code or '').strip():
        lines.append(f'کد الگو: {log.pattern_code.strip()}')
    if (log.provider or '').strip():
        lines.append(f'ارائه‌دهنده: {log.provider.strip()}')
    if log.status == SmsMessageLog.Status.FAILED and (log.error_message or '').strip():
        lines.append(f'خطا: {log.error_message.strip()[:300]}')
    return lines
