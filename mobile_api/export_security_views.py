"""API تأیید هویت پیش از خروجی — موبایل."""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.services.export_verification import (
    ExportVerificationError,
    begin_export_verification,
    complete_export_verification,
    resend_export_otp,
)
from mobile_api.responses import api_error, api_ok
from mobile_api.views import _parse_body


def _map_export_error(exc: ExportVerificationError):
    status = 429 if exc.code == 'otp_rate_limited' else 400
    return api_error(
        exc.message,
        code=exc.code.upper() if exc.code else 'EXPORT_VERIFICATION_ERROR',
        status=status,
        retry_after=exc.retry_after,
    )


class ExportSecurityVerifyPasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _parse_body(request)
        try:
            payload = begin_export_verification(
                request.user,
                data.get('password') or '',
                request=request,
            )
            return api_ok(payload)
        except ExportVerificationError as exc:
            return _map_export_error(exc)


class ExportSecurityVerifyOtpView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _parse_body(request)
        try:
            payload = complete_export_verification(
                request.user,
                data.get('password_challenge') or '',
                data.get('code') or '',
                request=request,
            )
            return api_ok(payload)
        except ExportVerificationError as exc:
            return _map_export_error(exc)


class ExportSecurityResendOtpView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _parse_body(request)
        try:
            payload = resend_export_otp(
                request.user,
                data.get('password_challenge') or '',
                request=request,
            )
            return api_ok(payload)
        except ExportVerificationError as exc:
            return _map_export_error(exc)
