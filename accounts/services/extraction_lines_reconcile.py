"""همگام‌سازی idempotent نشست فایلینگ ↔ خطوط استخراج ↔ فایل‌های phone-detector."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from accounts.models import PhoneDetectorExtractionLine
from accounts.services.phone_detector_line_ops import (
    normalize_line_phone,
    sync_lines_from_sessions,
)
from accounts.services.pd_sessions_file_lock import PdSessionsFileLock
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

RECONCILE_CACHE_LOCK = 'lac:extraction_lines_reconcile'
RECONCILE_LOCK_TTL = 90
_process_lock = threading.Lock()
_active_file_lock: PdSessionsFileLock | None = None


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


def _status_allows_auto_recovery(status: str) -> bool:
    """بازیابی خودکار فقط برای خارج‌شده‌های غیرکپچا — نه BLOCKED_CAPTCHA/ERROR."""
    return status in (
        OPS.EVICTED,
        OPS.PAUSED,
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
        if session and _session_requires_eviction(session):
            return True
    return False


def _preflight_provision_checks(
    phone: str,
    *,
    existing: PhoneDetectorExtractionLine | None,
) -> PhoneDetectorExtractionLine | None:
    """قبل از نوشتن فایل سشن — جلوگیری از بازنویسی خط دستی یا کپچا."""
    if existing and existing.admin_hold:
        return existing
    if existing and existing.operational_status == OPS.BLOCKED_CAPTCHA:
        return existing
    if existing and existing.line_source == SRC.MANUAL and not existing.divar_account_session_id:
        raise PhoneDetectorLineError(
            'این شماره قبلاً به‌صورت خط دستی OTP ثبت شده است.',
            code='phone_duplicate',
        )
    dup_qs = PhoneDetectorExtractionLine.objects.filter(phone=phone)
    if existing:
        dup_qs = dup_qs.exclude(pk=existing.pk)
    other = dup_qs.first()
    if other and other.line_source == SRC.MANUAL and not other.divar_account_session_id:
        raise PhoneDetectorLineError(
            'شماره با خط دستی OTP تداخل دارد.',
            code='phone_duplicate',
        )
    return existing


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


@transaction.atomic
def _provision_filing_session(session: DivarAccountSession) -> PhoneDetectorExtractionLine:
    from workspace.services.divar_session.phone_detector_bridge import (
        _write_refreshed_session_file,
    )

    phone = normalize_line_phone(session.divar_phone)
    line = (
        PhoneDetectorExtractionLine.objects.select_for_update()
        .filter(phone=phone)
        .first()
    )
    if line is None:
        line = (
            PhoneDetectorExtractionLine.objects.select_for_update()
            .filter(divar_account_session=session)
            .first()
        )

    preflight = _preflight_provision_checks(phone, existing=line)
    if preflight is not None and (
        preflight.admin_hold or preflight.operational_status == OPS.BLOCKED_CAPTCHA
    ):
        return preflight

    clear_phone_detector_file_sync_block(phone)
    _write_refreshed_session_file(session)

    line = PhoneDetectorExtractionLine.objects.select_for_update().filter(phone=phone).first()

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
        if line.admin_hold or line.operational_status == OPS.BLOCKED_CAPTCHA:
            pass
        elif _status_allows_auto_recovery(line.operational_status):
            line.operational_status = OPS.ACTIVE
            line.status_detail = 'بازیابی خودکار — نشست فایلینگ سالم شد'
            updates.extend(['operational_status', 'status_detail'])
        elif line.operational_status == OPS.RUNNING:
            pass
        elif line.operational_status != OPS.ACTIVE:
            line.operational_status = OPS.ACTIVE
            line.status_detail = 'فعال — همگام‌سازی خودکار'
            updates.extend(['operational_status', 'status_detail'])
        if updates:
            line.updated_at = timezone.now()
            updates.append('updated_at')
            line.save(update_fields=list(dict.fromkeys(updates)))

    if not _register_phone_in_pd_index(phone):
        raise PhoneDetectorLineError(
            f'ثبت {phone} در index.json ناموفق بود.',
            code='index_register_failed',
        )
    return line


def _pd_sessions_root():
    pd = resolve_phone_detector_dir()
    if not pd:
        return None
    return pd / 'sessions'


def _register_phone_in_pd_index(phone: str) -> bool:
    """پس از وجود فایل سشن، index را بازنویسی و عضویت شماره را تأیید کن."""
    root = _pd_sessions_root()
    if not root:
        return False
    phone = normalize_line_phone(phone)
    session_path = root / f'{phone}.json'
    if not session_path.is_file():
        logger.warning('register index: session file missing %s', phone)
        return False
    try:
        from accounts.services.phone_detector_lines import _get_engine

        registry = _get_engine().registry
        registry.save_index()
        phones = {normalize_line_phone(p) for p in registry.list_phones()}
        if phone in phones:
            return True
    except Exception:
        logger.warning('engine index register failed for %s', phone, exc_info=True)
    return _register_phone_in_pd_index_explicit(phone)


def _read_index_document(root: Path) -> dict[str, Any]:
    index_path = root / 'index.json'
    default: dict[str, Any] = {
        'active_phone': None,
        'rotate': True,
        'phones': [],
        'paused_phones': [],
    }
    if not index_path.is_file():
        return default
    try:
        loaded = json.loads(index_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return default
    if not isinstance(loaded, dict):
        return default
    return {**default, **loaded}


def _write_index_document(root: Path, data: dict[str, Any]) -> None:
    index_path = root / 'index.json'
    tmp = index_path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(index_path)


def _register_phone_in_pd_index_explicit(phone: str) -> bool:
    """Fallback: شماره را صریح به index اضافه کن اگر فایل روی دیسک هست."""
    root = _pd_sessions_root()
    if not root:
        return False
    phone = normalize_line_phone(phone)
    if not (root / f'{phone}.json').is_file():
        return False
    data = _read_index_document(root)
    phones = [normalize_line_phone(p) for p in data.get('phones') or [] if normalize_line_phone(p)]
    paused = [normalize_line_phone(p) for p in data.get('paused_phones') or [] if normalize_line_phone(p)]
    paused = [p for p in paused if p != phone]
    if phone not in phones:
        phones.append(phone)
    data['phones'] = phones
    data['paused_phones'] = paused
    if not data.get('active_phone'):
        data['active_phone'] = phone
    _write_index_document(root, data)
    return _index_contains_phone(root / 'index.json', phone)


def _index_contains_phone(index_path, phone: str) -> bool:
    phone = normalize_line_phone(phone)
    try:
        data = json.loads(Path(index_path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    return phone in {normalize_line_phone(p) for p in data.get('phones') or []}


def _read_index_phones(index_path) -> list[str]:
    try:
        data = json.loads(Path(index_path).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    return [normalize_line_phone(p) for p in data.get('phones') or [] if normalize_line_phone(p)]


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
            registry = engine.registry
            on_disk = phone in {normalize_line_phone(p) for p in registry.list_phones()}
            session_file = registry.path_for(phone)
            if on_disk or session_file.is_file():
                engine.remove_account(phone)
                still_listed = phone in {
                    normalize_line_phone(p) for p in registry.list_phones()
                }
                still_file = registry.path_for(phone).is_file()
                return not still_listed and not still_file
            return False
        return _remove_phone_from_index_only(phone)
    except Exception:
        logger.warning('evict %s from pd index failed', phone, exc_info=True)
        return False


def _phone_paused_in_index(index_path: Path, phone: str) -> bool:
    phone = normalize_line_phone(phone)
    try:
        data = json.loads(index_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    return phone in {
        normalize_line_phone(p) for p in data.get('paused_phones') or [] if normalize_line_phone(p)
    }


def _remove_phone_from_index_only(phone: str) -> bool:
    """خارج از چرخش (paused_phones) بدون حذف فایل سشن."""
    pd = resolve_phone_detector_dir()
    if not pd:
        return False
    root = pd / 'sessions'
    phone = normalize_line_phone(phone)
    if not (root / f'{phone}.json').is_file():
        return False
    data = _read_index_document(root)
    before = [normalize_line_phone(p) for p in data.get('phones') or [] if normalize_line_phone(p)]
    paused = [normalize_line_phone(p) for p in data.get('paused_phones') or [] if normalize_line_phone(p)]
    changed = False
    if phone in before:
        data['phones'] = [p for p in before if p != phone]
        changed = True
    if phone not in paused:
        paused.append(phone)
        data['paused_phones'] = paused
        changed = True
    elif not changed:
        return _phone_paused_in_index(root / 'index.json', phone)
    if data.get('active_phone') and normalize_line_phone(data['active_phone']) == phone:
        rotation = data.get('phones') or []
        data['active_phone'] = rotation[0] if rotation else None
    _write_index_document(root, data)
    return (
        not _index_contains_phone(root / 'index.json', phone)
        and _phone_paused_in_index(root / 'index.json', phone)
    )


def _line_index_in_rotation(line: PhoneDetectorExtractionLine) -> bool:
    """منبع eligibility برای index — هم‌تراز با schedulable خطوط."""
    if line.admin_hold:
        return False
    if line.operational_status in (
        OPS.BLOCKED_CAPTCHA,
        OPS.PAUSED,
        OPS.ERROR,
        OPS.EVICTED,
        OPS.RUNNING,
    ):
        return False
    if line.operational_status == OPS.COOLDOWN:
        if line.blocked_until and line.blocked_until > timezone.now():
            return False
    if line.operational_status == OPS.ACTIVE:
        return True
    if line.operational_status == OPS.COOLDOWN:
        return True
    return False


def _sync_rotation_index_from_db() -> int:
    """همگام‌سازی phones/paused_phones از DB — idempotent پس از reconcile یا probe."""
    root = _pd_sessions_root()
    if not root:
        return 0
    data = _read_index_document(root)
    on_disk = {
        normalize_line_phone(p.stem)
        for p in root.glob('09*.json')
        if normalize_line_phone(p.stem)
    }
    rotation: list[str] = []
    paused: list[str] = []
    for line in PhoneDetectorExtractionLine.objects.all().only(
        'phone',
        'operational_status',
        'admin_hold',
        'blocked_until',
    ):
        phone = normalize_line_phone(line.phone)
        if not phone or phone not in on_disk:
            continue
        if _line_index_in_rotation(line):
            if phone not in rotation:
                rotation.append(phone)
            continue
        if phone not in paused:
            paused.append(phone)
    for phone in sorted(on_disk):
        if phone not in rotation and phone not in paused:
            rotation.append(phone)
    active = normalize_line_phone(data.get('active_phone') or '')
    if active and active not in rotation:
        active = rotation[0] if rotation else None
    elif not active and rotation:
        active = rotation[0]
    prior = {
        tuple(normalize_line_phone(p) for p in data.get('phones') or []),
        tuple(normalize_line_phone(p) for p in data.get('paused_phones') or []),
    }
    data['phones'] = rotation
    data['paused_phones'] = paused
    data['active_phone'] = active
    data['rotate'] = bool(data.get('rotate', True))
    nxt = (tuple(rotation), tuple(paused))
    if prior == nxt and normalize_line_phone(data.get('active_phone') or '') == (active or ''):
        return 0
    _write_index_document(root, data)
    return 1


def _acquire_reconcile_lock(*, wait_seconds: float) -> tuple[bool, str]:
    """قفل درون‌پردازه + فایل بین‌پردازه — بدون bypass با force."""
    global _active_file_lock
    deadline = time.monotonic() + max(0.0, wait_seconds)
    while True:
        if _process_lock.acquire(blocking=False):
            break
        if time.monotonic() >= deadline:
            return False, 'process_busy'
        time.sleep(0.05)

    remaining = max(0.0, deadline - time.monotonic())
    file_lock = PdSessionsFileLock()
    if not file_lock.acquire(wait_seconds=remaining):
        _process_lock.release()
        return False, 'file_lock_busy'

    _active_file_lock = file_lock
    try:
        cache.add(
            RECONCILE_CACHE_LOCK,
            str(os.getpid()),
            timeout=RECONCILE_LOCK_TTL,
        )
    except Exception:
        logger.debug('reconcile cache lock hint skipped', exc_info=True)
    return True, ''


def _release_reconcile_lock() -> None:
    global _active_file_lock
    if _active_file_lock is not None:
        _active_file_lock.release()
        _active_file_lock = None
    try:
        cache.delete(RECONCILE_CACHE_LOCK)
    except Exception:
        pass
    try:
        _process_lock.release()
    except RuntimeError:
        pass


def reconcile_extraction_lines(
    *,
    wait_seconds: float = 0.0,
    force: bool = False,
) -> dict[str, Any]:
    """ورود، خروج و بازیابی خطوط — idempotent."""
    stats: dict[str, Any] = {
        'consent_granted': 0,
        'provisioned': 0,
        'evicted': 0,
        'recovered': 0,
        'index_adjusted': 0,
        'index_synced': 0,
        'skipped_opt_out': 0,
        'skipped_provision': 0,
    }
    if not resolve_phone_detector_dir():
        return {**stats, 'ok': False, 'reason': 'phone_detector_not_configured'}

    # force=True: حداقل ۱۲۰ث برای callers قدیمی (wait=0) — بدون دور زدن قفل
    effective_wait = wait_seconds
    if force and wait_seconds <= 0:
        effective_wait = 120.0

    acquired, lock_note = _acquire_reconcile_lock(wait_seconds=effective_wait)
    if not acquired:
        return {
            **stats,
            'ok': False,
            'skipped_concurrent': True,
            'lock': lock_note,
        }

    try:
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
                line = PhoneDetectorExtractionLine.objects.filter(
                    phone=phone,
                    line_source=SRC.FILING,
                ).first()

            if _eligible_filing_session(session):
                if line and (line.admin_hold or line.operational_status == OPS.BLOCKED_CAPTCHA):
                    stats['skipped_provision'] += 1
                    continue
                try:
                    before_status = line.operational_status if line else None
                    line = _provision_filing_session(session)
                    stats['provisioned'] += 1
                    if (
                        before_status is not None
                        and _status_allows_auto_recovery(before_status)
                        and line.operational_status == OPS.ACTIVE
                    ):
                        stats['recovered'] += 1
                except PhoneDetectorLineError as exc:
                    stats['skipped_provision'] += 1
                    logger.info('provision skip %s: %s', phone, exc.message)
                except Exception:
                    stats['skipped_provision'] += 1
                    logger.exception('provision failed %s', phone)
                continue

            if line and line.line_source == SRC.FILING:
                _evict_filing_line(line, session=session)
                stats['evicted'] += 1

        for line in PhoneDetectorExtractionLine.objects.select_related(
            'divar_account_session',
        ).all():
            if _line_should_leave_active_index(line):
                if _evict_line_from_active_rotation(line):
                    stats['index_adjusted'] += 1

        stats['index_synced'] = _sync_rotation_index_from_db()
        sync_lines_from_sessions()
        stats['ok'] = True
        if lock_note:
            stats['lock'] = lock_note
        return stats
    finally:
        _release_reconcile_lock()


@transaction.atomic
def _evict_filing_line(
    line: PhoneDetectorExtractionLine,
    *,
    session: DivarAccountSession | None,
) -> None:
    line = PhoneDetectorExtractionLine.objects.select_for_update().get(pk=line.pk)
    detail = 'خارج از چرخه — نشست فایلینگ نامعتبر یا غیرفعال'
    if session:
        detail = f'خارج از چرخه — {session.get_auth_status_display()}'
    _evict_phone_from_pd_index(line.phone, delete_session_file=True)
    line.operational_status = OPS.EVICTED
    line.status_detail = detail
    line.updated_at = timezone.now()
    line.save(update_fields=['operational_status', 'status_detail', 'updated_at'])


def _evict_line_from_active_rotation(line: PhoneDetectorExtractionLine) -> bool:
    if line.operational_status == OPS.PAUSED and line.admin_hold:
        return _remove_phone_from_index_only(line.phone)

    if line.operational_status == OPS.BLOCKED_CAPTCHA:
        delete_file = line.line_source == SRC.FILING
        if delete_file:
            return _evict_phone_from_pd_index(line.phone, delete_session_file=True)
        return _remove_phone_from_index_only(line.phone)

    if line.operational_status == OPS.ERROR:
        delete_file = line.line_source == SRC.FILING
        if delete_file:
            removed = _evict_phone_from_pd_index(line.phone, delete_session_file=True)
        else:
            removed = _remove_phone_from_index_only(line.phone)
        return removed

    if line.operational_status == OPS.EVICTED:
        return _remove_phone_from_index_only(line.phone)

    if line.line_source == SRC.FILING and line.divar_account_session_id:
        central = line.divar_account_session
        if central and _session_requires_eviction(central):
            _evict_filing_line(line, session=central)
            return True
    return False