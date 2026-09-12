"""Middleware instrumentation برای API موبایل."""
from __future__ import annotations

import logging
import uuid

logger = logging.getLogger('mobile_api.auth')

_QUIET_AUTH_FAILURES = frozenset({'', 'missing', 'unauthenticated'})


def _mobile_auth_failure_reason(request) -> str:
    reason = getattr(request, 'mobile_auth_failure', None)
    if reason:
        return str(reason)
    underlying = getattr(request, '_request', None)
    if underlying is not None:
        reason = getattr(underlying, 'mobile_auth_failure', None)
        if reason:
            return str(reason)
    return 'unauthenticated'


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

        auth_reason = _mobile_auth_failure_reason(request)
        user_id = ''
        if getattr(request, 'user', None) and request.user.is_authenticated:
            user_id = str(request.user.pk)

        log_kwargs = {
            'request_id': request_id,
            'endpoint': request.path,
            'device_id': (request.META.get('HTTP_X_DEVICE_ID') or '').strip(),
            'user_id': user_id or '-',
            'client_version': (
                request.META.get('HTTP_X_APP_VERSION')
                or request.META.get('HTTP_X_CLIENT_VERSION')
                or ''
            ).strip(),
            'auth_reason': auth_reason,
        }
        message = (
            'mobile_auth_denied request_id=%(request_id)s endpoint=%(endpoint)s '
            'device_id=%(device_id)s user_id=%(user_id)s client_version=%(client_version)s '
            'auth_reason=%(auth_reason)s'
        )
        if auth_reason in _QUIET_AUTH_FAILURES:
            logger.debug(message, log_kwargs)
        else:
            logger.warning(message, log_kwargs)
        return response
