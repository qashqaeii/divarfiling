"""Agency invitation accept — Mobile API (reuse workspace services)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from accounts.phone_utils import normalize_phone
from django.contrib.auth import get_user_model

from workspace.constants import AGENCY_ROLES
from workspace.services.agency_entitlement import CONSENT_VERSION_CURRENT
from workspace.services.agency_invitations import (
    _mask_phone,
    accept_agency_invitation,
    decline_agency_invitation,
    get_invitation_by_token,
    invitation_accept_allowed,
)

User = get_user_model()


def invitation_preview(token: str, user: Optional[User] = None) -> Dict[str, Any]:
    raw = (token or '').strip()
    invitation = get_invitation_by_token(raw)
    if not invitation:
        return {
            'valid': False,
            'error': 'لینک دعوت نامعتبر یا منقضی شده است.',
        }

    ok, msg = invitation_accept_allowed(invitation)
    status = invitation.status
    user_phone_matches = False
    if user and user.is_authenticated:
        user_phone = normalize_phone(getattr(user, 'phone', None) or user.username)
        user_phone_matches = user_phone == normalize_phone(invitation.phone)

    inviter = invitation.inviter
    return {
        'valid': ok or status != invitation.STATUS_PENDING,
        'can_accept': ok,
        'error': '' if ok else msg,
        'invitation': {
            'id': invitation.pk,
            'status': status,
            'role': invitation.role,
            'role_label': dict(AGENCY_ROLES).get(invitation.role, invitation.role),
            'masked_phone': _mask_phone(invitation.phone),
            'expires_at': invitation.expires_at.isoformat() if invitation.expires_at else '',
        },
        'agency': {
            'id': invitation.agency_id,
            'name': invitation.agency.name,
        },
        'inviter_name': (
            inviter.get_full_name() or getattr(inviter, 'phone', '') or inviter.username
        ) if inviter else '',
        'consent_version': CONSENT_VERSION_CURRENT,
        'user_authenticated': bool(user and user.is_authenticated),
        'user_phone_matches': user_phone_matches,
    }


def respond_to_invitation(
    user: User,
    token: str,
    *,
    action: str,
    consent_acknowledged: bool = False,
) -> Dict[str, Any]:
    raw = (token or '').strip()
    invitation = get_invitation_by_token(raw)
    if not invitation:
        raise ValueError('لینک دعوت نامعتبر است.')

    if action == 'decline':
        decline_agency_invitation(invitation, user)
        return {'action': 'declined', 'agency_id': invitation.agency_id}

    if action != 'accept':
        raise ValueError('عملیات نامعتبر است.')

    member = accept_agency_invitation(
        invitation,
        user,
        consent_acknowledged=consent_acknowledged,
    )
    return {
        'action': 'accepted',
        'agency_id': invitation.agency_id,
        'member_id': member.pk,
    }
