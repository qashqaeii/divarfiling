"""Viewهای موبایل برای اتصال دیوار و دریافت شماره مالک."""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from mobile_api.responses import api_error, api_ok
from mobile_api.services import divar_contact_mobile as svc
from workspace.services.divar_session.errors import DivarSessionError


def _divar_error(exc: DivarSessionError):
    status = 403 if exc.code in {'forbidden'} else 404 if exc.code == 'not_found' else 400
    return api_error(exc.message, code=exc.code.upper() if exc.code else 'DIVAR_ERROR', status=status)


class DivarContactStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return api_ok(svc.status_payload(request.user))


class DivarContactListingStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, token):
        payload = svc.status_for_listing(request.user, token)
        if not payload:
            return api_error('آگهی یافت نشد.', code='NOT_FOUND', status=404)
        return api_ok(payload)


class DivarContactOtpSendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            payload = svc.send_otp_payload(request.user, request.data.get('phone') or '')
        except DivarSessionError as exc:
            return _divar_error(exc)
        return api_ok(payload)


class DivarContactOtpVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            payload = svc.verify_otp_payload(
                request.user,
                request.data.get('phone') or '',
                request.data.get('otp') or '',
            )
        except DivarSessionError as exc:
            return _divar_error(exc)
        return api_ok(payload)


class DivarContactDisconnectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            payload = svc.disconnect_payload(request.user)
        except DivarSessionError as exc:
            return _divar_error(exc)
        return api_ok(payload)


class DivarContactFetchPhoneView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        try:
            payload = svc.fetch_phone_payload(request.user, token)
        except DivarSessionError as exc:
            return _divar_error(exc)
        # captcha_required همچنان در data برمی‌گردد (ok=false) مثل وب
        return api_ok(payload)
