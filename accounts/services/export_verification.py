"""تأیید هویت دو مرحله‌ای (رمز + OTP) پیش از خروجی داده‌های حساس."""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.http import JsonResponse
from django.utils import timezone

from accounts.services.otp import OtpChallenge, OtpError, OtpRateLimitError, request_otp, verify_otp

logger = logging.getLogger(__name__)

EXPORT_OTP_PURPOSE = 'login'
_SALT_PASSWORD = 'export-password-challenge-v1'
_SALT_TOKEN = 'export-access-token-v1'
_SESSION_KEY = 'export_verified_until'
_PASSWORD_CHALLENGE_MAX_AGE = 600  # ۱۰ دقیقه برای وارد کردن OTP


class ExportVerificationError(Exception):
    def __init__(self, message: str, *, code: str = 'export_verification_error', retry_after: int | None = None):
        self.message = message
        self.code = code
        self.retry_after = retry_after
        super().__init__(message)


def _password_signer() -> TimestampSigner:
    return TimestampSigner(salt=_SALT_PASSWORD)


def _token_signer() -> TimestampSigner:
    return TimestampSigner(salt=_SALT_TOKEN)


def _token_max_age() -> int:
    return max(60, int(getattr(settings, 'EXPORT_VERIFICATION_TOKEN_MAX_AGE', 300) or 300))


def _session_max_age() -> int:
    return _token_max_age()


def _mask_phone(phone: str) -> str:
    phone = (phone or '').strip()
    if len(phone) >= 7:
        return f'{phone[:4]}***{phone[-2:]}'
    return '***'


def verify_password_for_export(user, password: str) -> str:
    """رمز ورود را بررسی و توکن چالش رمز برمی‌گرداند."""
    if not user or not getattr(user, 'is_authenticated', False):
        raise ExportVerificationError('ورود به حساب الزامی است.', code='auth_required')
    raw = (password or '').strip()
    if not raw:
        raise ExportVerificationError('رمز عبور را وارد کنید.', code='password_required')
    if not user.check_password(raw):
        raise ExportVerificationError('رمز عبور نادرست است.', code='invalid_password')
    return _password_signer().sign(str(user.pk))


def _read_password_challenge(token: str, user_id: int) -> None:
    if not (token or '').strip():
        raise ExportVerificationError(
            'نشست تأیید منقضی شده است. دوباره رمز عبور را وارد کنید.',
            code='password_challenge_expired',
        )
    try:
        payload = _password_signer().unsign((token or '').strip(), max_age=_PASSWORD_CHALLENGE_MAX_AGE)
    except SignatureExpired:
        raise ExportVerificationError(
            'زمان تأیید به پایان رسیده است. دوباره رمز عبور را وارد کنید.',
            code='password_challenge_expired',
        ) from None
    except BadSignature:
        raise ExportVerificationError('توکن تأیید نامعتبر است.', code='invalid_challenge') from None
    if str(payload) != str(user_id):
        raise ExportVerificationError('توکن تأیید نامعتبر است.', code='invalid_challenge')


def request_export_otp(user, *, request=None) -> OtpChallenge:
    phone = getattr(user, 'phone', '') or ''
    if not phone:
        raise ExportVerificationError('شماره موبایل حساب یافت نشد.', code='phone_missing')
    try:
        return request_otp(phone, EXPORT_OTP_PURPOSE, request=request)
    except OtpRateLimitError as exc:
        raise ExportVerificationError(
            exc.message,
            code=getattr(exc, 'code', 'otp_rate_limited'),
            retry_after=getattr(exc, 'retry_after', None),
        ) from exc
    except OtpError as exc:
        raise ExportVerificationError(exc.message, code=getattr(exc, 'code', 'otp_error')) from exc


def _otp_challenge_payload(challenge: OtpChallenge, *, password_challenge: str) -> dict:
    now = timezone.now()
    data = {
        'phone_display': _mask_phone(challenge.phone),
        'purpose': challenge.purpose,
        'expires_in': max(0, int((challenge.expires_at - now).total_seconds())),
        'resend_in': max(0, int((challenge.resend_available_at - now).total_seconds())),
        'password_challenge': password_challenge,
    }
    if getattr(settings, 'OTP_DEBUG_RETURN_CODE', False) and challenge.debug_code:
        data['debug_code'] = challenge.debug_code
    return data


def begin_export_verification(user, password: str, *, request=None) -> dict:
    """مرحله ۱: تأیید رمز + ارسال OTP ورود."""
    challenge_token = verify_password_for_export(user, password)
    challenge = request_export_otp(user, request=request)
    return _otp_challenge_payload(challenge, password_challenge=challenge_token)


def resend_export_otp(user, password_challenge: str, *, request=None) -> dict:
    """ارسال مجدد OTP — فقط پس از تأیید رمز."""
    _read_password_challenge(password_challenge, user.pk)
    challenge = request_export_otp(user, request=request)
    return _otp_challenge_payload(challenge, password_challenge=password_challenge)


def complete_export_verification(user, password_challenge: str, otp_code: str, *, request=None) -> dict:
    """مرحله ۲: تأیید OTP و صدور مجوز خروجی."""
    _read_password_challenge(password_challenge, user.pk)
    phone = getattr(user, 'phone', '') or ''
    try:
        verify_otp(phone, EXPORT_OTP_PURPOSE, otp_code)
    except OtpError as exc:
        raise ExportVerificationError(exc.message, code=getattr(exc, 'code', 'otp_error')) from exc

    export_token = issue_export_token(user.pk)
    if request is not None:
        mark_session_export_verified(request)

    logger.info('Export verification completed user_id=%s', user.pk)
    return {
        'export_token': export_token,
        'expires_in': _token_max_age(),
        'phone_display': _mask_phone(phone),
    }


def issue_export_token(user_id: int) -> str:
    return _token_signer().sign(str(user_id))


def validate_export_token(token: str, user_id: int) -> bool:
    if not (token or '').strip():
        return False
    try:
        payload = _token_signer().unsign((token or '').strip(), max_age=_token_max_age())
    except (SignatureExpired, BadSignature):
        return False
    return str(payload) == str(user_id)


def mark_session_export_verified(request) -> None:
    until = timezone.now() + timedelta(seconds=_session_max_age())
    request.session[_SESSION_KEY] = until.timestamp()
    request.session.modified = True


def is_session_export_verified(request) -> bool:
    raw = request.session.get(_SESSION_KEY)
    if raw is None:
        return False
    try:
        until = float(raw)
    except (TypeError, ValueError):
        return False
    if timezone.now().timestamp() >= until:
        return False
    return True


def extract_export_token(request) -> str:
    token = (request.headers.get('X-Export-Token') or request.META.get('HTTP_X_EXPORT_TOKEN') or '').strip()
    if not token:
        token = (request.GET.get('export_token') or '').strip()
    return token


def is_export_authorized(request, user) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if is_session_export_verified(request):
        return True
    token = extract_export_token(request)
    return validate_export_token(token, user.pk)


def export_verification_required_response(request):
    """پاسخ 403 یکسان برای وب و API."""
    payload = {
        'ok': False,
        'error': 'برای خروجی گرفتن، تأیید هویت (رمز عبور + کد پیامک) لازم است.',
        'code': 'EXPORT_VERIFICATION_REQUIRED',
    }
    accept = (request.headers.get('Accept') or request.META.get('HTTP_ACCEPT') or '').lower()
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    wants_json = 'application/json' in accept or is_ajax
    if wants_json:
        return JsonResponse(payload, status=403)
    from django.http import HttpResponse

    html = (
        '<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
        '<title>تأیید هویت لازم است</title></head><body style="font-family:tahoma;padding:2rem;text-align:center">'
        '<h1>تأیید هویت لازم است</h1>'
        '<p>برای دانلود این فایل، از میزکار دوباره درخواست خروجی دهید و رمز عبور + کد پیامک را وارد کنید.</p>'
        '<p><a href="javascript:history.back()">بازگشت</a></p></body></html>'
    )
    return HttpResponse(html, status=403, content_type='text/html; charset=utf-8')
