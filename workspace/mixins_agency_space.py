"""Mixin صفحات فضای آژانس."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.urls import reverse

from workspace.services.agency_space_access import can_access_agency_space, get_user_space_agency
from workspace.services.crm_agency_features import is_agency_feature_enabled


class AgencySpaceFeatureMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        agency = get_user_space_agency(request.user)
        if not is_agency_feature_enabled('agency_space', agency):
            messages.error(request, 'فضای آژانس در حال حاضر فعال نیست.')
            return HttpResponseRedirect(reverse('workspace:crm_dashboard'))
        if not can_access_agency_space(request.user, agency):
            messages.error(request, 'دسترسی به فضای آژانس ندارید.')
            return HttpResponseRedirect(reverse('workspace:crm_dashboard'))
        return super().dispatch(request, *args, **kwargs)
