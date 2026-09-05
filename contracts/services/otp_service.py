"""OTP اختصاصی قرارداد.

ContractOTP جدا از accounts.OtpRequest است چون:
- به invitation/access_token و purpose قرارداد متصل است
- TTL/attempts/cooldown در context دعوتنامه مدیریت می‌شود
- فقط mobile_verified می‌دهد؛ identity_verified تلقی نمی‌شود

از accounts.services.otp برای generate/hash OTP استفاده می‌کند.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from accounts.services.otp import OtpError, generate_otp_code, hash_otp_code
from accounts.services.sms import SmsError, send_pattern_sms

CONTRACT_OTP_SMS_PURPOSE = 'contract_otp'
from contracts.constants import VERIFICATION_MISMATCH_MSG
from contracts.models import ContractInvitation, ContractOTP

logger = logging.getLogger(__name__)


class ContractOtpError(Exception):
    def __init__(self, message: str, *, code: str = 'otp_error', retry_after: int = 0):
        self.message = message
        self.code = code
        self.retry_after = retry_after
        super().__init__(message)


def _otp_ttl() -> int:
    return max(60, int(getattr(settings, 'OTP_EXPIRY_SECONDS', 120) or 120))


def _resend_seconds() -> int:
    return max(30, int(getattr(settings, 'OTP_RESEND_SECONDS', 60) or 60))


def _max_attempts() -> int:
    return max(1, int(getattr(settings, 'OTP_MAX_ATTEMPTS', 5) or 5))


def _max_sends_per_hour() -> int:
    return max(1, int(getattr(settings, 'OTP_MAX_SENDS_PER_HOUR', 8) or 8))


def _client_ip(request) -> str:
    if request is None:
        return ''
    forwarded = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    return forwarded or (request.META.get('REMOTE_ADDR') or '')[:64]


def _user_agent(request) -> str:
    if request is None:
        return ''
    return (request.META.get('HTTP_USER_AGENT') or '')[:500]


def _send_contract_otp_sms(phone: str, code: str) -> None:
    """ارسال OTP قرارداد با الگوی تأییدشده پنل پیامکی."""
    attr_name = getattr(settings, 'FARAZSMS_OTP_ATTR', 'code') or 'code'
    send_pattern_sms(
        phone,
        purpose=CONTRACT_OTP_SMS_PURPOSE,
        attributes={attr_name: code},
    )


@transaction.atomic
def request_contract_otp(
    invitation: ContractInvitation,
    phone: str,
    *,
    purpose: str = 'acceptance',
    request=None,
    access_token=None,
) -> ContractOTP:
    normalized = normalize_phone(phone)
    if not is_valid_iran_mobile(normalized):
        raise ContractOtpError('شماره موبایل معتبر نیست.', code='invalid_phone')

    if invitation.is_revoked:
        raise ContractOtpError('لینک دعوت ابطال شده است.', code='revoked')

    inv_mobile = normalize_phone(invitation.mobile)
    if normalized != inv_mobile:
        raise ContractOtpError(VERIFICATION_MISMATCH_MSG, code='phone_mismatch')

    now = timezone.now()
    recent = ContractOTP.objects.filter(
        invitation=invitation, phone=normalized, is_consumed=False,
        expires_at__gt=now,
    ).order_by('-created_at').first()
    if recent and (recent.created_at + timedelta(seconds=_resend_seconds())) > now:
        retry = int((recent.created_at + timedelta(seconds=_resend_seconds()) - now).total_seconds())
        raise ContractOtpError('لطفاً کمی صبر کنید.', code='rate_limited', retry_after=retry)

    hour_ago = now - timedelta(hours=1)
    send_count = ContractOTP.objects.filter(
        invitation=invitation, phone=normalized, created_at__gte=hour_ago,
    ).count()
    if send_count >= _max_sends_per_hour():
        raise ContractOtpError('تعداد درخواست‌ها بیش از حد مجاز است.', code='rate_limited')

    code = generate_otp_code()
    otp = ContractOTP.objects.create(
        invitation=invitation,
        access_token=access_token,
        phone=normalized,
        code_hash=hash_otp_code(code, normalized, f'contract_{purpose}'),
        purpose=purpose,
        expires_at=now + timedelta(seconds=_otp_ttl()),
        max_attempts=_max_attempts(),
        ip_address=_client_ip(request) or None,
        user_agent=_user_agent(request),
    )

    try:
        _send_contract_otp_sms(normalized, code)
    except (SmsError, OtpError) as exc:
        logger.warning('contract OTP SMS failed: %s', exc)
        if settings.DEBUG:
            logger.info('DEBUG contract OTP for %s: %s', normalized, code)
        else:
            raise ContractOtpError('ارسال پیامک ناموفق بود.', code='sms_failed') from exc

    return otp


@transaction.atomic
def verify_contract_otp(invitation: ContractInvitation, phone: str, code: str, *, request=None) -> ContractOTP:
    normalized = normalize_phone(phone)
    now = timezone.now()
    otp = (
        ContractOTP.objects.select_for_update()
        .filter(invitation=invitation, phone=normalized, is_consumed=False)
        .order_by('-created_at')
        .first()
    )
    if not otp:
        raise ContractOtpError('کد تأیید یافت نشد. دوباره درخواست دهید.', code='not_found')
    if otp.expires_at < now:
        raise ContractOtpError('کد تأیید منقضی شده است.', code='expired')
    if otp.attempts >= otp.max_attempts:
        raise ContractOtpError('تعداد تلاش‌ها بیش از حد مجاز است.', code='max_attempts')

    expected = hash_otp_code(code.strip(), normalized, f'contract_{otp.purpose}')
    if not secrets_compare(expected, otp.code_hash):
        otp.attempts += 1
        otp.save(update_fields=['attempts'])
        raise ContractOtpError('کد تأیید نادرست است.', code='invalid_code')

    otp.is_consumed = True
    otp.consumed_at = now
    otp.save(update_fields=['is_consumed', 'consumed_at'])
    return otp


def secrets_compare(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(a, b)


@transaction.atomic
def request_handover_otp(invitation, phone: str, *, request=None):
    from contracts.models import ContractHandoverInvitation
    if not isinstance(invitation, ContractHandoverInvitation):
        raise ContractOtpError('دعوتنامه نامعتبر است.')
    return _request_otp_for_target(
        phone=phone,
        purpose='handover_acceptance',
        request=request,
        handover_invitation=invitation,
        mobile_check=invitation.mobile,
        revoked=invitation.is_revoked,
    )


@transaction.atomic
def verify_handover_otp(invitation, phone: str, code: str, *, request=None):
    normalized = normalize_phone(phone)
    now = timezone.now()
    otp = (
        ContractOTP.objects.select_for_update()
        .filter(handover_invitation=invitation, phone=normalized, is_consumed=False)
        .order_by('-created_at')
        .first()
    )
    return _verify_otp_record(otp, code, normalized, now)


def _request_otp_for_target(*, phone, purpose, request, handover_invitation=None, invitation=None,
                            mobile_check='', revoked=False):
    normalized = normalize_phone(phone)
    if not is_valid_iran_mobile(normalized):
        raise ContractOtpError('شماره موبایل معتبر نیست.', code='invalid_phone')
    if revoked:
        raise ContractOtpError('لینک ابطال شده است.', code='revoked')
    if normalize_phone(mobile_check) != normalized:
        raise ContractOtpError(VERIFICATION_MISMATCH_MSG, code='phone_mismatch')

    now = timezone.now()
    filt = {'handover_invitation': handover_invitation} if handover_invitation else {'invitation': invitation}
    recent = ContractOTP.objects.filter(
        **filt, phone=normalized, is_consumed=False, expires_at__gt=now,
    ).order_by('-created_at').first()
    if recent and (recent.created_at + timedelta(seconds=_resend_seconds())) > now:
        retry = int((recent.created_at + timedelta(seconds=_resend_seconds()) - now).total_seconds())
        raise ContractOtpError('لطفاً کمی صبر کنید.', code='rate_limited', retry_after=retry)

    code = generate_otp_code()
    otp = ContractOTP.objects.create(
        invitation=invitation,
        handover_invitation=handover_invitation,
        phone=normalized,
        code_hash=hash_otp_code(code, normalized, f'contract_{purpose}'),
        purpose=purpose,
        expires_at=now + timedelta(seconds=_otp_ttl()),
        max_attempts=_max_attempts(),
        ip_address=_client_ip(request) or None,
        user_agent=_user_agent(request),
    )
    try:
        _send_contract_otp_sms(normalized, code)
    except (SmsError, OtpError) as exc:
        logger.warning('OTP SMS failed: %s', exc)
        if settings.DEBUG:
            logger.info('DEBUG OTP for %s: %s', normalized, code)
        else:
            raise ContractOtpError('ارسال پیامک ناموفق بود.', code='sms_failed') from exc
    return otp


def _verify_otp_record(otp, code: str, normalized: str, now):
    if not otp:
        raise ContractOtpError('کد تأیید یافت نشد. دوباره درخواست دهید.', code='not_found')
    if otp.expires_at < now:
        raise ContractOtpError('کد تأیید منقضی شده است.', code='expired')
    if otp.attempts >= otp.max_attempts:
        raise ContractOtpError('تعداد تلاش‌ها بیش از حد مجاز است.', code='max_attempts')
    expected = hash_otp_code(code.strip(), normalized, f'contract_{otp.purpose}')
    if not secrets_compare(expected, otp.code_hash):
        otp.attempts += 1
        otp.save(update_fields=['attempts'])
        raise ContractOtpError('کد تأیید نادرست است.', code='invalid_code')
    otp.is_consumed = True
    otp.consumed_at = now
    otp.save(update_fields=['is_consumed', 'consumed_at'])
    return otp
