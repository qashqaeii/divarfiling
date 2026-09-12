"""مدیریت خطوط (سشن‌های دیوار) phone-detector از پنل LAC."""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from django.conf import settings

_engine_lock = threading.Lock()
_engine = None
OTP_PENDING_TTL_SECONDS = 300


class PhoneDetectorLineError(Exception):
    def __init__(self, message: str, *, code: str = 'line_error'):
        self.message = message
        self.code = code
        super().__init__(message)


def resolve_phone_detector_dir() -> Optional[Path]:
    """مسیر checkout phone-detector روی سرور."""
    raw = (getattr(settings, 'PHONE_DETECTOR_DIR', None) or '').strip()
    candidates: list[Path] = []
    if raw:
        candidates.append(Path(raw).expanduser())
    base = Path(getattr(settings, 'BASE_DIR', Path.cwd()))
    candidates.extend([
        base.parent / 'phone-detector',
        Path('/root/phone-detector'),
    ])
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.is_dir() and (resolved / 'engine.py').is_file():
            return resolved
    return None


def phone_detector_available() -> bool:
    return resolve_phone_detector_dir() is not None


def sessions_root() -> Path:
    pd = resolve_phone_detector_dir()
    if not pd:
        raise PhoneDetectorLineError(
            'phone-detector یافت نشد — PHONE_DETECTOR_DIR را در .env تنظیم کنید.',
            code='not_configured',
        )
    return pd / 'sessions'


def _ensure_pd_path() -> Path:
    pd = resolve_phone_detector_dir()
    if not pd:
        raise PhoneDetectorLineError(
            'phone-detector یافت نشد — PHONE_DETECTOR_DIR را در .env تنظیم کنید.',
            code='not_configured',
        )
    return pd


def _get_engine():
    global _engine
    with _engine_lock:
        if _engine is None:
            pd_path = _ensure_pd_path()
            if str(pd_path) not in sys.path:
                sys.path.insert(0, str(pd_path))
            from engine import PhoneDetectorEngine

            _engine = PhoneDetectorEngine(
                places_path=pd_path.parent / 'config' / 'places-web.json',
                session_path=pd_path / 'session.json',
                sessions_dir=pd_path / 'sessions',
                output_dir=pd_path / 'output',
            )
        return _engine


def _import_pd_main():
    pd_path = _ensure_pd_path()
    if str(pd_path) not in sys.path:
        sys.path.insert(0, str(pd_path))
    from main import normalize_phone, set_cookie

    return normalize_phone, set_cookie


def _otp_pending_dir() -> Path:
    root = sessions_root() / '_otp_pending'
    root.mkdir(parents=True, exist_ok=True)
    return root


def _otp_pending_path(phone: str) -> Path:
    normalize_phone, _ = _import_pd_main()
    return _otp_pending_dir() / f'{normalize_phone(phone)}.json'


def _export_otp_pending(engine) -> dict[str, Any]:
    normalize_phone, _ = _import_pd_main()
    st = engine.state
    phone = normalize_phone(st.phone or engine.auth.get_session_phone() or '')
    cookies: list[dict[str, str]] = []
    for cookie in engine.session.cookies:
        cookies.append({
            'name': cookie.name,
            'value': cookie.value,
            'domain': cookie.domain or 'divar.ir',
            'path': cookie.path or '/',
        })
    return {
        'saved_at': datetime.now(timezone.utc).isoformat(),
        'phone': phone,
        'pre_auth_session_id': st.pre_auth_session_id,
        'device_id': st.device_id,
        'player_id': st.player_id,
        'did': st.did,
        'cdid': st.cdid,
        'city_slug': st.city_slug,
        'cookies': cookies,
    }


def _save_otp_pending(engine, phone: str) -> None:
    payload = _export_otp_pending(engine)
    normalize_phone, _ = _import_pd_main()
    payload['phone'] = normalize_phone(phone or payload.get('phone') or '')
    if not payload.get('pre_auth_session_id'):
        return
    path = _otp_pending_path(payload['phone'])
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def _load_otp_pending(phone: str) -> Optional[dict[str, Any]]:
    normalize_phone, _ = _import_pd_main()
    key = normalize_phone(phone or '')
    if not key:
        return None
    path = _otp_pending_path(key)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    saved_at = data.get('saved_at')
    if saved_at:
        try:
            saved = datetime.fromisoformat(str(saved_at).replace('Z', '+00:00'))
            age = (datetime.now(timezone.utc) - saved).total_seconds()
            if age > OTP_PENDING_TTL_SECONDS:
                path.unlink(missing_ok=True)
                return None
        except (TypeError, ValueError):
            pass
    if not data.get('pre_auth_session_id'):
        return None
    return data


def _clear_otp_pending(phone: str) -> None:
    normalize_phone, _ = _import_pd_main()
    key = normalize_phone(phone or '')
    if not key:
        return
    _otp_pending_path(key).unlink(missing_ok=True)


def _restore_otp_pending(engine, payload: dict[str, Any]) -> None:
    normalize_phone, set_cookie = _import_pd_main()
    phone = normalize_phone(payload.get('phone') or '')
    pending = engine._make_slot(phone, blank=True)
    pending.phone = phone
    pending.state.pre_auth_session_id = payload.get('pre_auth_session_id')
    if payload.get('device_id'):
        pending.state.device_id = str(payload['device_id'])
    if payload.get('player_id'):
        pending.state.player_id = str(payload['player_id'])
    if payload.get('did'):
        pending.state.did = str(payload['did'])
    if payload.get('cdid'):
        pending.state.cdid = str(payload['cdid'])
    if payload.get('city_slug'):
        pending.state.city_slug = str(payload['city_slug'])
    pending.state.phone = phone
    pending.session.cookies.clear()
    for raw in payload.get('cookies') or []:
        if not isinstance(raw, dict):
            continue
        name = raw.get('name')
        value = raw.get('value')
        if not name or value is None:
            continue
        set_cookie(
            pending.session,
            str(name),
            str(value),
            domain=str(raw.get('domain') or 'divar.ir'),
            path=str(raw.get('path') or '/'),
        )
    engine._bind_slot(pending)


def _ensure_otp_pending_loaded(engine, phone: str) -> None:
    normalize_phone, _ = _import_pd_main()
    key = normalize_phone(phone or '')
    current_phone = normalize_phone(engine.state.phone or engine.auth.get_session_phone() or '')
    if engine.state.pre_auth_session_id and current_phone == key:
        return
    payload = _load_otp_pending(key)
    if payload:
        _restore_otp_pending(engine, payload)
        return
    if not engine.state.pre_auth_session_id:
        raise PhoneDetectorLineError(
            'نشست OTP منقضی یا از بین رفته — دوباره «ارسال کد» را بزنید.',
            code='otp_session_missing',
        )


def _cookie_value(session_data: dict, name: str) -> str:
    for cookie in session_data.get('cookies') or []:
        if isinstance(cookie, dict) and cookie.get('name') == name:
            return str(cookie.get('value') or '')
    return ''


def _jwt_expiry_iso(token: str) -> Optional[str]:
    if not token:
        return None
    try:
        parts = token.split('.')
        if len(parts) < 2:
            return None
        import base64

        payload_b64 = parts[1]
        padding = '=' * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
        exp = payload.get('exp')
        if exp is None:
            return None
        return datetime.fromtimestamp(float(exp), tz=timezone.utc).isoformat()
    except (ValueError, TypeError, json.JSONDecodeError, OSError):
        return None


def _session_health_from_file(session_path: Path) -> dict[str, Any]:
    if not session_path.is_file():
        return {
            'has_file': False,
            'status': 'missing',
            'status_label': 'بدون سشن',
            'ok': False,
            'needs_relogin': True,
        }
    try:
        data = json.loads(session_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {
            'has_file': True,
            'status': 'corrupt',
            'status_label': 'فایل خراب',
            'ok': False,
            'needs_relogin': True,
        }
    if not isinstance(data, dict):
        return {
            'has_file': True,
            'status': 'corrupt',
            'status_label': 'فایل خراب',
            'ok': False,
            'needs_relogin': True,
        }

    access = _cookie_value(data, 'sAccessToken')
    refresh = _cookie_value(data, 'sRefreshToken')
    saved_at = data.get('saved_at')
    expires_at = _jwt_expiry_iso(access)

    expired = False
    if access:
        pd_path = resolve_phone_detector_dir()
        if pd_path and str(pd_path) not in sys.path:
            sys.path.insert(0, str(pd_path))
        try:
            from main import jwt_is_expired

            expired = jwt_is_expired(access)
        except Exception:
            expired = False
    elif not refresh:
        expired = True

    if not access and not refresh:
        status = 'empty'
        label = 'بدون توکن'
        ok = False
    elif expired:
        status = 'expired'
        label = 'نیاز به ورود مجدد'
        ok = False
    else:
        status = 'active'
        label = 'فعال'
        ok = True

    return {
        'has_file': True,
        'status': status,
        'status_label': label,
        'ok': ok,
        'needs_relogin': not ok,
        'saved_at': saved_at,
        'expires_at': expires_at,
        'cookie_count': len(data.get('cookies') or []),
    }


def _load_index(root: Path) -> dict[str, Any]:
    index_path = root / 'index.json'
    default = {'active_phone': None, 'rotate': True, 'phones': []}
    if not index_path.is_file():
        phones = sorted(p.stem for p in root.glob('09*.json'))
        return {**default, 'phones': phones}
    try:
        data = json.loads(index_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        phones = sorted(p.stem for p in root.glob('09*.json'))
        return {**default, 'phones': phones}
    if not isinstance(data, dict):
        phones = sorted(p.stem for p in root.glob('09*.json'))
        return {**default, 'phones': phones}

    on_disk = {p.stem for p in root.glob('09*.json')}
    phones: list[str] = []
    for raw in data.get('phones') or []:
        key = str(raw).strip()
        if key and key in on_disk and key not in phones:
            phones.append(key)
    for phone in sorted(on_disk):
        if phone not in phones:
            phones.append(phone)
    return {
        'active_phone': str(data['active_phone']).strip() if data.get('active_phone') else None,
        'rotate': bool(data.get('rotate', True)),
        'phones': phones,
    }


def _merge_engine_accounts(lines: list[dict], engine_info: dict) -> list[dict]:
    by_phone = {row['phone']: row for row in lines}
    for acc in engine_info.get('accounts') or []:
        phone = str(acc.get('phone') or '').strip()
        if not phone or phone not in by_phone:
            continue
        row = by_phone[phone]
        if acc.get('hip_blocked'):
            row['status'] = 'rate_limited'
            row['status_label'] = 'محدودیت / کپچا'
            row['ok'] = False
            row['hip_blocked'] = True
        elif acc.get('needs_relogin') or not acc.get('ok'):
            row['status'] = 'expired'
            row['status_label'] = 'نیاز به ورود مجدد'
            row['ok'] = False
            row['needs_relogin'] = True
        elif acc.get('ok'):
            row['status'] = 'active'
            row['status_label'] = 'فعال'
            row['ok'] = True
            row['needs_relogin'] = False
        row['in_rotation'] = bool(acc.get('in_rotation'))
        row['engine_active'] = bool(acc.get('active'))
    return lines


def list_lines(*, probe: bool = False) -> dict[str, Any]:
    """لیست خطوط ذخیره‌شده در sessions/ phone-detector."""
    pd = resolve_phone_detector_dir()
    if not pd:
        return {
            'ok': False,
            'configured': False,
            'error': 'phone-detector یافت نشد',
            'lines': [],
            'rotate': True,
            'active_phone': None,
            'sessions_dir': '',
        }

    root = pd / 'sessions'
    index = _load_index(root)
    lines: list[dict[str, Any]] = []

    for phone in index['phones']:
        health = _session_health_from_file(root / f'{phone}.json')
        lines.append({
            'phone': phone,
            'is_active': phone == index.get('active_phone'),
            'hip_blocked': False,
            'in_rotation': bool(health.get('ok')),
            'engine_active': phone == index.get('active_phone'),
            **health,
        })

    engine_info: dict[str, Any] = {}
    if probe and lines:
        try:
            engine = _get_engine()
            engine_info = engine.list_accounts()
            lines = _merge_engine_accounts(lines, engine_info)
        except Exception as exc:
            engine_info = {'probe_error': str(exc)}

    healthy = sum(1 for row in lines if row.get('ok') and not row.get('hip_blocked'))
    return {
        'ok': True,
        'configured': True,
        'lines': lines,
        'rotate': index.get('rotate', True),
        'active_phone': index.get('active_phone'),
        'sessions_dir': str(root),
        'phone_detector_dir': str(pd),
        'total': len(lines),
        'healthy_count': healthy,
        'needs_login': engine_info.get('needs_login') if engine_info else [
            row['phone'] for row in lines if row.get('needs_relogin')
        ],
        'probe_error': engine_info.get('probe_error'),
    }


def begin_add_line() -> dict[str, Any]:
    engine = _get_engine()
    return engine.begin_add_account()


def send_line_otp(phone: str) -> dict[str, Any]:
    phone = (phone or '').strip()
    if not phone:
        raise PhoneDetectorLineError('شماره موبایل الزامی است.', code='missing_phone')
    engine = _get_engine()
    try:
        result = engine.send_otp(phone)
        _save_otp_pending(engine, result.get('phone') or phone)
        return result
    except Exception as exc:
        raise PhoneDetectorLineError(str(exc), code='otp_send_failed') from exc


def verify_line_otp(*, otp: str, phone: str = '') -> dict[str, Any]:
    otp = (otp or '').strip()
    if not otp:
        raise PhoneDetectorLineError('کد تأیید الزامی است.', code='missing_otp')
    phone = (phone or '').strip()
    if not phone:
        raise PhoneDetectorLineError('شماره موبایل الزامی است.', code='missing_phone')
    engine = _get_engine()
    try:
        _ensure_otp_pending_loaded(engine, phone)
        result = engine.verify_otp(otp, phone=phone)
        _clear_otp_pending(result.get('phone') or phone)
        payload = list_lines(probe=False)
        return {**result, **payload}
    except PhoneDetectorLineError:
        raise
    except Exception as exc:
        raise PhoneDetectorLineError(str(exc), code='otp_verify_failed') from exc


def remove_line(phone: str) -> dict[str, Any]:
    phone = (phone or '').strip()
    if not phone:
        raise PhoneDetectorLineError('شماره خط الزامی است.', code='missing_phone')
    engine = _get_engine()
    try:
        result = engine.remove_account(phone)
        payload = list_lines(probe=False)
        return {**result, **payload}
    except Exception as exc:
        raise PhoneDetectorLineError(str(exc), code='remove_failed') from exc


def switch_line(phone: str) -> dict[str, Any]:
    phone = (phone or '').strip()
    if not phone:
        raise PhoneDetectorLineError('شماره خط الزامی است.', code='missing_phone')
    engine = _get_engine()
    try:
        result = engine.switch_account(phone)
        payload = list_lines(probe=False)
        return {**result, **payload}
    except Exception as exc:
        raise PhoneDetectorLineError(str(exc), code='switch_failed') from exc


def set_line_rotate(*, enabled: bool) -> dict[str, Any]:
    engine = _get_engine()
    result = engine.set_rotate(bool(enabled))
    payload = list_lines(probe=False)
    return {**result, **payload}


def handle_line_action(action: str, data: dict) -> dict[str, Any]:
    action = (action or '').strip().lower()
    if action == 'begin_add':
        return begin_add_line()
    if action == 'send_otp':
        return send_line_otp(data.get('phone') or '')
    if action == 'verify_otp':
        return verify_line_otp(otp=data.get('otp') or '', phone=data.get('phone') or '')
    if action == 'remove':
        return remove_line(data.get('phone') or '')
    if action == 'switch':
        return switch_line(data.get('phone') or '')
    if action == 'rotate':
        enabled = data.get('enabled')
        if enabled is None:
            enabled = data.get('rotate')
        return set_line_rotate(enabled=bool(enabled))
    raise PhoneDetectorLineError(f'عملیات نامعتبر: {action}', code='invalid_action')
