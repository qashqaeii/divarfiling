"""Explicit permissions for downloadable administrative reports.

The endpoint, not merely the menu, enforces this policy. Permission assignment
uses Django's existing per-model view permissions (no DB migration needed).
"""
from __future__ import annotations

from accounts.services.admin_exports import EXPORT_REGISTRY

# Finance and AI analytics exports are owner-only pending a dedicated role policy.
CATEGORY_PERMISSIONS = {
    'orders': ('shop.view_order', 'accounts.view_user'),
    'users': ('accounts.view_user',),
    'licenses': ('licenses.view_license', 'accounts.view_user'),
    'support': ('workspace.view_ticket', 'accounts.view_user'),
    'marketing': ('accounts.view_growthjourney', 'accounts.view_user'),
}
KEY_PERMISSIONS = {
    'users_management': (),  # Cross-domain user, device, licensing, billing data
    'users_pending_payment': ('accounts.view_user', 'shop.view_order'),
}


def can_export_report(user, export_key: str) -> bool:
    """Fail closed for unknown reports, inactive users, and unassigned roles."""
    meta = EXPORT_REGISTRY.get(export_key)
    if meta is None or user is None:
        return False
    if not (
        getattr(user, 'is_authenticated', False)
        and getattr(user, 'is_active', False)
        and getattr(user, 'is_staff', False)
    ):
        return False
    if user.is_superuser:
        return True
    required = KEY_PERMISSIONS.get(
        export_key, CATEGORY_PERMISSIONS.get(meta['category'], ())
    )
    return bool(required) and user.has_perms(required)
