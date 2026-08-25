"""میکسین و helper برای محافظت endpointهای خروجی."""
from __future__ import annotations

from accounts.services.export_verification import export_verification_required_response, is_export_authorized


class ExportSecurityMixin:
    """قبل از خروجی، تأیید رمز + OTP الزامی است."""

    def dispatch(self, request, *args, **kwargs):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and not is_export_authorized(request, user):
            return export_verification_required_response(request)
        return super().dispatch(request, *args, **kwargs)


def require_export_authorization(request, user):
    """برای APIView — در صورت عدم مجوز HttpResponse/Response برمی‌گرداند."""
    if is_export_authorized(request, user):
        return None
    return export_verification_required_response(request)


def require_export_authorization_api(request, user):
    """برای REST API موبایل — پاسخ DRF استاندارد."""
    if is_export_authorized(request, user):
        return None
    from mobile_api.responses import api_error

    return api_error(
        'برای خروجی گرفتن، تأیید هویت (رمز عبور + کد پیامک) لازم است.',
        code='EXPORT_VERIFICATION_REQUIRED',
        status=403,
    )
