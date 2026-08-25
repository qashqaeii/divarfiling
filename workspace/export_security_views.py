"""API تأیید هویت پیش از خروجی — میزکار وب."""
from __future__ import annotations

import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect

from accounts.services.export_verification import (
    ExportVerificationError,
    begin_export_verification,
    complete_export_verification,
    resend_export_otp,
)


def _parse_json(request) -> dict:
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return request.POST.dict()


def _error_response(exc: ExportVerificationError, status: int = 400) -> JsonResponse:
    payload = {'ok': False, 'error': exc.message, 'code': exc.code}
    if exc.retry_after is not None:
        payload['retry_after'] = exc.retry_after
    response = JsonResponse(payload, status=status)
    if exc.retry_after is not None:
        response['Retry-After'] = str(exc.retry_after)
    return response


@method_decorator(csrf_protect, name='dispatch')
class ExportSecurityVerifyPasswordView(LoginRequiredMixin, View):
    """مرحله ۱: تأیید رمز عبور و ارسال OTP."""

    def post(self, request):
        data = _parse_json(request)
        password = data.get('password') or ''
        try:
            payload = begin_export_verification(request.user, password, request=request)
            return JsonResponse({'ok': True, 'data': payload})
        except ExportVerificationError as exc:
            status = 429 if exc.code == 'otp_rate_limited' else 400
            return _error_response(exc, status=status)


@method_decorator(csrf_protect, name='dispatch')
class ExportSecurityVerifyOtpView(LoginRequiredMixin, View):
    """مرحله ۲: تأیید OTP و صدور مجوز خروجی."""

    def post(self, request):
        data = _parse_json(request)
        try:
            payload = complete_export_verification(
                request.user,
                data.get('password_challenge') or '',
                data.get('code') or '',
                request=request,
            )
            return JsonResponse({'ok': True, 'data': payload})
        except ExportVerificationError as exc:
            status = 429 if exc.code == 'otp_rate_limited' else 400
            return _error_response(exc, status=status)


@method_decorator(csrf_protect, name='dispatch')
class ExportSecurityResendOtpView(LoginRequiredMixin, View):
    """ارسال مجدد OTP — فقط پس از تأیید رمز."""

    def post(self, request):
        data = _parse_json(request)
        try:
            payload = resend_export_otp(
                request.user,
                data.get('password_challenge') or '',
                request=request,
            )
            return JsonResponse({'ok': True, 'data': payload})
        except ExportVerificationError as exc:
            status = 429 if exc.code == 'otp_rate_limited' else 400
            return _error_response(exc, status=status)
