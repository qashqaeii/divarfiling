"""Agency Hub — Dashboard, Advisors, Licenses, Activity, Settings."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from workspace.mixins_agency import AgencyOwnerRequiredMixin
from workspace.services.agency_hub import (
    build_activity_feed,
    build_dashboard_context,
    hub_base_context,
)
from workspace.services.agency_members import build_members_dashboard
from workspace.services.agency_seats import list_available_seats


class _AgencyHubBase(AgencyOwnerRequiredMixin, LoginRequiredMixin, TemplateView):
    hub_section = ''

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(hub_base_context(self.request.user))
        ctx['crm_section'] = 'agency'
        ctx['hub_section'] = self.hub_section
        from workspace.services.agency_activity import EVENT_TYPE_LABELS
        ctx['agency_event_labels'] = EVENT_TYPE_LABELS
        ctx['hub_nav'] = [
            ('dashboard', 'داشبورد', reverse('workspace:agency_hub_dashboard')),
            ('advisors', 'مشاوران', reverse('workspace:agency_hub_advisors')),
            ('licenses', 'لایسنس‌ها', reverse('workspace:agency_hub_licenses')),
            ('activity', 'فعالیت تیم', reverse('workspace:agency_hub_activity')),
            ('settings', 'تنظیمات', reverse('workspace:agency_hub_settings')),
        ]
        return ctx


class AgencyHubDashboardView(_AgencyHubBase):
    template_name = 'workspace/crm/agency/hub_dashboard.html'
    hub_section = 'dashboard'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        days = int(self.request.GET.get('days', 30) or 30)
        if days not in (7, 30, 90):
            days = 30
        ctx.update(build_dashboard_context(self.request.user, days=days))
        return ctx


class AgencyHubAdvisorsView(_AgencyHubBase):
    template_name = 'workspace/crm/agency/hub_advisors.html'
    hub_section = 'advisors'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        agency = ctx['hub_agency']
        if agency:
            ctx['members_dashboard'] = build_members_dashboard(self.request.user, agency)
            ctx['available_seats'] = list_available_seats(self.request.user, agency)
            ctx['team_export_url'] = reverse('workspace:agency_team_export')
            ctx['crm_team_url'] = reverse('workspace:crm_team')
        return ctx


class AgencyHubLicensesView(_AgencyHubBase):
    template_name = 'workspace/crm/agency/hub_licenses.html'
    hub_section = 'licenses'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        agency = ctx['hub_agency']
        if agency:
            from licenses.services.management import build_agency_license_pool
            ctx['license_pool'] = build_agency_license_pool(agency.owner)
        return ctx


class AgencyHubActivityView(_AgencyHubBase):
    template_name = 'workspace/crm/agency/hub_activity.html'
    hub_section = 'activity'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from workspace.services.agency_data_scope import list_visible_advisor_members
        ctx['advisors'] = list(list_visible_advisor_members(self.request.user))
        member_id = self.request.GET.get('advisor')
        actor_user_id = None
        if member_id and member_id.isdigit():
            from workspace.services.agency_data_scope import resolve_visible_agency_member
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


class AgencyHubSettingsView(_AgencyHubBase):
    template_name = 'workspace/crm/agency/hub_settings.html'
    hub_section = 'settings'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['legacy_team_url'] = reverse('workspace:crm_team') + '?tab=settings'
        ctx['advanced_tabs'] = [
            ('webhooks', 'Webhooks', reverse('workspace:crm_team') + '?tab=webhooks'),
            ('sync', 'Sync', reverse('workspace:crm_team') + '?tab=sync'),
            ('transfers', 'انتقال‌ها', reverse('workspace:crm_team') + '?tab=transfers'),
            ('audit', 'Audit', reverse('workspace:crm_team') + '?tab=audit'),
            ('messages', 'پیام‌ها', reverse('workspace:crm_team') + '?tab=messages'),
            ('announcements', 'اطلاعیه‌ها', reverse('workspace:crm_team') + '?tab=announcements'),
            ('tv', 'TV', reverse('workspace:crm_team_tv')),
        ]
        return ctx


class AgencyHubRedirectView(LoginRequiredMixin, TemplateView):
    """Owner → hub dashboard; others → legacy team."""

    def get(self, request, *args, **kwargs):
        from workspace.services.agency_entitlement import can_manage_agency
        if can_manage_agency(request.user):
            return redirect('workspace:agency_hub_dashboard')
        return redirect('workspace:crm_team')
