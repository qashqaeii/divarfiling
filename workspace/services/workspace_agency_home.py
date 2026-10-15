"""کارت آژانس در میزکار — بر اساس entitlement و RBAC واقعی."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.urls import reverse

from workspace.models import CRMAgencyMember
from workspace.services.agency_entitlement import (
    can_access_agency_hub,
    can_manage_agency,
    get_subscription_for_agency,
    is_expired_agency_owner,
)
from workspace.services.agency_rbac import (
    NAV_PROFILE_ADVISOR,
    NAV_PROFILE_MANAGER_LEGACY,
    NAV_PROFILE_OWNER,
    NAV_PROFILE_SECRETARY,
    PERM_INBOX_VIEW,
    PERM_TEAM_MANAGE,
    PERM_TEAM_VIEW_PERFORMANCE,
    has_agency_permission,
    is_agency_rbac_v2_enabled,
    resolve_nav_profile,
)
from workspace.services.agency_space_access import can_access_agency_space
from workspace.services.crm_agency_features import is_agency_feature_enabled
from workspace.services.crm_scope import can_view_team_inbox, get_membership


def _role_label(member: Optional[CRMAgencyMember]) -> str:
    if not member:
        return 'مالک اشتراک'
    return member.get_role_display() or member.role


_FA_BY_DECOR = {
    'house': 'fa-house',
    'users': 'fa-users',
    'share': 'fa-share-nodes',
    'inbox': 'fa-inbox',
    'history': 'fa-clock-rotate-left',
    'folder': 'fa-folder-open',
    'calendar': 'fa-calendar-day',
    'list_check': 'fa-list-check',
    'building': 'fa-building',
}


def _shortcut(label: str, url_name: str, decor: str, *, query: str = '') -> Dict[str, str]:
    path = reverse(url_name)
    if query:
        path = f'{path}?{query}'
    return {
        'label': label,
        'url': path,
        'decor': decor,
        'fa': _FA_BY_DECOR.get(decor, 'fa-circle'),
    }


def _build_shortcuts(user, agency, profile: str, rbac_on: bool) -> List[Dict[str, str]]:
    shortcuts: List[Dict[str, str]] = []
    space_ok = (
        agency
        and is_agency_feature_enabled('agency_space', agency)
        and can_access_agency_space(user, agency)
    )

    if profile in (NAV_PROFILE_OWNER, NAV_PROFILE_MANAGER_LEGACY) or (
        not rbac_on and can_manage_agency(user, agency)
    ):
        shortcuts.append(_shortcut('داشبورد آژانس', 'workspace:agency_hub_dashboard', 'house'))
        if not rbac_on or has_agency_permission(user, PERM_TEAM_MANAGE):
            shortcuts.append(_shortcut('مشاوران', 'workspace:agency_hub_advisors', 'users'))
        if space_ok:
            shortcuts.append(_shortcut('فضای آژانس', 'workspace:agency_hub_space', 'share'))
        if can_view_team_inbox(user) or (
            rbac_on and has_agency_permission(user, PERM_INBOX_VIEW)
        ):
            shortcuts.append(_shortcut('صندوق سرنخ', 'workspace:agency_hub_inbox', 'inbox'))
        elif not rbac_on or has_agency_permission(user, PERM_TEAM_VIEW_PERFORMANCE):
            shortcuts.append(_shortcut('فعالیت تیم', 'workspace:agency_hub_activity', 'history'))
    elif profile == NAV_PROFILE_SECRETARY:
        shortcuts.append(_shortcut('میزکار پذیرش', 'workspace:agency_hub_dashboard', 'house'))
        if has_agency_permission(user, PERM_INBOX_VIEW):
            shortcuts.append(_shortcut('صندوق سرنخ', 'workspace:agency_hub_inbox', 'inbox'))
        shortcuts.append(_shortcut('مخاطبین', 'workspace:crm_contacts', 'users'))
        shortcuts.append(_shortcut('پیگیری‌ها', 'workspace:crm_today', 'list_check'))
        if space_ok:
            shortcuts.append(_shortcut('فضای آژانس', 'workspace:agency_hub_space', 'share'))
    elif profile == NAV_PROFILE_ADVISOR or (not rbac_on and not can_manage_agency(user, agency)):
        if space_ok:
            shortcuts.append(_shortcut('فضای آژانس', 'workspace:agency_hub_space', 'building'))
        shortcuts.append(_shortcut('فایل‌های شخصی', 'workspace:crm_properties', 'folder'))
        shortcuts.append(_shortcut('مخاطبین', 'workspace:crm_contacts', 'users'))
        shortcuts.append(_shortcut('کارهای امروز', 'workspace:crm_today', 'calendar'))

    seen: set[str] = set()
    unique: List[Dict[str, str]] = []
    for item in shortcuts:
        if item['url'] in seen:
            continue
        seen.add(item['url'])
        unique.append(item)
    return unique[:4]


def build_workspace_agency_panel(user) -> Optional[Dict[str, Any]]:
    """None = کارت نمایش داده نشود."""
    if not user or not user.is_authenticated:
        return None

    membership = get_membership(user)
    agency = membership.agency if membership and membership.is_active else None

    if is_expired_agency_owner(user):
        name = (agency.name if agency else '') or 'آژانس شما'
        return {
            'agency_name': name,
            'role_label': _role_label(membership),
            'status': 'locked',
            'status_label': 'اشتراک آژانس منقضی شده',
            'enter_url': reverse('workspace:agency_locked'),
            'enter_label': 'تمدید اشتراک',
            'shortcuts': [],
            'show_shortcuts': False,
        }

    if not can_access_agency_hub(user):
        return None

    if not agency:
        from workspace.services.agency_entitlement import resolve_managed_agency

        agency, _sub = resolve_managed_agency(user)
    if not agency:
        return None

    rbac_on = is_agency_rbac_v2_enabled(agency)
    profile = resolve_nav_profile(user) if rbac_on else ''
    if not profile:
        if can_manage_agency(user, agency):
            profile = NAV_PROFILE_OWNER
        elif membership and membership.role == 'secretary':
            profile = NAV_PROFILE_SECRETARY
        else:
            profile = NAV_PROFILE_ADVISOR

    sub = get_subscription_for_agency(agency)
    status_label = 'دسترسی فعال'
    if can_manage_agency(user, agency):
        status_label = 'مدیریت آژانس · اشتراک فعال' if sub else 'مدیریت آژانس'
    elif membership and membership.role == 'secretary':
        status_label = 'پذیرش · عضو تیم'
    elif sub:
        status_label = 'عضو آژانس · اشتراک فعال'

    if profile == NAV_PROFILE_ADVISOR and not can_manage_agency(user, agency):
        enter_url = reverse('workspace:agency_advisor_member')
        enter_label = 'میزکار مشاور'
    elif profile == NAV_PROFILE_SECRETARY:
        enter_url = reverse('workspace:agency_hub_dashboard')
        enter_label = 'ورود به آژانس'
    else:
        enter_url = reverse('workspace:agency_hub_dashboard')
        enter_label = 'ورود به آژانس'

    shortcuts = _build_shortcuts(user, agency, profile, rbac_on)

    return {
        'agency_name': agency.name,
        'role_label': _role_label(membership),
        'status': 'active',
        'status_label': status_label,
        'enter_url': enter_url,
        'enter_label': enter_label,
        'shortcuts': shortcuts,
        'show_shortcuts': bool(shortcuts),
        'rbac_v2': rbac_on,
    }
