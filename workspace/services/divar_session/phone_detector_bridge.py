"""اتصال نشست مرکزی به خطوط Phone Detector بدون OTP مجدد."""
from __future__ import annotations

import json
import logging

from django.db import transaction
from django.utils import timezone

from accounts.models import PhoneDetectorExtractionLine
from workspace.divar_session_models import DivarAccountSession, DivarPdSessionFileSyncBlock
from workspace.services.divar_session.errors import DivarSessionError
from workspace.services.divar_session.pd_import import resolve_phone_detector_dir
from workspace.services.divar_session.pd_sync_block import (
    block_phone_detector_file_sync,
    clear_phone_detector_file_sync_block,
)
from workspace.services.divar_session.service import _persist_session, _runtime_from_row

logger = logging.getLogger(__name__)


def _session_json_path(phone: str):
    pd = resolve_phone_detector_dir()
    if not pd:
        return None
    return pd / 'sessions' / f'{phone}.json'


def on_central_session_invalidated(
    session: DivarAccountSession,
    *,
    reason: str = 'invalid',
) -> None:
    """خط مرتبط را از rotation خارج کن."""
    detail = {
        'disconnected': 'نشست کاربر قطع شد — خط متوقف شد',
        'expired': 'نشست منقضی شد — خط متوقف شد',
        'invalid': 'نشست نامعتبر — خط متوقف شد',
    }.get(reason, 'نشست نامعتبر — خط متوقف شد')

    block_reason = {
        'disconnected': DivarPdSessionFileSyncBlock.Reason.DISCONNECTED,
        'expired': DivarPdSessionFileSyncBlock.Reason.INVALID,
        'invalid': DivarPdSessionFileSyncBlock.Reason.INVALID,
    }.get(reason, DivarPdSessionFileSyncBlock.Reason.INVALID)

    linked = PhoneDetectorExtractionLine.objects.filter(divar_account_session=session)
    if linked.exists():
        block_phone_detector_file_sync(
            session.divar_phone,
            reason=block_reason,
            session=session,
        )
    linked.update(
        operational_status=PhoneDetectorExtractionLine.OperationalStatus.EVICTED,
        status_detail=detail,
        updated_at=timezone.now(),
    )
    try:
        from accounts.services.extraction_lines_reconcile import reconcile_extraction_lines

        reconcile_extraction_lines()
    except Exception:
        logger.debug('reconcile after session invalidation skipped', exc_info=True)


def list_sessions_for_admin(*, consent_only: bool = False) -> list[dict]:
    qs = DivarAccountSession.objects.select_related('user').order_by('-updated_at')
    if consent_only:
        qs = qs.filter(phone_detector_consent=True)
    rows = []
    for row in qs:
        line = PhoneDetectorExtractionLine.objects.filter(divar_account_session=row).first()
        if not line:
            line = PhoneDetectorExtractionLine.objects.filter(
                phone=row.divar_phone,
                line_source=PhoneDetectorExtractionLine.LineSource.FILING,
            ).first()
        auto_managed = (
            row.auth_status == DivarAccountSession.AuthStatus.CONNECTED
            and not row.extraction_auto_opt_out
        )
        rows.append({
            'id': str(row.pk),
            'divar_phone': row.divar_phone,
            'user_label': getattr(row.user, 'phone', None) or row.user.username,
            'user_id': row.user_id,
            'auth_status': row.auth_status,
            'auth_status_label': row.get_auth_status_display(),
            'last_health_check_at': row.last_health_check_at,
            'last_success_at': row.last_success_at,
            'phone_detector_consent': row.phone_detector_consent or auto_managed,
            'consent_auto': auto_managed,
            'extraction_auto_opt_out': row.extraction_auto_opt_out,
            'extraction_auto_managed': auto_managed,
            'on_line': bool(line) and (line.operational_status != PhoneDetectorExtractionLine.OperationalStatus.EVICTED if line else False),
            'line_phone': line.phone if line else '',
            'line_operational_status': line.operational_status if line else '',
            'line_source': line.line_source if line else '',
            'can_add_to_line': False,
            'can_opt_out_auto_sync': auto_managed,
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


def _write_refreshed_session_file(session: DivarAccountSession) -> None:
    runtime = _runtime_from_row(session)
    health = runtime.health_check()
    if not health.ok:
        session.auth_status = DivarAccountSession.AuthStatus.EXPIRED
        session.save(update_fields=['auth_status', 'updated_at'])
        raise DivarSessionError('نشست منقضی شده است.', code='session_expired')
    _persist_session(session, runtime)

    path = _session_json_path(session.divar_phone)
    if not path:
        raise DivarSessionError('phone-detector پیکربندی نشده است.', code='not_configured')
    payload = runtime.export_session_payload(phone=session.divar_phone)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def add_session_to_phone_detector_line(session: DivarAccountSession) -> dict:
    session.extraction_auto_opt_out = False
    session.save(update_fields=['extraction_auto_opt_out', 'updated_at'])
    grant_phone_detector_consent(session)
    from accounts.services.extraction_lines_reconcile import reconcile_extraction_lines

    stats = reconcile_extraction_lines(force=True)
    line = PhoneDetectorExtractionLine.objects.filter(divar_account_session=session).first()
    return {
        'ok': True,
        'phone': session.divar_phone,
        'line_id': line.pk if line else None,
        'reconcile': stats,
    }


def unlink_session_from_line(session: DivarAccountSession) -> dict:
    session.extraction_auto_opt_out = True
    session.save(update_fields=['extraction_auto_opt_out', 'updated_at'])
    had_line = PhoneDetectorExtractionLine.objects.filter(divar_account_session=session).exists()
    if had_line:
        block_phone_detector_file_sync(
            session.divar_phone,
            reason=DivarPdSessionFileSyncBlock.Reason.UNLINKED,
            session=session,
        )
    PhoneDetectorExtractionLine.objects.filter(divar_account_session=session).update(
        operational_status=PhoneDetectorExtractionLine.OperationalStatus.EVICTED,
        status_detail='همگام‌سازی خودکار توسط مدیر قطع شد',
        updated_at=timezone.now(),
    )
    from accounts.services.extraction_lines_reconcile import reconcile_extraction_lines

    reconcile_extraction_lines(force=True)
    return {'ok': True, 'opt_out': True}
