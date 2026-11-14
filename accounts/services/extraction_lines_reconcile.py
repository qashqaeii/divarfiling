"""همگام‌سازی idempotent نشست فایلینگ ↔ خطوط استخراج ↔ فایل‌های phone-detector."""
from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.models import PhoneDetectorExtractionLine
from accounts.services.phone_detector_line_ops import (
    normalize_line_phone,
    sync_lines_from_sessions,
)
from accounts.services.phone_detector_lines import (
    PhoneDetectorLineError,
    resolve_phone_detector_dir,
)  # noqa: TID251 — سرویس reconcile به لایه خطوط متکی است
from workspace.divar_session_models import DivarAccountSession
from workspace.services.divar_session.pd_sync_block import (
    clear_phone_detector_file_sync_block,
    is_phone_detector_file_sync_blocked,
)
from workspace.services.divar_session.phone_detector_bridge import (
    grant_phone_detector_consent,
)

logger = logging.getLogger(__name__)

OPS = PhoneDetectorExtractionLine.OperationalStatus
SRC = PhoneDetectorExtractionLine.LineSource

_RECONCILE_STATS: dict[str, int] = {}


def _eligible_filing_session(session: DivarAccountSession) -> bool:
    if session.extraction_auto_opt_out:
        return False
    if is_phone_detector_file_sync_blocked(session.divar_phone):
        return False
    if session.auth_status != DivarAccountSession.AuthStatus.CONNECTED:
        return False
    if not (session.encrypted_session or '').strip():
        return False
    return True


def _session_requires_eviction(session: DivarAccountSession) -> bool:
    return session.auth_status in (
        DivarAccountSession.AuthStatus.EXPIRED,
        DivarAccountSession.AuthStatus.DISCONNECTED,
        DivarAccountSession.AuthStatus.PENDING_OTP,
        DivarAccountSession.AuthStatus.CAPTCHA_REQUIRED,
        DivarAccountSession.AuthStatus.ERROR,
    )


def _line_should_leave_active_index(line: PhoneDetectorExtractionLine) -> bool:
    if line.admin_hold:
        return True
    if line.operational_status in (
        OPS.BLOCKED_CAPTCHA,
        OPS.ERROR,
        OPS.EVICTED,
    ):
        return True
    if line.line_source == SRC.FILING and line.divar_account_session_id:
        session = line.divar_account_session
        if _session_requires_eviction(session):
            return True
    return False


def _ensure_consent_for_connected() -> int:
    updated = 0
    qs = DivarAccountSession.objects.filter(
        auth_status=DivarAccountSession.AuthStatus.CONNECTED,
        phone_detector_consent=False,
        extraction_auto_opt_out=False,
    )
    for row in qs.iterator():
        grant_phone_detector_consent(row)
        updated += 1
    return updated


def _provision_filing_session(session: DivarAccountSession) -> PhoneDetectorExtractionLine:
    from workspace.services.divar_session.phone_detector_bridge import (
        _write_refreshed_session_file,
    )

    phone = normalize_line_phone(session.divar_phone)
    clear_phone_detector_file_sync_block(phone)
    _write_refreshed_session_file(session)

    line = PhoneDetectorExtractionLine.objects.filter(phone=phone).first()
    if line and line.line_source == SRC.MANUAL and not line.divar_account_session_id:
        raise PhoneDetectorLineError(
            'این شماره قبلاً به‌صورت خط دستی OTP ثبت شده است.',
            code='phone_duplicate',
        )

    created = False
    if not line:
        line = PhoneDetectorExtractionLine.objects.create(
            phone=phone,
            divar_account_session=session,
            line_source=SRC.FILING,
            operational_status=OPS.ACTIVE,
            status_detail='همگام‌سازی خودکار از نشست فایلینگ',
        )
        created = True
    else:
        updates: list[str] = []
        if line.divar_account_session_id != session.pk:
            line.divar_account_session = session
            updates.append('divar_account_session')
        if line.line_source != SRC.FILING:
            line.line_source = SRC.FILING
            updates.append('line_source')
        if line.admin_hold:
            pass
        elif line.operational_status in (OPS.EVICTED, OPS.PAUSED) and not _line_should_leave_active_index(line):
            line.operational_status = OPS.ACTIVE
            line.status_detail = 'بازیابی خودکار — نشست فایلینگ سالم شد'
            updates.extend(['operational_status', 'status_detail'])
        elif (
            line.operational_status not in (OPS.BLOCKED_CAPTCHA, OPS.RUNNING)
            and not line.admin_hold
        ):
            if line.operational_status != OPS.ACTIVE:
                line.operational_status = OPS.ACTIVE
                line.status_detail = 'فعال — همگام‌سازی خودکار'
                updates.extend(['operational_status', 'status_detail'])
        if updates:
            line.updated_at = timezone.now()
            updates.append('updated_at')
            line.save(update_fields=list(dict.fromkeys(updates)))

    _ensure_phone_in_pd_index(phone)
    return line if created else line


def _ensure_phone_in_pd_index(phone: str) -> None:
    if not resolve_phone_detector_dir():
        return
    try:
        from accounts.services.phone_detector_lines import _get_engine

        engine = _get_engine()
        engine.registry.save_index()
    except Exception:
        logger.debug('index refresh for %s skipped', phone, exc_info=True)


def _evict_phone_from_pd_index(
    phone: str,
    *,
    delete_session_file: bool,
) -> bool:
    if not resolve_phone_detector_dir():
        return False
    phone = normalize_line_phone(phone)
    try:
        if delete_session_file:
            from accounts.services.phone_detector_lines import _get_engine

            engine = _get_engine()
            if phone in (engine.registry.list_phones() if hasattr(engine, 'registry') else []):
                engine.remove_account(phone)
            else:
                path = engine.registry.path_for(phone)
                if path.is_file():
                    engine.remove_account(phone)
        else:
            _remove_phone_from_index_only(phone)
        return True
    except Exception:
        logger.warning('evict %s from pd index failed', phone, exc_info=True)
        return False


def _remove_phone_from_index_only(phone: str) -> None:
    """حذف از چرخش بدون پاک‌کردن فایل سشن (خطوط دستی با کپچا)."""
    pd = resolve_phone_detector_dir()
    if not pd:
        return
    root = pd / 'sessions'
    index_path = root / 'index.json'
    if not index_path.is_file():
        return
    import json

    try:
        data = json.loads(index_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(data, dict):
        return
    phones = [normalize_line_phone(p) for p in data.get('phones') or []]
    phones = [p for p in phones if p and p != phone]
    if data.get('active_phone') and normalize_line_phone(data['active_phone']) == phone:
        data['active_phone'] = phones[0] if phones else None
    data['phones'] = phones
    tmp = index_path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(index_path)


@transaction.atomic
def reconcile_extraction_lines(*, force: bool = False) -> dict[str, Any]:
    """ورود، خروج و بازیابی خطوط — idempotent."""
    stats = {
        'consent_granted': 0,
        'provisioned': 0,
        'evicted': 0,
        'recovered': 0,
        'index_adjusted': 0,
        'skipped_opt_out': 0,
    }
    if not resolve_phone_detector_dir():
        return {**stats, 'ok': False, 'reason': 'phone_detector_not_configured'}

    stats['consent_granted'] = _ensure_consent_for_connected()

    for session in DivarAccountSession.objects.select_related('user').iterator():
        phone = normalize_line_phone(session.divar_phone)
        if not phone:
            continue
        if session.extraction_auto_opt_out:
            stats['skipped_opt_out'] += 1
            continue

        line = PhoneDetectorExtractionLine.objects.filter(
            divar_account_session=session,
        ).first()
        if not line:
            line = PhoneDetectorExtractionLine.objects.filter(phone=phone, line_source=SRC.FILING).first()

        if _eligible_filing_session(session):
            try:
                before_status = line.operational_status if line else None
                line = _provision_filing_session(session)
                stats['provisioned'] += 1
                if before_status in (OPS.EVICTED, OPS.PAUSED, None) and line.operational_status == OPS.ACTIVE:
                    stats['recovered'] += 1
            except PhoneDetectorLineError as exc:
                logger.info('provision skip %s: %s', phone, exc.message)
            except Exception:
                logger.exception('provision failed %s', phone)
            continue

        if line and line.line_source == SRC.FILING:
            _evict_filing_line(line, session=session)
            stats['evicted'] += 1

    for line in PhoneDetectorExtractionLine.objects.select_related('divar_account_session').all():
        if _line_should_leave_active_index(line):
            if _evict_line_from_active_rotation(line):
                stats['index_adjusted'] += 1

    sync_lines_from_sessions()
    return {**stats, 'ok': True}


def _evict_filing_line(
    line: PhoneDetectorExtractionLine,
    *,
    session: DivarAccountSession | None,
) -> None:
    detail = 'خارج از چرخه — نشست فایلینگ نامعتبر یا غیرفعال'
    if session:
        detail = f'خارج از چرخه — {session.get_auth_status_display()}'
    _evict_phone_from_pd_index(line.phone, delete_session_file=True)
    line.operational_status = OPS.EVICTED
    line.status_detail = detail
    line.updated_at = timezone.now()
    line.save(update_fields=['operational_status', 'status_detail', 'updated_at'])


def _evict_line_from_active_rotation(line: PhoneDetectorExtractionLine) -> bool:
    delete_file = line.line_source == SRC.FILING
    if line.operational_status == OPS.BLOCKED_CAPTCHA and line.line_source == SRC.MANUAL:
        delete_file = False
    if line.operational_status == OPS.PAUSED and line.admin_hold:
        return _remove_phone_from_index_only(line.phone) or True

    if line.operational_status in (OPS.BLOCKED_CAPTCHA, OPS.ERROR):
        if not delete_file:
            removed = _remove_phone_from_index_only(line.phone)
        else:
            removed = _evict_phone_from_pd_index(line.phone, delete_session_file=True)
        if line.operational_status != OPS.EVICTED and line.line_source == SRC.FILING:
            line.operational_status = OPS.EVICTED
            line.status_detail = line.status_detail or 'خارج از چرخه — غیرقابل استخراج'
            line.updated_at = timezone.now()
            line.save(update_fields=['operational_status', 'status_detail', 'updated_at'])
        return removed

    if line.line_source == SRC.FILING and line.divar_account_session_id:
        central = line.divar_account_session
        if central and _session_requires_eviction(central):
            _evict_filing_line(line, session=central)
            return True
    return False