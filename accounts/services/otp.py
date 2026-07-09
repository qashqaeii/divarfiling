"""سرویس OTP امن — هش کد، انقضا، محدودیت ارسال/تلاش، مصرف یک‌باره."""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from accounts.services.sms import SmsError, send_pattern_sms
from accounts.services.sms.base import SmsResult

logger = logging.getLogger(__name__)


class OtpError(Exception):
    """خطای قابل نمایش به کاربر در جریان OTP."""

    def __init__(self, message: str, *, code: str = 'otp_error'):
        self.message = message
        self.code = code
        super().__init__(message)


class OtpRateLimitError(OtpError):
    def __init__(self, message: str, *, retry_after: int = 0):
        self.retry_after = retry_after
        super().__init__(message, code='otp_rate_limited')


@dataclass(frozen=True)
class OtpChallenge:
    phone: str
    purpose: str
    expires_at: timezone.datetime
    resend_available_at: timezone.datetime
    debug_code: str | None = None  # فقط در حالت console/DEBUG برای تست


def _otp_length() -> int:
    return max(4, min(8, int(getattr(settings, 'OTP_LENGTH', 6) or 6)))


def _otp_ttl() -> int:
    return max(60, int(getattr(settings, 'OTP_EXPIRY_SECONDS', 120) or 120))


def _resend_seconds() -> int:
    return max(0, int(getattr(settings, 'OTP_RESEND_SECONDS', 60) or 0))


def _max_attempts() -> int:
    return max(1, int(getattr(settings, 'OTP_MAX_ATTEMPTS', 5) or 5))


def _max_sends_per_hour() -> int:
    return max(1, int(getattr(settings, 'OTP_MAX_SENDS_PER_HOUR', 5) or 5))


def _pepper() -> str:
    return (
        getattr(settings, 'OTP_PEPPER', '')
        or getattr(settings, 'SECRET_KEY', '')
        or 'otp-pepper'
    )


def hash_otp_code(code: str, phone: str, purpose: str) -> str:
    """هش HMAC-SHA256 کد OTP — کد خام ذخیره نمی‌شود."""
    material = f'{normalize_phone(phone)}|{purpose}|{code}'.encode()
    return hmac.new(_pepper().encode(), material, hashlib.sha256).hexdigest()


def generate_otp_code() -> str:
    length = _otp_length()
    # secrets برای جلوگیری از پیش‌بینی‌پذیری
    upper = 10 ** length
    return str(secrets.randbelow(upper)).zfill(length)


def _client_ip(request) -> str:
    if request is None:
        return ''
    forwarded = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    return forwarded or (request.META.get('REMOTE_ADDR') or '')[:64]


def _user_agent(request) -> str:
    if request is None:
        return ''
    return (request.META.get('HTTP_USER_AGENT') or '')[:500]


def _mask_phone(phone: str) -> str:
    if len(phone) < 7:
        return '***'
    return f'{phone[:4]}***{phone[-2:]}'


def request_otp(
    phone: str,
    purpose: str,
    *,
    request=None,
    force_new: bool = True,
) -> OtpChallenge:
    """
    صدور و ارسال OTP.
    purpose: login | register | verify_phone | ...
    """
    from accounts.models import OtpRequest, SmsMessageLog

    normalized = normalize_phone(phone)
    if not is_valid_iran_mobile(normalized):
        raise OtpError('شماره موبایل معتبر نیست.', code='invalid_phone')

    purpose = (purpose or '').strip().lower()
    if purpose not in {c[0] for c in OtpRequest.Purpose.choices}:
        raise OtpError('نوع درخواست نامعتبر است.', code='invalid_purpose')

    now = timezone.now()
    hour_ago = now - timedelta(hours=1)
    recent_sends = OtpRequest.objects.filter(
        phone=normalized,
        purpose=purpose,
        created_at__gte=hour_ago,
    ).count()
    if recent_sends >= _max_sends_per_hour():
        raise OtpRateLimitError(
            'تعداد درخواست کد برای این شماره بیش از حد مجاز است. کمی بعد تلاش کنید.',
            retry_after=3600,
        )

    latest = (
        OtpRequest.objects.filter(phone=normalized, purpose=purpose, is_consumed=False)
        .order_by('-created_at')
        .first()
    )
    if latest and latest.created_at + timedelta(seconds=_resend_seconds()) > now:
        wait = int(
            (latest.created_at + timedelta(seconds=_resend_seconds()) - now).total_seconds()
        )
        raise OtpRateLimitError(
            f'لطفاً {wait} ثانیه دیگر برای ارسال مجدد صبر کنید.',
            retry_after=max(wait, 1),
        )

    code = generate_otp_code()
    code_hash = hash_otp_code(code, normalized, purpose)
    expires_at = now + timedelta(seconds=_otp_ttl())

    with transaction.atomic():
        # باطل کردن چالش‌های قبلی مصرف‌نشده
        OtpRequest.objects.filter(
            phone=normalized,
            purpose=purpose,
            is_consumed=False,
        ).update(is_consumed=True, consumed_at=now)

        otp = OtpRequest.objects.create(
            phone=normalized,
            purpose=purpose,
            code_hash=code_hash,
            expires_at=expires_at,
            max_attempts=_max_attempts(),
            ip_address=_client_ip(request) or None,
            user_agent=_user_agent(request),
        )

        sms_log = SmsMessageLog.objects.create(
            phone=normalized,
            purpose=purpose,
            channel=SmsMessageLog.Channel.PATTERN,
            provider=getattr(settings, 'SMS_PROVIDER', 'console'),
            pattern_code=(getattr(settings, 'FARAZSMS_PATTERNS', {}) or {}).get(purpose, ''),
            status=SmsMessageLog.Status.PENDING,
            otp_request=otp,
        )

    attr_name = getattr(settings, 'FARAZSMS_OTP_ATTR', 'code') or 'code'
    try:
        result: SmsResult = send_pattern_sms(
            normalized,
            purpose=purpose,
            attributes={attr_name: code},
        )
        sms_log.mark_sent(
            provider=result.provider,
            message_id=result.message_id,
            status=SmsMessageLog.Status.FAKE if result.is_fake else SmsMessageLog.Status.SENT,
        )
    except SmsError as exc:
        sms_log.mark_failed(str(exc))
        logger.warning(
            'OTP SMS failed phone=%s purpose=%s code=%s',
            _mask_phone(normalized),
            purpose,
            exc.code,
        )
        raise OtpError(
            'ارسال پیامک ناموفق بود. لطفاً کمی بعد دوباره تلاش کنید.',
            code=exc.code,
        ) from exc

    logger.info(
        'OTP issued phone=%s purpose=%s expires_in=%ss',
        _mask_phone(normalized),
        purpose,
        _otp_ttl(),
    )

    debug_code = None
    provider = (getattr(settings, 'SMS_PROVIDER', 'console') or '').lower()
    if provider in ('console', 'fake', 'dev', 'test') or getattr(settings, 'OTP_DEBUG_RETURN_CODE', False):
        debug_code = code

    return OtpChallenge(
        phone=normalized,
        purpose=purpose,
        expires_at=expires_at,
        resend_available_at=now + timedelta(seconds=_resend_seconds()),
        debug_code=debug_code,
    )


def verify_otp(phone: str, purpose: str, code: str) -> bool:
    """
    تأیید OTP. در صورت موفقیت True و کد مصرف می‌شود.
    در صورت شکست OtpError پرتاب می‌کند.
    """
    from accounts.models import OtpRequest

    normalized = normalize_phone(phone)
    purpose = (purpose or '').strip().lower()
    raw_code = (code or '').strip().translate(
        str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
    )
    if not raw_code.isdigit() or len(raw_code) != _otp_length():
        raise OtpError('کد تأیید نامعتبر است.', code='invalid_code_format')

    now = timezone.now()
    otp = (
        OtpRequest.objects.filter(
            phone=normalized,
            purpose=purpose,
            is_consumed=False,
        )
        .order_by('-created_at')
        .first()
    )
    if otp is None:
        raise OtpError('کد فعالی یافت نشد. دوباره درخواست دهید.', code='otp_not_found')

    if otp.expires_at <= now:
        otp.is_consumed = True
        otp.consumed_at = now
        otp.save(update_fields=['is_consumed', 'consumed_at'])
        raise OtpError('کد منقضی شده است. کد جدید درخواست کنید.', code='otp_expired')

    if otp.attempts >= otp.max_attempts:
        otp.is_consumed = True
        otp.consumed_at = now
        otp.save(update_fields=['is_consumed', 'consumed_at'])
        raise OtpError(
            'تعداد تلاش‌ها بیش از حد مجاز است. کد جدید درخواست کنید.',
            code='otp_locked',
        )

    expected = hash_otp_code(raw_code, normalized, purpose)
    otp.attempts += 1
    if not hmac.compare_digest(expected, otp.code_hash):
        otp.save(update_fields=['attempts'])
        remaining = max(0, otp.max_attempts - otp.attempts)
        if remaining <= 0:
            otp.is_consumed = True
            otp.consumed_at = now
            otp.save(update_fields=['is_consumed', 'consumed_at'])
            raise OtpError(
                'تعداد تلاش‌ها بیش از حد مجاز است. کد جدید درخواست کنید.',
                code='otp_locked',
            )
        raise OtpError(
            f'کد نادرست است. {remaining} تلاش باقی مانده.',
            code='otp_mismatch',
        )

    otp.is_consumed = True
    otp.consumed_at = now
    otp.save(update_fields=['attempts', 'is_consumed', 'consumed_at'])
    logger.info('OTP verified phone=%s purpose=%s', _mask_phone(normalized), purpose)
    return True
