"""Middleware instrumentation برای API موبایل."""
from __future__ import annotations

import logging
import uuid

logger = logging.getLogger('mobile_api.auth')


class MobileAuthLoggingMiddleware:
    """لاگ ساختاریافته برای 401 بدون ذخیره token خام."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = (
            request.META.get('HTTP_X_REQUEST_ID')
            or request.META.get('HTTP_X_CORRELATION_ID')
            or uuid.uuid4().hex[:16]
        )
        request.mobile_request_id = request_id

        response = self.get_response(request)

        if not request.path.startswith('/api/mobile/v1/'):
            return response
        if response.status_code != 401:
            return response

        auth_reason = getattr(request, 'mobile_auth_failure', None)
        if not auth_reason:
            auth_reason = 'unauthenticated'
        user_id = ''
        if getattr(request, 'user', None) and request.user.is_authenticated:
            user_id = str(request.user.pk)

        logger.warning(
            'mobile_auth_denied request_id=%s endpoint=%s device_id=%s user_id=%s '
            'client_version=%s auth_reason=%s',
            request_id,
            request.path,
            (request.META.get('HTTP_X_DEVICE_ID') or '').strip(),
            user_id or '-',
            (request.META.get('HTTP_X_APP_VERSION') or request.META.get('HTTP_X_CLIENT_VERSION') or '').strip(),
            auth_reason,
        )
        return response
