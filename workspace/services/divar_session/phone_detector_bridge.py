"""اتصال نشست مرکزی به خطوط Phone Detector بدون OTP مجدد."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from accounts.models import PhoneDetectorExtractionLine
from workspace.divar_session_models import DivarAccountSession
from workspace.services.divar_session.crypto import decrypt_payload
from workspace.services.divar_session.pd_import import PhoneDetectorImportError, resolve_phone_detector_dir
from workspace.services.divar_session.service import DivarSessionError, _persist_session, _runtime_from_row

logger = logging.getLogger(__name__)


def list_sessions_for_admin(*, consent_only: bool = False) -> list[dict]:
    qs = DivarAccountSession.objects.select_related('user').order_by('-updated_at')
    if consent_only:
        qs = qs.filter(phone_detector_consent=True)
    rows = []
    for row in qs:
        line = PhoneDetectorExtractionLine.objects.filter(divar_account_session=row).first()
        rows.append({
            'id': str(row.pk),
            'divar_phone': row.divar_phone,
            'user_label': getattr(row.user, 'phone', None) or row.user.username,
            'user_id': row.user_id,
            'auth_status': row.auth_status,
            'auth_status_label': row.get_auth_status_display(),
            'last_health_check_at': row.last_health_check_at,
            'last_success_at': row.last_success_at,
            'phone_detector_consent': row.phone_detector_consent,
            'on_line': bool(line),
            'line_phone': line.phone if line else '',
            'line_operational_status': line.operational_status if line else '',
            'can_add_to_line': (
                row.phone_detector_consent
                and row.auth_status == DivarAccountSession.AuthStatus.CONNECTED
                and not line
            ),
        })
    return rows


def grant_phone_detector_consent(session: DivarAccountSession, *, version: str = '1') -> None:
    session.phone_detector_consent = True
    session.phone_detector_consent_at = timezone.now()
    session.phone_detector_consent_version = version
    session.save(
        update_fields=[
            'phone_detector_consent',
            'phone_detector_consent_at',
            'phone_detector_consent_version',
            'updated_at',
        ],
    )


def add_session_to_phone_detector_line(session: DivarAccountSession) -> dict:
    if not session.phone_detector_consent:
        raise DivarSessionError('مجوز استفاده در Phone Detector ثبت نشده است.', code='no_consent')
    if session.auth_status != DivarAccountSession.AuthStatus.CONNECTED:
        raise DivarSessionError('نشست معتبر نیست.', code='invalid_session')
    if PhoneDetectorExtractionLine.objects.filter(divar_account_session=session).exists():
        raise DivarSessionError('این نشست قبلاً به خطوط اضافه شده است.', code='already_linked')
    if PhoneDetectorExtractionLine.objects.filter(phone=session.divar_phone).exists():
        raise DivarSessionError(
            'این شماره قبلاً در خطوط Phone Detector ثبت شده است.',
            code='phone_duplicate',
        )

    pd = resolve_phone_detector_dir()
    if not pd:
        raise DivarSessionError('phone-detector پیکربندی نشده است.', code='not_configured')

    runtime = _runtime_from_row(session)
    health = runtime.health_check()
    if not health.ok:
        session.auth_status = DivarAccountSession.AuthStatus.EXPIRED
        session.save(update_fields=['auth_status', 'updated_at'])
        raise DivarSessionError('نشست منقضی شده است.', code='session_expired')

    payload = decrypt_payload(session.encrypted_session)
    sessions_dir = pd / 'sessions'
    sessions_dir.mkdir(parents=True, exist_ok=True)
    target = sessions_dir / f'{session.divar_phone}.json'
    tmp = target.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(target)

    _persist_session(session, runtime)

    with transaction.atomic():
        line = PhoneDetectorExtractionLine.objects.create(
            phone=session.divar_phone,
            operational_status=PhoneDetectorExtractionLine.OperationalStatus.PAUSED,
            divar_account_session=session,
            status_detail='از نشست کاربر فایلینگ — فعال‌سازی دستی لازم است',
        )

    from accounts.services.phone_detector_line_ops import sync_lines_from_sessions

    sync_lines_from_sessions()
    return {'ok': True, 'phone': session.divar_phone, 'line_id': line.pk}


def unlink_session_from_line(session: DivarAccountSession) -> dict:
    deleted, _ = PhoneDetectorExtractionLine.objects.filter(divar_account_session=session).delete()
    return {'ok': True, 'removed': deleted}
