"""Context processors برای accounts."""
from django.conf import settings

from divar_shop.db_safe import DB_CONTEXT_ERRORS

from accounts.services.admin_panel_shell import build_admin_panel_shell_context

_OTP_AUTH_PATH_PREFIXES = (
    '/accounts/login/otp',
    '/accounts/register/',
    '/accounts/verify-phone',
    '/accounts/password-reset',
)


def otp_auth_ui(request):
    """مهلت OTP و تایمر ارسال مجدد — صفحات ورود/ثبت‌نام با پیامک."""
    path = request.path or ''
    if not any(path.startswith(prefix) for prefix in _OTP_AUTH_PATH_PREFIXES):
        return {}
    ttl = max(60, int(getattr(settings, 'OTP_EXPIRY_SECONDS', 300) or 300))
    resend = max(0, int(getattr(settings, 'OTP_RESEND_SECONDS', 60) or 0))
    if ttl % 60 == 0:
        minutes = ttl // 60
    else:
        minutes = max(1, round(ttl / 60))
    return {
        'otp_expiry_minutes': minutes,
        'otp_resend_seconds': resend,
    }


def admin_panel_shell(request):
    if '/accounts/admin-panel' not in (request.path or ''):
        return {}
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_staff', False):
        return {}
    try:
        return build_admin_panel_shell_context(request)
    except DB_CONTEXT_ERRORS:
        return {'admin_panel_shell': True, 'admin_panel_nav_badges': {}}
