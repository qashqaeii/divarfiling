"""لایه نازک OTP برای API موبایل — همان سرویس accounts.services.otp."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from django.conf import settings

from accounts.models import User
from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from accounts.services.account_completion import (
    AccountCompletionError,
    create_user_from_verified_phone,
    set_password_for_phone,
)
from accounts.services.otp import (
    OtpChallenge,
    OtpError,
    OtpRateLimitError,
    request_otp,
    verify_otp,
)
from accounts.services.otp_challenge import issue_verified_challenge, read_verified_challenge

PURPOSE_LOGIN = 'login'
PURPOSE_REGISTER = 'register'
PURPOSE_RESET = 'password_reset'
PURPOSE_VERIFY = 'verify_phone'
PUBLIC_PURPOSES = frozenset({PURPOSE_LOGIN, PURPOSE_REGISTER, PURPOSE_RESET})
ALL_PURPOSES = PUBLIC_PURPOSES | {PURPOSE_VERIFY}


class MobileAuthError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = 'AUTH_ERROR',
        status: int = 400,
        retry_after: Optional[int] = None,
    ):
        self.message = message
        self.code = code
        self.status = status
        self.retry_after = retry_after
        super().__init__(message)


def _challenge_payload(challenge: OtpChallenge) -> Dict[str, Any]:
    from django.utils import timezone

    now = timezone.now()
    expires_in = max(0, int((challenge.expires_at - now).total_seconds()))
    resend_in = max(0, int((challenge.resend_available_at - now).total_seconds()))
    data: Dict[str, Any] = {
        'phone': challenge.phone,
        'phone_display': _display_phone(challenge.phone),
        'purpose': challenge.purpose,
        'expires_in': expires_in,
        'resend_in': resend_in,
    }
    if getattr(settings, 'OTP_DEBUG_RETURN_CODE', False) and challenge.debug_code:
        data['debug_code'] = challenge.debug_code
    return data


def _display_phone(phone: str) -> str:
    phone = normalize_phone(phone or '')
    if len(phone) == 11:
        return f'{phone[:4]}***{phone[-2:]}'
    return phone


def _map_otp_error(exc: OtpError) -> MobileAuthError:
    if isinstance(exc, OtpRateLimitError):
        return MobileAuthError(
            exc.message,
            code='OTP_RATE_LIMITED',
            status=429,
            retry_after=getattr(exc, 'retry_after', None),
        )
    code_map = {
        'invalid_phone': ('OTP_INVALID_PHONE', 400),
        'invalid_code_format': ('OTP_INVALID', 400),
        'otp_not_found': ('OTP_EXPIRED', 400),
        'otp_expired': ('OTP_EXPIRED', 400),
        'otp_locked': ('OTP_RATE_LIMITED', 429),
        'otp_mismatch': ('OTP_INVALID', 400),
        'invalid_code': ('OTP_INVALID', 400),
    }
    mapped, status = code_map.get(getattr(exc, 'code', ''), ('OTP_ERROR', 400))
    return MobileAuthError(exc.message, code=mapped, status=status)


def request_public_otp(phone: str, purpose: str, *, request=None) -> Dict[str, Any]:
    purpose = (purpose or '').strip().lower()
    if purpose not in PUBLIC_PURPOSES:
        raise MobileAuthError('نوع درخواست نامعتبر است.', code='VALIDATION_ERROR')
    normalized = normalize_phone(phone or '')
    if not is_valid_iran_mobile(normalized):
        raise MobileAuthError('شماره موبایل معتبر نیست.', code='OTP_INVALID_PHONE')

    if purpose == PURPOSE_LOGIN:
        if not User.objects.filter(phone=normalized).exists():
            raise MobileAuthError(
                'حسابی با این شماره یافت نشد. ابتدا ثبت‌نام کنید.',
                code='USER_NOT_FOUND',
                status=404,
            )
    elif purpose == PURPOSE_REGISTER:
        if User.objects.filter(phone=normalized).exists():
            raise MobileAuthError(
                'این شماره قبلاً ثبت شده — وارد شوید.',
                code='PHONE_TAKEN',
                status=409,
            )
    elif purpose == PURPOSE_RESET:
        if not User.objects.filter(phone=normalized, is_active=True).exists():
            raise MobileAuthError(
                'حسابی با این شماره یافت نشد.',
                code='USER_NOT_FOUND',
                status=404,
            )

    try:
        challenge = request_otp(normalized, purpose, request=request)
    except OtpError as exc:
        raise _map_otp_error(exc) from exc
    return _challenge_payload(challenge)


def resend_public_otp(phone: str, purpose: str, *, request=None) -> Dict[str, Any]:
    return request_public_otp(phone, purpose, request=request)


def verify_login_otp(phone: str, code: str) -> User:
    normalized = normalize_phone(phone or '')
    try:
        verify_otp(normalized, PURPOSE_LOGIN, code)
    except OtpError as exc:
        raise _map_otp_error(exc) from exc
    user = User.objects.filter(phone=normalized).first()
    if not user or not user.is_active:
        raise MobileAuthError(
            'حساب کاربری یافت نشد یا غیرفعال است.',
            code='USER_NOT_FOUND',
            status=404,
        )
    from accounts.services.phone_verification import complete_phone_verification

    complete_phone_verification(user, channel='android_otp_login')
    return user


def verify_step_otp(phone: str, purpose: str, code: str) -> Dict[str, Any]:
    purpose = (purpose or '').strip().lower()
    if purpose not in {PURPOSE_REGISTER, PURPOSE_RESET}:
        raise MobileAuthError('نوع درخواست نامعتبر است.', code='VALIDATION_ERROR')
    normalized = normalize_phone(phone or '')
    try:
        verify_otp(normalized, purpose, code)
    except OtpError as exc:
        raise _map_otp_error(exc) from exc
    if purpose == PURPOSE_RESET:
        if not User.objects.filter(phone=normalized, is_active=True).exists():
            raise MobileAuthError(
                'حساب کاربری یافت نشد یا غیرفعال است.',
                code='USER_NOT_FOUND',
                status=404,
            )
    token = issue_verified_challenge(normalized, purpose)
    return {
        'phone': normalized,
        'phone_display': _display_phone(normalized),
        'purpose': purpose,
        'challenge_token': token,
    }


def complete_register(phone: str, challenge_token: str, password: str, password2: str, *, request=None) -> User:
    _validate_passwords(password, password2)
    try:
        token_phone = read_verified_challenge(challenge_token, PURPOSE_REGISTER)
    except ValueError as exc:
        raise MobileAuthError(str(exc), code='OTP_CHALLENGE_INVALID') from exc
    requested = normalize_phone(phone or '')
    if requested and requested != token_phone:
        raise MobileAuthError('شماره با توکن تأیید هم‌خوان نیست.', code='VALIDATION_ERROR')
    try:
        return create_user_from_verified_phone(token_phone, password, request=request)
    except AccountCompletionError as exc:
        status = 409 if exc.code == 'phone_taken' else 400
        raise MobileAuthError(exc.message, code=exc.code.upper(), status=status) from exc


def complete_password_reset(phone: str, challenge_token: str, password: str, password2: str) -> User:
    _validate_passwords(password, password2)
    try:
        token_phone = read_verified_challenge(challenge_token, PURPOSE_RESET)
    except ValueError as exc:
        raise MobileAuthError(str(exc), code='OTP_CHALLENGE_INVALID') from exc
    requested = normalize_phone(phone or '')
    if requested and requested != token_phone:
        raise MobileAuthError('شماره با توکن تأیید هم‌خوان نیست.', code='VALIDATION_ERROR')
    try:
        return set_password_for_phone(token_phone, password)
    except AccountCompletionError as exc:
        raise MobileAuthError(exc.message, code=exc.code.upper(), status=404) from exc


def request_verify_phone_otp(user, *, request=None) -> Dict[str, Any]:
    phone = normalize_phone(getattr(user, 'phone', '') or '')
    if not is_valid_iran_mobile(phone):
        raise MobileAuthError(
            'شماره موبایل حساب شما معتبر نیست. ابتدا از پروفایل آن را اصلاح کنید.',
            code='OTP_INVALID_PHONE',
        )
    if getattr(user, 'phone_verified', False):
        raise MobileAuthError('شماره موبایل شما قبلاً تأیید شده است.', code='ALREADY_VERIFIED')
    try:
        challenge = request_otp(phone, PURPOSE_VERIFY, request=request)
    except OtpError as exc:
        raise _map_otp_error(exc) from exc
    return _challenge_payload(challenge)


def complete_verify_phone(user, code: str) -> User:
    phone = normalize_phone(getattr(user, 'phone', '') or '')
    if not is_valid_iran_mobile(phone):
        raise MobileAuthError('شماره موبایل حساب شما معتبر نیست.', code='OTP_INVALID_PHONE')
    try:
        verify_otp(phone, PURPOSE_VERIFY, code)
    except OtpError as exc:
        raise _map_otp_error(exc) from exc
    from accounts.services.phone_verification import complete_phone_verification

    complete_phone_verification(user, channel='android_phone_verify')
    return user


def _validate_passwords(password: str, password2: str) -> None:
    password = password or ''
    password2 = password2 or ''
    if len(password) < 8:
        raise MobileAuthError('رمز عبور باید حداقل ۸ کاراکتر باشد.', code='VALIDATION_ERROR')
    if password != password2:
        raise MobileAuthError('رمز عبور و تکرار آن یکسان نیستند.', code='VALIDATION_ERROR')
