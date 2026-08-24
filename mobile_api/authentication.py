"""احراز هویت JWT موبایل با ثبت دلیل خطا برای instrumentation."""
from __future__ import annotations

import logging

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

logger = logging.getLogger('mobile_api.auth')

AUTH_FAILURE_MISSING = 'missing'
AUTH_FAILURE_INVALID = 'invalid'
AUTH_FAILURE_EXPIRED = 'expired'


class MobileJWTAuthentication(JWTAuthentication):
    """JWTAuthentication با ثبت auth_failure_reason روی request."""

    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            request.mobile_auth_failure = AUTH_FAILURE_MISSING
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            request.mobile_auth_failure = AUTH_FAILURE_INVALID
            return None

        try:
            validated_token = self.get_validated_token(raw_token)
        except TokenError as exc:
            message = str(exc).lower()
            if 'expired' in message:
                request.mobile_auth_failure = AUTH_FAILURE_EXPIRED
            else:
                request.mobile_auth_failure = AUTH_FAILURE_INVALID
            return None

        try:
            user = self.get_user(validated_token)
        except InvalidToken:
            request.mobile_auth_failure = AUTH_FAILURE_INVALID
            return None

        request.mobile_auth_failure = ''
        return user, validated_token
