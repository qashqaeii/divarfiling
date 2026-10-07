"""Agency Hub navigation — single canonical nav for team + agency."""
from __future__ import annotations

from django.urls import reverse

from workspace.services.agency_entitlement import can_manage_agency, resolve_managed_agency
from workspace.services.agency_space_access import can_access_agency_space
from workspace.services.crm_agency_features import is_agency_feature_enabled
from workspace.services.crm_scope import can_manage_team, can_view_team_inbox, get_membership


# Mobile primary rail — order matters; only keys present in build_hub_nav() are shown.
HUB_NAV_MOBILE_PRIMARY_KEYS: tuple[str, ...] = (
    'dashboard',
    'advisors',
    'space',
    'activity',
)


def partition_hub_nav(nav: list[tuple[str, str, str]]) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """Split hub nav into primary mobile rail vs overflow (settings, inbox, …)."""
    by_key = {key: (key, label, url) for key, label, url in nav}
    primary = [by_key[k] for k in HUB_NAV_MOBILE_PRIMARY_KEYS if k in by_key]
    primary_keys = {item[0] for item in primary}
    secondary = [item for item in nav if item[0] not in primary_keys]
    return primary, secondary


def build_hub_nav(user) -> list[tuple[str, str, str]]:
    agency, _sub = resolve_managed_agency(user)
    if not agency:
        membership = get_membership(user)
        agency = membership.agency if membership else None

    nav: list[tuple[str, str, str]] = [
        ('dashboard', 'داشبورد', reverse('workspace:agency_hub_dashboard')),
        ('advisors', 'مشاوران', reverse('workspace:agency_hub_advisors')),
    ]
    if can_manage_agency(user):
        nav.append(('licenses', 'لایسنس‌ها', reverse('workspace:agency_hub_licenses')))
    nav.append(('activity', 'فعالیت تیم', reverse('workspace:agency_hub_activity')))
    if agency and is_agency_feature_enabled('agency_space', agency) and can_access_agency_space(user, agency):
        nav.append(('space', 'فضای آژانس', reverse('workspace:agency_hub_space')))
    if can_view_team_inbox(user):
        nav.append(('inbox', 'صندوق', reverse('workspace:agency_hub_inbox')))
    if agency and is_agency_feature_enabled('messages', agency):
        nav.append(('messages', 'پیام‌ها', reverse('workspace:agency_hub_messages')))
    if agency and is_agency_feature_enabled('announcements', agency):
        nav.append(('announcements', 'اطلاعیه‌ها', reverse('workspace:agency_hub_announcements')))
    nav.append(('settings', 'تنظیمات', reverse('workspace:agency_hub_settings')))
    return nav


def build_settings_advanced_tabs() -> list[tuple[str, str, str]]:
    return [
        ('sync', 'همگام‌سازی', reverse('workspace:agency_hub_settings_sync')),
        ('webhooks', 'وب‌هوک', reverse('workspace:agency_hub_settings_webhooks')),
        ('transfers', 'انتقال‌ها', reverse('workspace:agency_hub_settings_transfers')),
        ('audit', 'ممیزی', reverse('workspace:agency_hub_settings_audit')),
        ('messages', 'پیام‌ها', reverse('workspace:agency_hub_messages')),
        ('announcements', 'اطلاعیه‌ها', reverse('workspace:agency_hub_announcements')),
        ('tv', 'TV دفتر', reverse('workspace:agency_hub_tv')),
    ]
