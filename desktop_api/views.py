"""Viewهای REST API دسکتاپ — /api/desktop/v1/"""
from __future__ import annotations

import json

from django.conf import settings
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from desktop_api.services.auth_service import authenticate_credentials, tokens_for_user
from desktop_api.throttles import (
    DesktopBindThrottle,
    DesktopLoginThrottle,
    DesktopRefreshThrottle,
    DesktopValidateThrottle,
)
from licenses.services.desktop_licensing import DesktopLicensingError
from licenses.services.security import RateLimitExceeded, check_rate_limit, get_client_ip
from mobile_api.responses import api_error, api_ok


def _feature_enabled() -> bool:
    return bool(getattr(settings, 'DESKTOP_ACCOUNT_LOGIN_ENABLED', False))


def _parse_body(request) -> dict:
    try:
        if not request.body:
            return {}
        return json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return {}


def _licensing_error(exc: DesktopLicensingError):
    return api_error(
        exc.message,
        code=exc.code,
        status=exc.http_status,
        fields=exc.payload if exc.payload else None,
    )


def _user_payload(user) -> dict:
    from mobile_api.serializers import user_to_dict
    return user_to_dict(user)


class FeatureDisabled(APIException):
    status_code = 503
    default_detail = 'ورود با حساب کاربری در اپ دسکتاپ فعلاً غیرفعال است.'
    default_code = 'FEATURE_DISABLED'


class DesktopFeatureGateMixin:
    def initial(self, request, *args, **kwargs):
        if not _feature_enabled():
            raise FeatureDisabled()
        super().initial(request, *args, **kwargs)


class LoginView(DesktopFeatureGateMixin, APIView):
    permission_classes = [AllowAny]
    throttle_classes = [DesktopLoginThrottle]

    def post(self, request):
        data = _parse_body(request)
        username = data.get('username') or data.get('phone') or ''
        password = data.get('password') or ''

        client_ip = get_client_ip(getattr(request, 'META', {}) or {})
        try:
            check_rate_limit('desktop_login', client_ip)
        except RateLimitExceeded as exc:
            return api_error(str(exc), code='RATE_LIMIT', status=429)

        user, err = authenticate_credentials(username, password, request)
        if user is None:
            return api_error(err or 'خطای ورود', code='AUTH_INVALID', status=401)

        tokens = tokens_for_user(user)
        return api_ok({
            **_tokens_payload(tokens),
            'user': _user_payload(user),
        })


class RefreshView(DesktopFeatureGateMixin, APIView):
    permission_classes = [AllowAny]
    throttle_classes = [DesktopRefreshThrottle]

    def post(self, request):
        data = _parse_body(request)
        refresh_str = data.get('refresh') or ''
        if not refresh_str:
            return api_error('توکن refresh الزامی است.', code='VALIDATION_ERROR')
        try:
            refresh = RefreshToken(refresh_str)
            access = refresh.access_token
            return api_ok({
                'access': str(access),
                'refresh': str(refresh),
                'expires_in': int(access.lifetime.total_seconds()),
            })
        except TokenError:
            return api_error('توکن منقضی شده است.', code='AUTH_EXPIRED', status=401)


class LogoutView(DesktopFeatureGateMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = _parse_body(request)
        refresh_str = data.get('refresh') or ''
        if refresh_str:
            try:
                token = RefreshToken(refresh_str)
                token.blacklist()
            except Exception:
                pass
        return api_ok({'message': 'خروج از حساب انجام شد.'})


class EligibleLicensesView(DesktopFeatureGateMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        hw = (request.GET.get('hardware_fingerprint') or '').strip()
        if not hw:
            return api_error(
                'شناسه سخت‌افزاری الزامی است.',
                code='VALIDATION_ERROR',
            )
        try:
            from licenses.services.desktop_licensing import get_eligible_licenses
            return api_ok(get_eligible_licenses(request.user, hw))
        except DesktopLicensingError as exc:
            return _licensing_error(exc)


class BindLicenseView(DesktopFeatureGateMixin, APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [DesktopBindThrottle]

    def post(self, request):
        data = _parse_body(request)
        hw = (data.get('hardware_fingerprint') or '').strip()
        license_id = data.get('license_id')
        device_label = (data.get('device_label') or 'Windows').strip()

        if not hw:
            return api_error('شناسه سخت‌افزاری الزامی است.', code='VALIDATION_ERROR')

        client_ip = get_client_ip(getattr(request, 'META', {}) or {})
        try:
            check_rate_limit('desktop_bind', client_ip)
        except RateLimitExceeded as exc:
            return api_error(str(exc), code='RATE_LIMIT', status=429)

        if license_id is not None:
            try:
                license_id = int(license_id)
            except (TypeError, ValueError):
                return api_error('شناسه لایسنس نامعتبر است.', code='VALIDATION_ERROR')

        try:
            from licenses.services.desktop_licensing import bind_desktop_device
            payload = bind_desktop_device(
                request.user,
                hw,
                request,
                license_id=license_id,
                device_label=device_label,
            )
            return api_ok(payload)
        except DesktopLicensingError as exc:
            if exc.code == 'LICENSE_SELECTION_REQUIRED' and exc.payload:
                return api_error(
                    exc.message,
                    code=exc.code,
                    status=exc.http_status,
                    fields=exc.payload,
                )
            return _licensing_error(exc)


class ValidateSessionView(DesktopFeatureGateMixin, APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [DesktopValidateThrottle]

    def post(self, request):
        data = _parse_body(request)
        hw = (data.get('hardware_fingerprint') or '').strip()
        license_key = (data.get('license_key') or '').strip() or None

        if not hw:
            return api_error('شناسه سخت‌افزاری الزامی است.', code='VALIDATION_ERROR')

        client_ip = get_client_ip(getattr(request, 'META', {}) or {})
        try:
            check_rate_limit('desktop_validate', client_ip)
        except RateLimitExceeded as exc:
            return api_error(str(exc), code='RATE_LIMIT', status=429)

        try:
            from licenses.services.desktop_licensing import validate_desktop_session
            payload = validate_desktop_session(
                request.user,
                hw,
                request,
                license_key=license_key,
            )
            if not payload.get('valid'):
                return api_error(
                    payload.get('error', 'session نامعتبر است'),
                    code=payload.get('code', 'SESSION_INVALID'),
                    status=403,
                    fields={
                        k: payload[k]
                        for k in ('eligible',)
                        if k in payload
                    } or None,
                )
            return api_ok(payload)
        except DesktopLicensingError as exc:
            return _licensing_error(exc)


def _tokens_payload(tokens: dict) -> dict:
    return {
        'access': tokens['access'],
        'refresh': tokens['refresh'],
        'expires_in': tokens['expires_in'],
    }
