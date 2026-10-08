"""Agency Hub pages migrated from legacy CRM Team tabs."""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from workspace.crm_views import CRMTeamView, CRMContextMixin
from workspace.mixins_agency import AgencyOwnerRequiredMixin, AgencyTeamHubRequiredMixin
from workspace.services.agency_hub import build_dashboard_context, hub_base_context
from workspace.services.agency_hub_nav import (
    build_hub_nav,
    build_settings_advanced_tabs,
    partition_hub_nav,
)
from workspace.services.agency_members import build_members_dashboard
from workspace.services.agency_seats import list_available_seats
from workspace.services.agency_team_routes import redirect_after_team_action


def _hub_shell_context(request, hub_section: str) -> dict:
    from workspace.services.agency_activity import EVENT_TYPE_LABELS

    ctx = hub_base_context(request.user)
    hub_nav = build_hub_nav(request.user)
    hub_nav_primary, hub_nav_more = partition_hub_nav(hub_nav)
    ctx.update({
        'crm_section': 'agency',
        'hub_section': hub_section,
        'agency_event_labels': EVENT_TYPE_LABELS,
        'hub_nav': hub_nav,
        'hub_nav_primary': hub_nav_primary,
        'hub_nav_more': hub_nav_more,
        'agency_team_action_url': reverse('workspace:agency_team_action'),
        'crm_team_url': reverse('workspace:agency_team_action'),
    })
    return ctx


class _AgencyHubTeamBase(AgencyTeamHubRequiredMixin, LoginRequiredMixin, TemplateView):
    hub_section = ''
    team_tab = ''

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_hub_shell_context(self.request, self.hub_section))
        return ctx


class AgencyHubDashboardView(_AgencyHubTeamBase):
    template_name = 'workspace/crm/agency/hub_dashboard.html'
    hub_section = 'dashboard'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days = int(self.request.GET.get('days', 30) or 30)
        if days not in (7, 30, 90):
            days = 30
        ctx.update(build_dashboard_context(self.request.user, days=days))
        return ctx


class AgencyHubAdvisorsView(_AgencyHubTeamBase):
    template_name = 'workspace/crm/agency/hub_advisors.html'
    hub_section = 'advisors'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        agency = ctx.get('hub_agency')
        if agency:
            ctx['members_dashboard'] = build_members_dashboard(self.request.user, agency)
            ctx['available_seats'] = list_available_seats(self.request.user, agency)
            ctx['team_export_url'] = reverse('workspace:agency_team_export')
        return ctx


class AgencyHubLicensesView(AgencyOwnerRequiredMixin, _AgencyHubTeamBase):
    template_name = 'workspace/crm/agency/hub_licenses.html'
    hub_section = 'licenses'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        agency = ctx.get('hub_agency')
        if agency:
            from licenses.services.management import build_agency_license_pool
            ctx['license_pool'] = build_agency_license_pool(agency.owner)
        return ctx


class AgencyHubActivityView(_AgencyHubTeamBase):
    template_name = 'workspace/crm/agency/hub_activity.html'
    hub_section = 'activity'

    def get_context_data(self, **kwargs):
        from workspace.services.agency_data_scope import list_visible_advisor_members, resolve_visible_agency_member
        from workspace.services.agency_hub import build_activity_feed

        ctx = super().get_context_data(**kwargs)
        ctx['advisors'] = list(list_visible_advisor_members(self.request.user))
        member_id = self.request.GET.get('advisor')
        actor_user_id = None
        if member_id and member_id.isdigit():
            try:
                actor_user_id = resolve_visible_agency_member(
                    self.request.user, int(member_id),
                ).user_id
            except Exception:
                actor_user_id = None
        ctx['events'] = build_activity_feed(
            self.request.user,
            advisor_id=actor_user_id,
            event_type=self.request.GET.get('event_type', ''),
        )
        ctx['event_type_filter'] = self.request.GET.get('event_type', '')
        return ctx


class AgencyHubSettingsView(_AgencyHubTeamBase):
    template_name = 'workspace/crm/agency/hub_settings.html'
    hub_section = 'settings'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['profile_settings_url'] = reverse('workspace:agency_hub_settings_profile')
        ctx['advanced_tabs'] = build_settings_advanced_tabs()
        return ctx


class _AgencyTeamTabView(_AgencyHubTeamBase):
    """Renders a legacy team tab partial inside Agency Hub chrome."""
    template_name = 'workspace/crm/agency/hub_team_tab.html'
    team_tab = ''
    team_tab_template = ''
    extra_team_css: list[str] = []
    extra_team_js: list[str] = []

    def get(self, request, *args, **kwargs):
        from workspace.crm_views import CRMTeamView

        return TemplateView.get(self, request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from workspace.crm_views import CRMTeamView

        team_view = CRMTeamView()
        team_view.setup(self.request, *self.args, **self.kwargs)
        ctx = team_view.get_context_data(**kwargs)
        ctx.update(_hub_shell_context(self.request, self.hub_section))
        ctx['tab'] = self.team_tab
        ctx['team_tab_template'] = self.team_tab_template
        ctx['extra_team_css'] = self.extra_team_css
        ctx['extra_team_js'] = self.extra_team_js
        ctx['agency_team_action_url'] = reverse('workspace:agency_team_action')
        ctx['crm_team_url'] = ctx['agency_team_action_url']
        ctx['crm_team_tv_url'] = reverse('workspace:agency_hub_tv')
        return ctx


class AgencyHubInboxView(_AgencyTeamTabView):
    hub_section = 'inbox'
    team_tab = 'inbox'
    team_tab_template = 'workspace/crm/includes/team_tab_inbox.html'


class AgencyHubMessagesView(_AgencyTeamTabView):
    hub_section = 'messages'
    team_tab = 'messages'
    team_tab_template = 'workspace/crm/includes/team_tab_messages.html'
    extra_team_css = [
        'workspace/css/crm-team-messages.css',
        'workspace/css/crm-team-mobile.css',
    ]
    extra_team_js = [
        'workspace/js/crm-team-messages.js',
        'workspace/js/crm-team-hub-badges.js',
    ]


class AgencyHubAnnouncementsView(_AgencyTeamTabView):
    hub_section = 'announcements'
    team_tab = 'announcements'
    team_tab_template = 'workspace/crm/includes/team_tab_announcements.html'
    extra_team_css = [
        'workspace/css/crm-team-announcements.css',
    ]
    extra_team_js = [
        'workspace/js/crm-team-announcements.js',
        'workspace/js/crm-team-hub-badges.js',
    ]


class AgencyHubSettingsProfileView(_AgencyTeamTabView):
    hub_section = 'settings'
    team_tab = 'settings'
    team_tab_template = 'workspace/crm/includes/team_tab_settings_audit.html'
    extra_team_css = [
        'workspace/css/crm-team-audit.css',
    ]


class AgencyHubSettingsSyncView(_AgencyTeamTabView):
    hub_section = 'settings'
    team_tab = 'sync'
    team_tab_template = 'workspace/crm/includes/team_tab_sync.html'


class AgencyHubSettingsWebhooksView(_AgencyTeamTabView):
    hub_section = 'settings'
    team_tab = 'webhooks'
    team_tab_template = 'workspace/crm/includes/team_tab_webhooks.html'


class AgencyHubSettingsTransfersView(_AgencyTeamTabView):
    hub_section = 'settings'
    team_tab = 'transfers'
    team_tab_template = 'workspace/crm/includes/team_tab_transfers.html'


class AgencyHubSettingsAuditView(_AgencyTeamTabView):
    hub_section = 'settings'
    team_tab = 'audit'
    team_tab_template = 'workspace/crm/includes/team_tab_audit.html'
    extra_team_css = [
        'workspace/css/crm-team-audit.css',
    ]
    extra_team_js = [
        'workspace/js/crm-team-audit.js',
    ]


class AgencyHubTVView(CRMContextMixin, AgencyTeamHubRequiredMixin, LoginRequiredMixin, TemplateView):
    """داشبورد تمام‌صفحه TV — canonical Agency route."""
    template_name = 'workspace/crm/team/tv.html'

    def dispatch(self, request, *args, **kwargs):
        from django.contrib import messages
        from workspace.services.crm_agency_features import is_agency_feature_enabled
        from workspace.services.crm_scope import get_membership

        membership = get_membership(request.user)
        agency = membership.agency if membership else None
        if not agency:
            messages.error(request, 'ابتدا به یک آژانس بپیوندید.')
            return redirect('workspace:agency_hub_dashboard')
        if not is_agency_feature_enabled('tv_mode', agency):
            messages.error(request, 'حالت TV برای این آژانس فعال نیست.')
            return redirect('workspace:agency_hub_settings')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from workspace.services.crm_agency_tv import get_tv_dashboard_payload

        ctx = super().get_context_data(**kwargs)
        ctx['crm_section'] = 'team-tv'
        ctx['tv_payload'] = get_tv_dashboard_payload(self.request.user, use_cache=False)
        optional = ('chart', 'goals', 'activity', 'schedule', 'announcements', 'alerts')
        ctx['tv_widgets'] = [w for w in ctx['tv_payload'].get('allowed_widgets', []) if w in optional]
        ctx['api_crm_team_tv_url'] = reverse('workspace:api_crm_team_tv')
        ctx['crm_team_url'] = reverse('workspace:agency_hub_dashboard')
        ctx['crm_team_tv_url'] = reverse('workspace:agency_hub_tv')
        return ctx


class AgencyHubRedirectView(LoginRequiredMixin, View):
    """Canonical entry: /crm/agency/ → dashboard or member view."""

    def get(self, request, *args, **kwargs):
        from workspace.services.agency_entitlement import can_manage_agency, has_assigned_agency_seat
        from workspace.services.crm_scope import can_manage_team

        user = request.user
        if can_manage_agency(user) or can_manage_team(user):
            return redirect('workspace:agency_hub_dashboard')
        if has_assigned_agency_seat(user):
            return redirect('workspace:agency_advisor_member')
        return redirect('workspace:agency_hub_dashboard')


class AgencyTeamActionView(CRMTeamView):
    """POST endpoint for agency/team forms — GET redirects to dashboard."""

    def get(self, request, *args, **kwargs):
        return redirect('workspace:agency_hub_dashboard')
