"""ارسال Push Notification از طریق FCM HTTP v1 (و fallback قدیمی)."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import requests
from django.conf import settings

from mobile_api.models import MobileDevice
from mobile_api.services.notification_copy import welcome_message

logger = logging.getLogger(__name__)

FCM_SCOPE = 'https://www.googleapis.com/auth/firebase.messaging'
UNREGISTERED_CODES = frozenset({'UNREGISTERED', 'INVALID_ARGUMENT', 'NOT_FOUND'})


def _fcm_project_id() -> str:
    return getattr(settings, 'FCM_PROJECT_ID', '') or 'divarfiling'


def _fcm_service_account_file() -> str:
    return getattr(settings, 'FCM_SERVICE_ACCOUNT_FILE', '') or ''


def _fcm_server_key() -> str:
    return getattr(settings, 'FCM_SERVER_KEY', '') or ''


def _get_v1_access_token() -> Optional[str]:
    path = _fcm_service_account_file()
    if not path:
        return None
    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests

        creds = service_account.Credentials.from_service_account_file(
            path,
            scopes=[FCM_SCOPE],
        )
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token
    except Exception:
        logger.exception('FCM v1 token refresh failed')
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


def send_push_to_user(
    user,
    *,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
) -> int:
    """ارسال به تمام دستگاه‌های کاربر. تعداد موفق را برمی‌گرداند."""
    tokens = list(
        MobileDevice.objects.filter(user=user)
        .exclude(fcm_token='')
        .values_list('fcm_token', flat=True)
        .distinct()
    )
    if not tokens:
        return 0

    payload_data = {k: str(v) for k, v in (data or {}).items()}
    payload_data.setdefault('title', title)
    payload_data.setdefault('body', body or title)
    sent = 0
    for token in tokens:
        if _send_fcm_v1(token, title, body, payload_data) or _send_fcm_legacy(token, title, body, payload_data):
            sent += 1
    return sent


def send_welcome_push(user) -> int:
    """Push خوش‌آمدگویی — فقط وقتی fcm_token برای اولین‌بار ثبت می‌شود."""
    title, body = welcome_message()
    return send_push_to_user(
        user,
        title=title,
        body=body,
        data={
            'type': 'welcome',
            'deep_link': 'divarfiling://home',
        },
    )


def _send_fcm_v1(token: str, title: str, body: str, data: Dict[str, str]) -> bool:
    access = _get_v1_access_token()
    if not access:
        return False
    project_id = _fcm_project_id()
    url = f'https://fcm.googleapis.com/v1/projects/{project_id}/messages:send'
    message = {
        'message': {
            'token': token,
            'notification': {'title': title, 'body': body or title},
            'data': data,
            'android': {'priority': 'HIGH'},
        },
    }
    try:
        resp = requests.post(
            url,
            headers={
                'Authorization': f'Bearer {access}',
                'Content-Type': 'application/json',
            },
            json=message,
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        error_code = _extract_fcm_error_code(payload)
        if resp.status_code in (404, 400) and error_code in UNREGISTERED_CODES:
            logger.info('FCM token unregistered; clearing from database')
            _invalidate_fcm_token(token)
            return False
        logger.warning('FCM v1 HTTP %s: %s', resp.status_code, resp.text[:300])
    except Exception:
        logger.exception('FCM v1 send error')
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
                'notification': {
                    'title': title,
                    'body': body,
                    'sound': 'default',
                },
                'data': data,
                'priority': 'high',
            },
            timeout=10,
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
    except Exception:
        logger.exception('FCM legacy send error')
    return False
