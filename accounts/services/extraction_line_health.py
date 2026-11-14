"""ممیزی read-only و Probe سبک خطوط استخراج — بدون ثبت توکن در لاگ."""
from __future__ import annotations

import logging
from typing import Any, Literal

from django.utils import timezone

from accounts.models import PhoneDetectorExtractionLine
from accounts.services.phone_detector_line_ops import (
    normalize_line_phone,
    probe_and_reactivate_line,
    _line_central_session_allows_activation,
)
from accounts.services.phone_detector_lines import (
    PhoneDetectorLineError,
    session_file_exists,
)
from workspace.divar_session_models import DivarAccountSession
from workspace.services.divar_session.pd_sync_block import is_phone_detector_file_sync_blocked

logger = logging.getLogger(__name__)

OPS = PhoneDetectorExtractionLine.OperationalStatus
SRC = PhoneDetectorExtractionLine.LineSource

LineVerdict = Literal[
    'healthy',
    'captcha',
    'needs_otp',
    'session_expired',
    'session_file_missing',
    'api_error',
    'admin_paused',
    'evicted',
    'sync_blocked',
    'unknown',
]

VERDICT_LABELS_FA: dict[str, str] = {
    'healthy': 'سالم',
    'captcha': 'کپچا',
    'needs_otp': 'نیازمند OTP',
    'session_expired': 'نشست منقضی',
    'session_file_missing': 'فایل نشست ناموجود',
    'api_error': 'خطای API',
    'admin_paused': 'توقف مدیر',
    'evicted': 'خارج از چرخه',
    'sync_blocked': 'مسدود همگام‌سازی',
    'unknown': 'نامشخص',
}


def _central_auth_verdict(session: DivarAccountSession | None) -> LineVerdict | None:
    if not session:
        return None
    status = session.auth_status
    if status == DivarAccountSession.AuthStatus.CONNECTED:
        return None
    if status in (
        DivarAccountSession.AuthStatus.PENDING_OTP,
        DivarAccountSession.AuthStatus.CAPTCHA_REQUIRED,
    ):
        return 'needs_otp'
    if status in (
        DivarAccountSession.AuthStatus.EXPIRED,
        DivarAccountSession.AuthStatus.DISCONNECTED,
    ):
        return 'session_expired'
    if status == DivarAccountSession.AuthStatus.ERROR:
        return 'api_error'
    return 'session_expired'


def _offline_verdict(line: PhoneDetectorExtractionLine) -> LineVerdict:
    phone = normalize_line_phone(line.phone)
    if line.admin_hold or line.operational_status == OPS.PAUSED:
        return 'admin_paused'
    if is_phone_detector_file_sync_blocked(phone):
        return 'sync_blocked'
    if not session_file_exists(phone):
        return 'session_file_missing'
    central = line.divar_account_session if line.divar_account_session_id else None
    central_v = _central_auth_verdict(central)
    if central_v:
        return central_v
    if line.operational_status == OPS.EVICTED:
        return 'evicted'
    if line.operational_status == OPS.BLOCKED_CAPTCHA:
        return 'captcha'
    if line.operational_status == OPS.ERROR:
        return 'needs_otp'
    if not _line_central_session_allows_activation(line):
        return 'session_expired'
    return 'unknown'


def _probe_result_to_verdict(probe: dict[str, Any]) -> LineVerdict:
    if probe.get('ok'):
        return 'healthy'
    code = str(probe.get('code') or '')
    if code == 'missing':
        return 'session_file_missing'
    if code == 'needs_relogin':
        return 'needs_otp'
    if code == 'still_blocked':
        return 'captcha'
    if code in ('probe_failed', 'probe_unavailable'):
        return 'api_error'
    return 'unknown'


def _filing_owner_allows_reactivation(line: PhoneDetectorExtractionLine) -> tuple[bool, str]:
    if line.line_source != SRC.FILING or not line.divar_account_session_id:
        return True, ''
    session = line.divar_account_session
    if session.extraction_auto_opt_out:
        return False, 'کاربر از استخراج خودکار انصراف داده است'
    if not session.phone_detector_consent:
        return False, 'رضایت phone-detector ثبت نشده است'
    if session.auth_status != DivarAccountSession.AuthStatus.CONNECTED:
        return False, 'نشست مرکزی متصل نیست'
    if not (session.encrypted_session or '').strip():
        return False, 'نشست مرکزی خالی است'
    return True, ''


def probe_line_live(phone: str) -> dict[str, Any]:
    """Probe زنده — auth سپس read-only؛ تحت قفل sessions (بدون لاگ توکن)."""
    from accounts.services.pd_sessions_file_lock import (
        DEFAULT_MUTATION_WAIT,
        run_pd_sessions_mutation,
    )
    from accounts.services.phone_detector_lines import _get_engine

    phone = normalize_line_phone(phone)
    if not session_file_exists(phone):
        return {
            'ok': False,
            'code': 'missing',
            'message': 'فایل نشست روی دیسک یافت نشد',
        }

    def _probe() -> dict[str, Any]:
        return _get_engine().probe_line_reactivation(phone)

    try:
        return run_pd_sessions_mutation(_probe, wait_seconds=DEFAULT_MUTATION_WAIT)
    except RuntimeError as exc:
        return {
            'ok': False,
            'code': 'probe_unavailable',
            'message': str(exc),
        }
    except Exception as exc:
        logger.info('probe failed for %s: %s', phone, exc.__class__.__name__)
        return {
            'ok': False,
            'code': 'probe_failed',
            'message': f'بررسی ناموفق: {exc.__class__.__name__}',
        }


def audit_extraction_line(
    line: PhoneDetectorExtractionLine,
    *,
    probe: bool = False,
) -> dict[str, Any]:
    """ممیزی یک خط — پیش‌فرض بدون تماس شبکه."""
    phone = normalize_line_phone(line.phone)
    offline = _offline_verdict(line)
    result: dict[str, Any] = {
        'phone': phone,
        'line_source': line.line_source,
        'operational_status': line.operational_status,
        'verdict': offline,
        'verdict_label': VERDICT_LABELS_FA.get(offline, offline),
        'probed': False,
        'has_session_file': session_file_exists(phone),
        'central_auth': (
            line.divar_account_session.auth_status
            if line.divar_account_session_id
            else None
        ),
        'detail': line.status_detail or '',
        'checked_at': timezone.now().isoformat(),
    }
    if offline in ('admin_paused', 'sync_blocked', 'session_file_missing', 'evicted'):
        return result
    central_v = _central_auth_verdict(
        line.divar_account_session if line.divar_account_session_id else None,
    )
    if central_v and central_v != offline:
        result['verdict'] = central_v
        result['verdict_label'] = VERDICT_LABELS_FA.get(central_v, central_v)
        return result
    if not probe:
        if offline == 'unknown' and line.operational_status == OPS.ACTIVE:
            result['detail'] = (result['detail'] or '') + ' — برای تأیید نهایی Probe لازم است'
        return result

    probe_out = probe_line_live(phone)
    result['probed'] = True
    verdict = _probe_result_to_verdict(probe_out)
    result['verdict'] = verdict
    result['verdict_label'] = VERDICT_LABELS_FA.get(verdict, verdict)
    result['probe_code'] = probe_out.get('code')
    result['detail'] = str(probe_out.get('message') or result['detail'])
    return result


def audit_all_extraction_lines(
    *,
    probe: bool = False,
    phone: str | None = None,
) -> list[dict[str, Any]]:
    qs = PhoneDetectorExtractionLine.objects.select_related('divar_account_session').order_by(
        'line_index',
        'phone',
    )
    if phone:
        qs = qs.filter(phone=normalize_line_phone(phone))
    return [audit_extraction_line(row, probe=probe) for row in qs]


def reactivate_healthy_line(phone: str) -> dict[str, Any]:
    """فقط پس از Probe موفق و تأیید مالک نشست (خط فایلینگ)."""
    phone = normalize_line_phone(phone)
    line = PhoneDetectorExtractionLine.objects.select_related('divar_account_session').filter(
        phone=phone,
    ).first()
    if not line:
        raise PhoneDetectorLineError('خط یافت نشد.', code='line_not_found')
    audit = audit_extraction_line(line, probe=True)
    if audit['verdict'] != 'healthy':
        raise PhoneDetectorLineError(
            f"خط سالم نیست — نتیجه: {audit['verdict_label']}",
            code='not_healthy',
        )
    allowed, reason = _filing_owner_allows_reactivation(line)
    if not allowed:
        raise PhoneDetectorLineError(reason, code='owner_not_confirmed')
    return probe_and_reactivate_line(phone)