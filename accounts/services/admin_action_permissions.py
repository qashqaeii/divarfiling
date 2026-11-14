"""Role-scoped permissions for high-impact management operations."""
from __future__ import annotations


def _active_staff(user) -> bool:
    return bool(
        user is not None
        and getattr(user, 'is_authenticated', False)
        and getattr(user, 'is_active', False)
        and getattr(user, 'is_staff', False)
    )


def can_review_card_transfer(user) -> bool:
    """Approving a receipt changes paid status and grants entitlements."""
    if not _active_staff(user):
        return False
    return bool(
        user.is_superuser
        or user.has_perms(('shop.change_cardtransfersubmission', 'shop.change_order'))
    )


def can_send_admin_sms(user) -> bool:
    """Allow explicitly delegated marketing/SMS operators, or superusers."""
    if not _active_staff(user):
        return False
    return bool(
        user.is_superuser
        or user.has_perms(('accounts.change_marketingcampaign', 'accounts.add_smsmessagelog'))
    )


def can_manage_user_licenses(user) -> bool:
    """تغییر وضعیت، انقضا و اسلات لایسنس از پرونده ۳۶۰."""
    if not _active_staff(user):
        return False
    return bool(
        user.is_superuser
        or user.has_perms(('licenses.change_license', 'licenses.change_licenseactivation'))
    )


def can_manage_support_tickets(user) -> bool:
    """Reply, close, and update customer tickets from the admin dossier."""
    if not _active_staff(user):
        return False
    return bool(
        user.is_superuser
        or user.has_perms(('workspace.change_ticket', 'workspace.add_ticketmessage'))
    )


def can_view_user_management(user) -> bool:
    """Full user dossiers expose identity, orders and license/device details."""
    if not _active_staff(user):
        return False
    return bool(
        user.is_superuser
        or user.has_perms((
            'accounts.view_user',
            'shop.view_order',
            'licenses.view_license',
        ))
    )


def can_view_financial_integrity(user) -> bool:
    """Read-only cross-module payment/entitlement diagnostics."""
    if not _active_staff(user):
        return False
    return bool(
        user.is_superuser
        or user.has_perms(('shop.view_order', 'licenses.view_license', 'accounts.view_user'))
    )
