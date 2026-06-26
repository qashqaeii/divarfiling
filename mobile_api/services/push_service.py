"""ارسال Push Notification از طریق FCM."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests
from django.conf import settings

from mobile_api.models import MobileDevice

logger = logging.getLogger(__name__)


def _fcm_server_key() -> str:
    return getattr(settings, 'FCM_SERVER_KEY', '') or ''


def send_push_to_user(
    user,
    *,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
) -> int:
    """ارسال به تمام دستگاه‌های کاربر. تعداد موفق را برمی‌گرداند."""
    server_key = _fcm_server_key()
    if not server_key:
        logger.debug('FCM_SERVER_KEY not configured — push skipped')
        return 0

    tokens = list(
        MobileDevice.objects.filter(user=user)
        .exclude(fcm_token='')
        .values_list('fcm_token', flat=True)
        .distinct()
    )
    if not tokens:
        return 0

    sent = 0
    payload_data = {k: str(v) for k, v in (data or {}).items()}
    for token in tokens:
        if _send_fcm_legacy(server_key, token, title, body, payload_data):
            sent += 1
    return sent


def _send_fcm_legacy(
    server_key: str,
    token: str,
    title: str,
    body: str,
    data: Dict[str, str],
) -> bool:
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
            logger.warning('FCM send failed: %s', result)
        else:
            logger.warning('FCM HTTP %s: %s', resp.status_code, resp.text[:200])
    except Exception:
        logger.exception('FCM send error')
    return False
