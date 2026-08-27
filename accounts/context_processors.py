"""Context processors برای accounts."""
from divar_shop.db_safe import DB_CONTEXT_ERRORS

from accounts.services.admin_panel_shell import build_admin_panel_shell_context


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
