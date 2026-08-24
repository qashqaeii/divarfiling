"""ارسال Push Notification از طریق FCM HTTP v1."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

import requests
from django.conf import settings
from django.core.cache import cache

from mobile_api.models import MobileDevice
from mobile_api.services.notification_catalog import get_spec

logger = logging.getLogger(__name__)

FCM_SCOPE = 'https://www.googleapis.com/auth/firebase.messaging'
UNREGISTERED_CODES = frozenset({'UNREGISTERED', 'INVALID_ARGUMENT', 'NOT_FOUND'})

# timeout کوتاه برای سرور ایران — connect/read جدا
FCM_CONNECT_TIMEOUT = 3
FCM_READ_TIMEOUT = 5
FCM_NETWORK_RETRIES = 1
FCM_RETRY_BACKOFF_SEC = 0.5

FCM_CIRCUIT_FAIL_KEY = 'fcm:circuit:failures'
FCM_CIRCUIT_OPEN_KEY = 'fcm:circuit:open'
FCM_CIRCUIT_FAIL_THRESHOLD = 3
FCM_CIRCUIT_FAIL_WINDOW = 60
FCM_CIRCUIT_COOLDOWN = 120

_oauth_token_cache: Dict[str, Any] = {'token': None, 'expires_at': 0.0}


def _fcm_project_id() -> str:
    return getattr(settings, 'FCM_PROJECT_ID', '') or 'divarfiling'


def _fcm_service_account_file() -> str:
    return getattr(settings, 'FCM_SERVICE_ACCOUNT_FILE', '') or ''


def _fcm_server_key() -> str:
    return getattr(settings, 'FCM_SERVER_KEY', '') or ''


def _fcm_http_timeout() -> Tuple[float, float]:
    connect = getattr(settings, 'FCM_CONNECT_TIMEOUT', FCM_CONNECT_TIMEOUT)
    read = getattr(settings, 'FCM_READ_TIMEOUT', FCM_READ_TIMEOUT)
    return float(connect), float(read)


def _circuit_is_open() -> bool:
    return bool(cache.get(FCM_CIRCUIT_OPEN_KEY))


def _record_fcm_failure(reason: str) -> None:
    try:
        failures = cache.get(FCM_CIRCUIT_FAIL_KEY, 0) + 1
        cache.set(FCM_CIRCUIT_FAIL_KEY, failures, FCM_CIRCUIT_FAIL_WINDOW)
        if failures >= FCM_CIRCUIT_FAIL_THRESHOLD:
            cache.set(FCM_CIRCUIT_OPEN_KEY, True, FCM_CIRCUIT_COOLDOWN)
            logger.warning(
                'FCM circuit opened cooldown_sec=%s reason=%s failures=%s',
                FCM_CIRCUIT_COOLDOWN,
                reason,
                failures,
            )
    except Exception:
        logger.exception('FCM circuit breaker update failed')


def _get_v1_access_token(*, force_refresh: bool = False) -> Optional[str]:
    path = _fcm_service_account_file()
    if not path:
        return None

    now = time.time()
    cached = _oauth_token_cache.get('token')
    expires_at = float(_oauth_token_cache.get('expires_at') or 0)
    if not force_refresh and cached and expires_at > now + 60:
        return cached

    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests

        creds = service_account.Credentials.from_service_account_file(
            path,
            scopes=[FCM_SCOPE],
        )
        creds.refresh(google.auth.transport.requests.Request(timeout=_fcm_http_timeout()))
        token = creds.token
        expiry = creds.expiry.timestamp() if getattr(creds, 'expiry', None) else now + 3300
        _oauth_token_cache['token'] = token
        _oauth_token_cache['expires_at'] = expiry
        return token
    except requests.Timeout:
        logger.warning('FCM OAuth token refresh timeout (oauth2.googleapis.com)')
        _record_fcm_failure('oauth_timeout')
    except requests.RequestException as exc:
        logger.warning('FCM OAuth token refresh network error: %s', exc)
        _record_fcm_failure('oauth_network')
    except Exception:
        logger.exception('FCM v1 token refresh failed')
        _record_fcm_failure('oauth_error')
    return None


def _invalidate_fcm_token(token: str) -> None:
    updated = MobileDevice.objects.filter(fcm_token=token).update(fcm_token='')
    if updated:
        logger.info('Cleared %s stale FCM token(s)', updated)


def _extract_fcm_error_code(payload: Dict[str, Any]) -> str:
    details = payload.get('error', {}).get('details') or []
    for item in details:
        if not isinstance(item, dict):
            continue
        code = item.get('errorCode') or item.get('error_code')
        if code:
            return str(code)
    return ''


def _active_tokens_for_user(user) -> list:
    return list(
        MobileDevice.objects.filter(user=user, is_active=True)
        .exclude(fcm_token='')
        .values_list('fcm_token', flat=True)
        .distinct()
    )


def send_push_to_user(
    user,
    *,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
    display_notification: Optional[bool] = None,
) -> int:
    """ارسال به دستگاه‌های فعال کاربر. تعداد پذیرش FCM را برمی‌گرداند (نه نمایش روی گوشی)."""
    stats = send_push_to_tokens(
        _active_tokens_for_user(user),
        title=title,
        body=body,
        data=data,
        display_notification=display_notification,
    )
    return stats['success']


def send_push_to_tokens(
    tokens,
    *,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
    display_notification: Optional[bool] = None,
) -> Dict[str, int]:
    unique = [t for t in dict.fromkeys(tokens) if t]
    if not unique:
        return {'attempted': 0, 'success': 0, 'failure': 0}

    if _circuit_is_open():
        logger.warning(
            'FCM circuit open — skipping push attempted=%s endpoint=fcm.googleapis.com',
            len(unique),
        )
        return {'attempted': len(unique), 'success': 0, 'failure': len(unique)}

    payload_data = {k: str(v) for k, v in (data or {}).items() if v is not None}
    payload_data.setdefault('title', title)
    payload_data.setdefault('body', body or title)
    ntype = payload_data.get('type', '')
    spec = get_spec(ntype)
    if display_notification is None:
        display_notification = spec.display_fcm_notification
    payload_data.setdefault('channel', spec.channel)
    payload_data.setdefault('priority', spec.priority)

    access_token = _get_v1_access_token()
    success = 0
    for token in unique:
        ok = _send_fcm_v1(
            token,
            title,
            body,
            payload_data,
            display_notification=display_notification,
            channel=spec.channel,
            access_token=access_token,
        )
        if ok:
            success += 1
    return {
        'attempted': len(unique),
        'success': success,
        'failure': len(unique) - success,
    }


def send_welcome_push(user) -> int:
    """سازگاری قدیمی — welcome از create_notification ساخته می‌شود."""
    from mobile_api.services.notification_copy import welcome_message

    title, body = welcome_message()
    return send_push_to_user(
        user,
        title=title,
        body=body,
        data={
            'type': 'welcome',
            'deep_link': 'divarfiling://home',
        },
        display_notification=True,
    )


def _send_fcm_v1(
    token: str,
    title: str,
    body: str,
    data: Dict[str, str],
    *,
    display_notification: bool = False,
    channel: str = '',
    access_token: Optional[str] = None,
) -> bool:
    access = access_token or _get_v1_access_token()
    if not access:
        return False

    project_id = _fcm_project_id()
    url = f'https://fcm.googleapis.com/v1/projects/{project_id}/messages:send'
    android: Dict[str, Any] = {
        'priority': 'HIGH',
        'ttl': '86400s',
    }
    if display_notification:
        android['notification'] = {
            'title': title,
            'body': body or title,
            'channel_id': channel or data.get('channel', ''),
        }
    message = {
        'message': {
            'token': token,
            'data': data,
            'android': android,
        },
    }

    attempts = FCM_NETWORK_RETRIES + 1
    for attempt in range(attempts):
        try:
            resp = requests.post(
                url,
                headers={
                    'Authorization': f'Bearer {access}',
                    'Content-Type': 'application/json',
                },
                json=message,
                timeout=_fcm_http_timeout(),
            )
            if resp.status_code == 200:
                return True
            if resp.status_code == 401 and attempt == 0:
                access = _get_v1_access_token(force_refresh=True)
                if access:
                    continue
            try:
                payload = resp.json()
            except ValueError:
                payload = {}
            error_code = _extract_fcm_error_code(payload)
            if resp.status_code in (404, 400) and error_code in UNREGISTERED_CODES:
                logger.info('FCM token unregistered code=%s; clearing from database', error_code)
                _invalidate_fcm_token(token)
                return False
            logger.warning(
                'FCM v1 HTTP error status=%s code=%s endpoint=fcm.googleapis.com',
                resp.status_code,
                error_code or '-',
            )
            return False
        except requests.Timeout:
            logger.warning(
                'FCM v1 network timeout endpoint=fcm.googleapis.com attempt=%s/%s',
                attempt + 1,
                attempts,
            )
            _record_fcm_failure('send_timeout')
            if attempt < attempts - 1:
                time.sleep(FCM_RETRY_BACKOFF_SEC * (2 ** attempt))
                continue
            return False
        except requests.RequestException as exc:
            logger.warning('FCM v1 network error endpoint=fcm.googleapis.com: %s', exc)
            _record_fcm_failure('send_network')
            if attempt < attempts - 1:
                time.sleep(FCM_RETRY_BACKOFF_SEC * (2 ** attempt))
                continue
            return False
        except Exception:
            logger.exception('FCM v1 send error')
            return False
    return False


def _send_fcm_legacy(token: str, title: str, body: str, data: Dict[str, str]) -> bool:
    server_key = _fcm_server_key()
    if not server_key:
        return False
    try:
        resp = requests.post(
            'https://fcm.googleapis.com/fcm/send',
            headers={
                'Authorization': f'key={server_key}',
                'Content-Type': 'application/json',
            },
            json={
                'to': token,
                'data': data,
                'priority': 'high',
            },
            timeout=_fcm_http_timeout(),
        )
        if resp.status_code == 200:
            result = resp.json()
            if result.get('success', 0) > 0:
                return True
            failure = (result.get('results') or [{}])[0]
            error = failure.get('error', '')
            if error in ('InvalidRegistration', 'NotRegistered', 'MismatchSenderId'):
                logger.info('FCM legacy token unregistered (%s); clearing from database', error)
                _invalidate_fcm_token(token)
                return False
            logger.warning('FCM legacy send failed: %s', result)
        else:
            logger.warning('FCM legacy HTTP %s: %s', resp.status_code, resp.text[:200])
    except requests.Timeout:
        logger.warning('FCM legacy network timeout endpoint=fcm.googleapis.com/fcm/send')
        _record_fcm_failure('legacy_timeout')
    except requests.RequestException as exc:
        logger.warning('FCM legacy network error: %s', exc)
        _record_fcm_failure('legacy_network')
    except Exception:
        logger.exception('FCM legacy send error')
    return False
