"""احراز هویت JWT موبایل با ثبت دلیل خطا برای instrumentation."""
from __future__ import annotations

import logging

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = logging.getLogger('mobile_api.auth')

AUTH_FAILURE_MISSING = 'missing'
AUTH_FAILURE_INVALID = 'invalid'
AUTH_FAILURE_EXPIRED = 'expired'


def _set_auth_failure(request, reason: str) -> None:
    """DRF request wrapper را هم پوشش می‌دهد تا middleware بتواند بخواند."""
    request.mobile_auth_failure = reason
    underlying = getattr(request, '_request', None)
    if underlying is not None:
        underlying.mobile_auth_failure = reason


class MobileJWTAuthentication(JWTAuthentication):
    """JWTAuthentication با ثبت auth_failure_reason روی request."""

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            _set_auth_failure(request, AUTH_FAILURE_MISSING)
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            _set_auth_failure(request, AUTH_FAILURE_INVALID)
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except TokenError as exc:
            message = str(exc).lower()
            if 'expired' in message:
                _set_auth_failure(request, AUTH_FAILURE_EXPIRED)
            else:
                _set_auth_failure(request, AUTH_FAILURE_INVALID)
            return None

        try:
            user = self.get_user(validated_token)
        except InvalidToken:
            _set_auth_failure(request, AUTH_FAILURE_INVALID)
            return None

        _set_auth_failure(request, '')
        return user, validated_token
