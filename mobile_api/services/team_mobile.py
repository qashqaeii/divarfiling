"""سرویس‌های تیم آژانس برای Mobile API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.constants import AGENCY_ROLES, AGENCY_MANAGER_ROLES
from workspace.services.crm_agency import get_team_inbox
from workspace.services.crm_agency_announcements import unread_announcement_count
from workspace.services.crm_agency_features import is_agency_feature_enabled
from workspace.services.crm_agency_messages import unread_message_count
from workspace.services.crm_panel_notifications import unread_panel_count
from workspace.services.crm_scope import (
    agency_members,
    can_manage_team,
    can_operate_team_leads,
    get_membership,
)


def member_to_dict(member) -> Dict[str, Any]:
    user = member.user
    return {
        'id': member.pk,
        'user_id': member.user_id,
        'name': user.get_full_name() or user.phone or user.username,
        'phone': getattr(user, 'phone', None) or '',
        'role': member.role,
        'role_label': dict(AGENCY_ROLES).get(member.role, member.role),
        'title': member.title or '',
        'is_active': bool(member.is_active),
    }


def serialize_members(agency, *, exclude_user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    rows = []
    for member in agency_members(agency):
        if exclude_user_id and member.user_id == exclude_user_id:
            continue
        rows.append(member_to_dict(member))
    return rows


def team_overview_for_user(user) -> Dict[str, Any]:
    membership = get_membership(user)
    if not membership:
        return {
            'has_agency': False,
            'agency': None,
            'membership': None,
            'permissions': {
                'can_manage': False,
                'can_operate_inbox': False,
                'can_broadcast': False,
                'messages_enabled': False,
                'announcements_enabled': False,
            },
            'unread': {
                'messages': 0,
                'notifications': 0,
                'announcements': 0,
                'total': 0,
            },
            'members_count': 0,
            'inbox_leads_count': 0,
        }

    agency = membership.agency
    messages_enabled = is_agency_feature_enabled('messages', agency)
    announcements_enabled = is_agency_feature_enabled('announcements', agency)
    unread_messages = unread_message_count(user) if messages_enabled else 0
    unread_notifications = unread_panel_count(user)
    unread_announcements = unread_announcement_count(user) if announcements_enabled else 0
    can_manage = can_manage_team(user)
    can_inbox = can_operate_team_leads(user)
    members = list(agency_members(agency))
    inbox_count = 0
    if can_inbox:
        try:
            inbox_count = get_team_inbox(agency).count()
        except Exception:
            inbox_count = len(list(get_team_inbox(agency)[:100]))

    return {
        'has_agency': True,
        'agency': {
            'id': agency.pk,
            'name': agency.name,
            'slug': agency.slug,
        },
        'membership': {
            'id': membership.pk,
            'role': membership.role,
            'role_label': dict(AGENCY_ROLES).get(membership.role, membership.role),
            'title': membership.title or '',
        },
        'permissions': {
            'can_manage': can_manage,
            'can_operate_inbox': can_inbox,
            'can_broadcast': membership.role in AGENCY_MANAGER_ROLES,
            'messages_enabled': messages_enabled,
            'announcements_enabled': announcements_enabled,
        },
        'unread': {
            'messages': unread_messages,
            'notifications': unread_notifications,
            'announcements': unread_announcements,
            'total': unread_messages + unread_notifications + unread_announcements,
        },
        'members_count': len(members),
        'inbox_leads_count': inbox_count,
    }


def serialize_inbox_leads(agency) -> List[Dict[str, Any]]:
    return [
        {
            'id': c.pk,
            'name': c.name or '',
            'phone': c.phone or '',
            'source': c.source or '',
            'created_at': c.created_at.isoformat() if c.created_at else '',
        }
        for c in get_team_inbox(agency)[:100]
    ]
