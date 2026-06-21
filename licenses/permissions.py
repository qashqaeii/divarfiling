"""دسترسی API لایسنس ربات دسکتاپ."""
from rest_framework.permissions import BasePermission
from django.conf import settings


class BotLicenseAPIPermission(BasePermission):
    """
    API فعال‌سازی/اعتبارسنجی ربات — در production نیاز به X-Bot-Api-Key دارد.
    در DEBUG یا LICENSE_ALLOW_LOCAL_DEV بدون کلید مجاز است.
    """

    message = 'دسترسی API لایسنس مجاز نیست.'

    def has_permission(self, request, view):
        if settings.DEBUG or settings.LICENSE_ALLOW_LOCAL_DEV:
            return True
        expected = getattr(settings, 'LICENSE_BOT_API_KEY', '') or ''
        if not expected:
            return False
        return request.headers.get('X-Bot-Api-Key', '') == expected
