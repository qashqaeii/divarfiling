"""سرویس مرکزی نشست‌های دیوار."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone

from accounts.phone_utils import is_valid_iran_mobile, normalize_phone
from accounts.models import PhoneDetectorExtractionLine
from workspace.divar_session_models import (
    DivarAccountSession,
    DivarOtpChallenge,
    DivarPhoneFetchLog,
)
from workspace.services.divar_session.coordination import (
    assert_rate_limit,
    session_operation_lock,
)
from workspace.services.divar_session.crypto import decrypt_payload, encrypt_payload
from workspace.services.divar_session.errors import DivarSessionError
from workspace.services.divar_session.pd_import import PhoneDetectorImportError
from workspace.services.divar_session.runtime import DivarUserRuntime

logger = logging.getLogger(__name__)

OTP_TTL_SECONDS = 120
OTP_RATE_LIMIT_SECONDS = 60
FETCH_RATE_LIMIT_SECONDS = 8
PD_CONSENT_VERSION = '1'

_ACTIVE_STATUSES = (
    DivarAccountSession.AuthStatus.CONNECTED,
    DivarAccountSession.AuthStatus.CAPTCHA_REQUIRED,
)


def _otp_rate_key(user_id: int, phone: str) -> str:
    return f'divar_otp_rl:{user_id}:{phone}'


def _fetch_rate_key(user_id: int) -> str:
    return f'divar_fetch_rl:{user_id}'


def _visible_session(user) -> Optional[DivarAccountSession]:
    """آخرین نشست قابل‌نمایش (غیر از قطع‌شده)."""
    return (
        DivarAccountSession.objects.filter(user=user)
        .exclude(auth_status=DivarAccountSession.AuthStatus.DISCONNECTED)
        .order_by('-updated_at', '-connected_at')
        .first()
    )


def get_primary_session(user) -> Optional[DivarAccountSession]:
    """نشست عملیاتی برای fetch — شامل نشست معتبر حین OTP مجدد."""
    row = (
        DivarAccountSession.objects.filter(
            user=user,
            auth_status__in=_ACTIVE_STATUSES,
        )
        .order_by('-last_success_at', '-connected_at', '-updated_at')
        .first()
    )
    if row:
        return row
    pending = (
        DivarAccountSession.objects.filter(
            user=user,
            auth_status=DivarAccountSession.AuthStatus.PENDING_OTP,
        )
        .exclude(encrypted_session='')
        .order_by('-updated_at')
        .first()
    )
    if pending and pending.encrypted_session:
        return pending
    return None


def _try_refresh_session_row(row: DivarAccountSession) -> bool:
    if not row.encrypted_session:
        return False
    try:
        runtime = _runtime_from_row(row)
        health = runtime.health_check()
        if health.ok:
            _persist_session(row, runtime)
            return True
    except Exception:
        logger.debug('divar session refresh failed for %s', row.pk, exc_info=True)
    return False


def _mark_session_expired(row: DivarAccountSession) -> DivarAccountSession:
    row.auth_status = DivarAccountSession.AuthStatus.EXPIRED
    row.save(update_fields=['auth_status', 'updated_at'])
    from workspace.services.divar_session.phone_detector_bridge import on_central_session_invalidated

    on_central_session_invalidated(row, reason='expired')
    return row


def _resolve_expired_if_needed(row: DivarAccountSession) -> DivarAccountSession:
    if row.auth_status != DivarAccountSession.AuthStatus.CONNECTED:
        return row
    if not row.encrypted_session:
        return _mark_session_expired(row)
    if row.token_expires_at and row.token_expires_at <= timezone.now():
        if _try_refresh_session_row(row):
            return row
        return _mark_session_expired(row)
    return row


def public_session_status(user) -> dict[str, Any]:
    row = _visible_session(user)
    if not row:
        return {'has_session': False, 'button_state': 'connect'}

    row = _resolve_expired_if_needed(row)

    if row.auth_status == DivarAccountSession.AuthStatus.EXPIRED:
        return {
            'has_session': False,
            'button_state': 'reconnect',
            'divar_phone_masked': _mask_phone(row.divar_phone),
        }
    if row.auth_status == DivarAccountSession.AuthStatus.CAPTCHA_REQUIRED:
        return {
            'has_session': True,
            'button_state': 'captcha',
            'divar_phone_masked': _mask_phone(row.divar_phone),
            'hip_status': row.hip_status,
            'captcha_post_url': (row.captcha_post_url or '').strip(),
        }
    if row.auth_status == DivarAccountSession.AuthStatus.CONNECTED:
        return {
            'has_session': True,
            'button_state': 'fetch',
            'divar_phone_masked': _mask_phone(row.divar_phone),
        }
    if row.auth_status == DivarAccountSession.AuthStatus.PENDING_OTP:
        if row.encrypted_session:
            return {
                'has_session': True,
                'button_state': 'fetch',
                'divar_phone_masked': _mask_phone(row.divar_phone),
            }
        return {'has_session': False, 'button_state': 'connect'}
    return {'has_session': False, 'button_state': 'connect'}


def _mask_phone(phone: str) -> str:
    p = normalize_phone(phone or '')
    if len(p) < 6:
        return '***'
    return f'{p[:4]}***{p[-2:]}'


def _runtime_from_row(row: DivarAccountSession) -> DivarUserRuntime:
    runtime = DivarUserRuntime()
    if row.encrypted_session:
        payload = decrypt_payload(row.encrypted_session)
        runtime.apply_session_payload(payload)
    return runtime


def _persist_session(
    row: DivarAccountSession,
    runtime: DivarUserRuntime,
    *,
    preserve_captcha: bool = False,
    force_auth_status: str | None = None,
) -> None:
    health = runtime.health_check()
    payload = runtime.export_session_payload(phone=row.divar_phone)
    row.encrypted_session = encrypt_payload(payload)
    row.last_health_check_at = timezone.now()
    row.token_expires_at = health.expires_at
    if health.ok and health.status == 'active':
        row.last_refresh_at = timezone.now()

    if force_auth_status:
        row.auth_status = force_auth_status
    elif preserve_captcha and row.auth_status == DivarAccountSession.AuthStatus.CAPTCHA_REQUIRED:
        pass
    elif health.ok:
        if row.auth_status != DivarAccountSession.AuthStatus.CAPTCHA_REQUIRED:
            row.auth_status = DivarAccountSession.AuthStatus.CONNECTED
            row.last_error_code = ''
            row.last_error_message = ''
    elif health.needs_relogin:
        row.auth_status = DivarAccountSession.AuthStatus.EXPIRED

    update_fields = [
        'encrypted_session',
        'last_health_check_at',
        'token_expires_at',
        'auth_status',
        'last_error_code',
        'last_error_message',
        'updated_at',
    ]
    if health.ok and health.status == 'active':
        update_fields.append('last_refresh_at')
    row.save(update_fields=update_fields)


def send_divar_otp(user, phone: str) -> dict[str, Any]:
    phone = normalize_phone(phone or '')
    if not is_valid_iran_mobile(phone):
        raise DivarSessionError('شماره موبایل معتبر نیست.', code='invalid_phone')
    assert_rate_limit(_otp_rate_key(user.id, phone), seconds=OTP_RATE_LIMIT_SECONDS)
    try:
        runtime = DivarUserRuntime()
        normalized = runtime.send_login_otp(phone)
    except PhoneDetectorImportError as exc:
        raise DivarSessionError(str(exc), code='not_configured') from exc
    except Exception as exc:
        logger.warning('divar otp send failed user=%s: %s', user.id, exc.__class__.__name__)
        raise DivarSessionError('ارسال کد از دیوار ناموفق بود.', code='otp_send_failed') from exc

    pending = runtime.export_otp_pending(normalized)
    encrypted = encrypt_payload(pending)
    expires = timezone.now() + timedelta(seconds=OTP_TTL_SECONDS)
    DivarOtpChallenge.objects.update_or_create(
        user=user,
        divar_phone=normalized,
        defaults={'encrypted_pending': encrypted, 'expires_at': expires},
    )
    with transaction.atomic():
        row, _ = DivarAccountSession.objects.select_for_update().get_or_create(
            user=user,
            divar_phone=normalized,
            defaults={'auth_status': DivarAccountSession.AuthStatus.PENDING_OTP},
        )
        if not row.encrypted_session:
            row.auth_status = DivarAccountSession.AuthStatus.PENDING_OTP
            row.save(update_fields=['auth_status', 'updated_at'])

    return {'ok': True, 'phone': normalized, 'otp_ttl_seconds': OTP_TTL_SECONDS}


def verify_divar_otp(user, phone: str, otp: str) -> dict[str, Any]:
    phone = normalize_phone(phone or '')
    otp = (otp or '').strip()
    if not otp:
        raise DivarSessionError('کد تأیید الزامی است.', code='missing_otp')
    challenge = DivarOtpChallenge.objects.filter(user=user, divar_phone=phone).first()
    if not challenge or challenge.is_expired:
        raise DivarSessionError(
            'نشست OTP منقضی شده — دوباره «ارسال کد» را بزنید.',
            code='otp_expired',
        )
    try:
        runtime = DivarUserRuntime()
        runtime.apply_otp_pending(decrypt_payload(challenge.encrypted_pending))
        saved_phone = runtime.verify_login_otp(otp, phone=phone)
    except PhoneDetectorImportError as exc:
        raise DivarSessionError(str(exc), code='not_configured') from exc
    except Exception as exc:
        logger.warning('divar otp verify failed user=%s: %s', user.id, exc.__class__.__name__)
        raise DivarSessionError('کد تأیید نامعتبر یا منقضی است.', code='otp_invalid') from exc

    challenge.delete()
    with transaction.atomic():
        row, _ = DivarAccountSession.objects.select_for_update().get_or_create(
            user=user,
            divar_phone=saved_phone,
        )
        row.divar_phone = saved_phone
        row.auth_status = DivarAccountSession.AuthStatus.CONNECTED
        row.connected_at = timezone.now()
        row.hip_status = ''
        row.captcha_post_url = ''
        _persist_session(row, runtime)
        row.last_success_at = timezone.now()
        row.save(
            update_fields=[
                'divar_phone',
                'connected_at',
                'last_success_at',
                'captcha_post_url',
                'updated_at',
            ],
        )

    return {'ok': True, 'phone': saved_phone, 'status': public_session_status(user)}


def disconnect_divar_session(user, *, session_id: str | None = None) -> dict[str, Any]:
    qs = DivarAccountSession.objects.filter(user=user)
    if session_id:
        qs = qs.filter(pk=session_id)
    updated = 0
    from workspace.services.divar_session.phone_detector_bridge import on_central_session_invalidated

    for row in qs:
        on_central_session_invalidated(row, reason='disconnected')
        row.mark_disconnected()
        updated += 1
    return {'ok': True, 'disconnected': updated}


def _contact_uuid_from_listing(listing) -> str:
    data = listing.data or {}
    for key in ('تماس_contact_uuid', 'contact_uuid', 'تماس contact_uuid'):
        val = data.get(key)
        if val:
            return str(val).strip()
    contact = data.get('تماس') or data.get('contact')
    if isinstance(contact, dict) and contact.get('contact_uuid'):
        return str(contact['contact_uuid']).strip()
    return ''


def fetch_listing_phone(user, listing) -> dict[str, Any]:
    assert_rate_limit(_fetch_rate_key(user.id), seconds=FETCH_RATE_LIMIT_SECONDS)

    row = get_primary_session(user)
    if not row:
        raise DivarSessionError('ابتدا حساب دیوار را متصل کنید.', code='no_session')
    if row.auth_status == DivarAccountSession.AuthStatus.PENDING_OTP and row.encrypted_session:
        effective = DivarAccountSession.AuthStatus.CONNECTED
    else:
        effective = row.auth_status
    if effective not in _ACTIVE_STATUSES:
        raise DivarSessionError('ابتدا حساب دیوار را متصل کنید.', code='no_session')

    token = (listing.token or '').strip()
    if not token:
        raise DivarSessionError('شناسه آگهی موجود نیست.', code='missing_token')

    post_url = (listing.link or '').strip() or f'https://divar.ir/v/{token}'
    contact_uuid = _contact_uuid_from_listing(listing)

    phone_out = ''
    name_hint = ''

    try:
        with session_operation_lock(row):
            row.refresh_from_db()
            runtime = _runtime_from_row(row)
            health = runtime.health_check()
            if not health.ok:
                _mark_session_expired(row)
                raise DivarSessionError('نشست منقضی شده — دوباره متصل شوید.', code='session_expired')

            scraper = runtime.make_scraper()
            if not contact_uuid:
                detail = scraper.fetch_post_detail(token)
                if not detail:
                    raise DivarSessionError('آگهی در دیوار یافت نشد.', code='listing_not_found')
                contact = detail.get('contact') or {}
                contact_uuid = str(contact.get('contact_uuid') or '').strip()
                webengage = detail.get('webengage') or {}
                name_hint = str(webengage.get('contact_name') or '').strip()

            if not contact_uuid:
                raise DivarSessionError('اطلاعات تماس این آگهی در دسترس نیست.', code='no_contact_uuid')

            phone, _display, hip_status = scraper.fetch_contact_phone(
                token,
                contact_uuid,
                post_url,
            )
            if hip_status and str(hip_status).startswith('captcha'):
                row.auth_status = DivarAccountSession.AuthStatus.CAPTCHA_REQUIRED
                row.hip_status = str(hip_status)
                row.captcha_post_url = post_url
                row.last_error_code = 'captcha_required'
                row.last_error_message = 'نیاز به حل کپچا در دیوار'
                _persist_session(row, runtime, preserve_captcha=True)
                row.save(update_fields=['captcha_post_url', 'updated_at'])
                DivarPhoneFetchLog.objects.create(
                    user=user,
                    listing_token=token,
                    success=False,
                    error_code='captcha_required',
                )
                return {
                    'ok': False,
                    'code': 'captcha_required',
                    'post_url': post_url,
                    'status': public_session_status(user),
                }

            if hip_status == 'auth_expired':
                _mark_session_expired(row)
                raise DivarSessionError(
                    'نشست منقضی شده — دوباره متصل شوید.',
                    code='auth_expired',
                )
            if not phone:
                raise DivarSessionError(
                    'شماره تماس در پاسخ دیوار موجود نبود.',
                    code='no_phone',
                )

            pd = runtime._pd
            phone_out = pd.normalize_phone(phone)
            row.auth_status = DivarAccountSession.AuthStatus.CONNECTED
            row.hip_status = ''
            row.captcha_post_url = ''
            row.last_success_at = timezone.now()
            _persist_session(row, runtime)
            row.save(update_fields=['captcha_post_url', 'last_success_at', 'updated_at'])
    except DivarSessionError as exc:
        if exc.code != 'captcha_required':
            DivarPhoneFetchLog.objects.create(
                user=user,
                listing_token=token,
                success=False,
                error_code=exc.code,
            )
        raise
    except PhoneDetectorImportError as exc:
        raise DivarSessionError(str(exc), code='not_configured') from exc
    except Exception as exc:
        logger.warning('divar fetch phone failed user=%s: %s', user.id, exc.__class__.__name__)
        DivarPhoneFetchLog.objects.create(
            user=user,
            listing_token=token,
            success=False,
            error_code='fetch_failed',
        )
        raise DivarSessionError('خطا در ارتباط با دیوار.', code='fetch_failed') from exc

    DivarPhoneFetchLog.objects.create(
        user=user,
        listing_token=token,
        success=True,
        error_code='',
    )
    return {
        'ok': True,
        'phone': phone_out,
        'owner_name_hint': name_hint,
        'status': public_session_status(user),
    }


def admin_stats() -> dict[str, int]:
    qs = DivarAccountSession.objects.all()
    return {
        'total_sessions': qs.count(),
        'connected': qs.filter(auth_status=DivarAccountSession.AuthStatus.CONNECTED).count(),
        'expired': qs.filter(auth_status=DivarAccountSession.AuthStatus.EXPIRED).count(),
        'captcha': qs.filter(auth_status=DivarAccountSession.AuthStatus.CAPTCHA_REQUIRED).count(),
        'pd_consent': qs.filter(phone_detector_consent=True).count(),
        'pd_linked': PhoneDetectorExtractionLine.objects.filter(
            divar_account_session__isnull=False,
        ).count(),
        'fetch_success': DivarPhoneFetchLog.objects.filter(success=True).count(),
        'fetch_errors_recent': DivarPhoneFetchLog.objects.filter(
            success=False,
            created_at__gte=timezone.now() - timedelta(days=7),
        ).count(),
    }
