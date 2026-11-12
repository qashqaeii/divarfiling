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
