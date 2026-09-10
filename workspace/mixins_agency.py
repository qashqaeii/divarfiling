"""Mixinهای دسترسی بخش آژانس — enforce در Backend."""
from __future__ import annotations

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse

from workspace.services.agency_entitlement import (
    agency_hub_access_level,
    can_manage_agency,
    get_active_subscription_for_owner,
    is_expired_agency_owner,
)


class AgencyHubAccessMixin:
    """دسترسی به hub آژانس — Owner با Subscription یا Advisor با Seat معتبر."""

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()
        level = agency_hub_access_level(user)
        if level == 'none':
            return self._deny(request, 'بخش آژانس فقط برای مشترکین پلن آژانس در دسترس است.')
        if level == 'owner_locked':
            return HttpResponseRedirect(reverse('workspace:agency_locked'))
        return super().dispatch(request, *args, **kwargs)

    def _deny(self, request, message: str):
        messages.error(request, message)
        return HttpResponseRedirect(reverse('workspace:crm_dashboard'))


class AgencyOwnerRequiredMixin:
    """فقط Owner با AgencySubscription فعال."""

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()
        if is_expired_agency_owner(user):
            return HttpResponseRedirect(reverse('workspace:agency_locked'))
        if not can_manage_agency(user):
            return self._deny(request)
        return super().dispatch(request, *args, **kwargs)

    def _deny(self, request):
        messages.error(request, 'دسترسی مدیریت آژانس ندارید.')
        return HttpResponseRedirect(reverse('workspace:crm_dashboard'))


class AgencyManageAPIPermissionMixin:
    def permission_denied_response(self, request):
        from django.http import JsonResponse
        return JsonResponse({'error': 'دسترسی آژانس مجاز نیست'}, status=403)

    def check_agency_owner(self, request):
        from workspace.services.crm_scope import get_membership
        membership = get_membership(request.user)
        agency = membership.agency if membership else None
        if is_expired_agency_owner(request.user):
            return False
        return can_manage_agency(request.user, agency)
