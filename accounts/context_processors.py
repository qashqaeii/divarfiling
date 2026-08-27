"""Context processors برای accounts."""
from accounts.services.admin_panel_shell import build_admin_panel_shell_context


def admin_panel_shell(request):
    if '/accounts/admin-panel' not in (request.path or ''):
        return {}
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_staff', False):
        return {}
    return build_admin_panel_shell_context(request)
