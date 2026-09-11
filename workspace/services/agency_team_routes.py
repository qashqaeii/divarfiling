"""Legacy CRM Team tab → canonical Agency Hub routes."""
from __future__ import annotations

from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse

# Legacy ?tab= values → Django URL name
LEGACY_TEAM_TAB_URLS: dict[str, str] = {
    'command': 'workspace:agency_hub_dashboard',
    'overview': 'workspace:agency_hub_dashboard',
    'members': 'workspace:agency_hub_advisors',
    'inbox': 'workspace:agency_hub_inbox',
    'messages': 'workspace:agency_hub_messages',
    'announcements': 'workspace:agency_hub_announcements',
    'sync': 'workspace:agency_hub_settings_sync',
    'webhooks': 'workspace:agency_hub_settings_webhooks',
    'transfers': 'workspace:agency_hub_settings_transfers',
    'settings': 'workspace:agency_hub_settings_profile',
    'audit': 'workspace:agency_hub_settings_audit',
}

# POST hidden field `tab` → redirect target after action
POST_TAB_REDIRECT_URLS = LEGACY_TEAM_TAB_URLS


def default_legacy_team_tab(request: HttpRequest) -> str:
    from workspace.services.agency_entitlement import can_manage_agency
    from workspace.services.crm_scope import can_manage_team, get_membership

    user = request.user
    membership = get_membership(user)
    agency = membership.agency if membership else None
    if agency and can_manage_agency(user):
        return 'members'
    if agency and can_manage_team(user):
        return 'command'
    return 'overview'


def redirect_legacy_team_tab(request: HttpRequest, tab: str | None = None):
    """Redirect /crm/team/?tab=… to the matching Agency Hub page."""
    tab = (tab or request.GET.get('tab') or '').strip()
    if not tab:
        tab = default_legacy_team_tab(request)
    url_name = LEGACY_TEAM_TAB_URLS.get(tab, 'workspace:agency_hub_dashboard')
    target = reverse(url_name)
    query = request.GET.urlencode()
    if query:
        # Preserve non-tab query params (e.g. days=30 on overview)
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        parsed = urlparse(target)
        params = parse_qs(parsed.query, keep_blank_values=True)
        for key, values in parse_qs(query, keep_blank_values=True).items():
            if key == 'tab':
                continue
            params[key] = values
        flat = [(k, v) for k, vals in params.items() for v in vals]
        target = urlunparse(parsed._replace(query=urlencode(flat)))
    return redirect(target)


def redirect_after_team_action(tab: str):
    url_name = POST_TAB_REDIRECT_URLS.get(tab, 'workspace:agency_hub_dashboard')
    return redirect(url_name)
