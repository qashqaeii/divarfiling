"""Team property sharing — Mobile API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.models import CRMResourceShare
from workspace.services.agency_entitlement import can_share_team_resources
from workspace.services.crm_property_share import list_outgoing_property_shares, share_mode_label
from workspace.services.crm_scope import get_membership, property_for_user
from workspace.services.crm_sharing import revoke_share, share_property
from mobile_api.services.team_mobile import serialize_members


def _share_row(share: CRMResourceShare) -> Dict[str, Any]:
    user = share.shared_with
    return {
        'id': share.pk,
        'member_id': None,
        'user_id': share.shared_with_id,
        'name': user.get_full_name() or getattr(user, 'phone', None) or user.username,
        'share_mode': share.share_mode,
        'share_mode_label': share_mode_label(share.share_mode or ''),
        'note': share.note or '',
        'created_at': share.created_at.isoformat() if share.created_at else None,
    }


def list_property_team_shares(user, property_id: int) -> Optional[Dict[str, Any]]:
    prop = property_for_user(user, property_id)
    if not prop or prop.deleted_at:
        return None
    is_owner = prop.user_id == user.id
    membership = get_membership(user)
    can_manage = is_owner and bool(membership) and can_share_team_resources(user)
    shares: List[Dict[str, Any]] = []
    if is_owner:
        shares = [_share_row(s) for s in list_outgoing_property_shares(prop)]
    return {
        'property_id': prop.pk,
        'is_owner': is_owner,
        'can_share': can_manage,
        'shares': shares,
        'share_modes': [
            {'value': k, 'label': v}
            for k, v in CRMResourceShare.SHARE_MODE_CHOICES
        ],
    }


def grant_property_team_share(
    user,
    property_id: int,
    *,
    member_id: int,
    share_mode: str = '',
) -> Dict[str, Any]:
    prop = property_for_user(user, property_id)
    if not prop or prop.deleted_at:
        raise ValueError('ملک یافت نشد')
    if prop.user_id != user.id:
        raise PermissionError('فقط مالک می‌تواند به اشتراک بگذارد')
    share = share_property(
        user,
        prop,
        int(member_id),
        share_mode=share_mode or CRMResourceShare.SHARE_MODE_CONFIDENTIAL,
    )
    return _share_row(share)


def revoke_property_team_share(user, property_id: int, share_id: int) -> None:
    prop = property_for_user(user, property_id)
    if not prop or prop.deleted_at:
        raise ValueError('ملک یافت نشد')
    revoke_share(user, int(share_id))


def searchable_team_members(user, property_id: int, *, q: str = '') -> Optional[List[Dict[str, Any]]]:
    prop = property_for_user(user, property_id)
    if not prop or prop.deleted_at or prop.user_id != user.id:
        return None
    membership = get_membership(user)
    if not membership or not can_share_team_resources(user):
        return []
    members = serialize_members(membership.agency, exclude_user_id=user.id)
    query = (q or '').strip()
    if query:
        members = [
            m for m in members
            if query in (m.get('name') or '') or query in (m.get('phone') or '')
        ]
    return members
