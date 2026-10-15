"""Mixinهای دسترسی بخش آژانس — enforce در Backend."""
from __future__ import annotations

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse

from workspace.services.agency_entitlement import (
    agency_hub_access_level,
    can_access_agency_hub,
    can_manage_agency,
    get_subscription_for_agency,
    has_assigned_agency_seat,
    is_expired_agency_owner,
)
from workspace.services.crm_scope import can_manage_team, get_membership


class AgencyHubAccessMixin:
    """دسترسی به hub آژانس — Owner با Subscription یا Advisor با Seat معتبر."""

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()
        level = agency_hub_access_level(user)
        if level == 'none' and not can_access_agency_hub(user):
            return self._deny(request, 'بخش آژانس فقط برای مشترکین پلن آژانس در دسترس است.')
        if level == 'owner_locked':
            return HttpResponseRedirect(reverse('workspace:agency_locked'))
        return super().dispatch(request, *args, **kwargs)

    def _deny(self, request, message: str):
        messages.error(request, message)
        return HttpResponseRedirect(reverse('workspace:crm_dashboard'))


class AgencyTeamHubRequiredMixin(AgencyHubAccessMixin):
    """Owner، مدیر تیم با اشتراک فعال — مشاور بدون نقش مدیریتی به member view."""

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()

        from workspace.services.agency_rbac import (
            NAV_PROFILE_SECRETARY,
            is_agency_secretary_hub_enabled,
            resolve_nav_profile,
            staff_can_access_agency_hub_without_seat,
        )
        from workspace.services.crm_scope import get_membership

        membership = get_membership(user)
        agency = membership.agency if membership else None
        if (
            resolve_nav_profile(user) == NAV_PROFILE_SECRETARY
            and agency
            and is_agency_secretary_hub_enabled(agency)
        ):
            return super().dispatch(request, *args, **kwargs)

        if (
            has_assigned_agency_seat(user)
            and not can_manage_agency(user)
            and not can_manage_team(user)
            and not staff_can_access_agency_hub_without_seat(user)
        ):
            return HttpResponseRedirect(reverse('workspace:agency_advisor_member'))

        level = agency_hub_access_level(user)
        if level == 'advisor' and not can_manage_team(user):
            return HttpResponseRedirect(reverse('workspace:agency_advisor_member'))

        return super().dispatch(request, *args, **kwargs)


class AgencyOwnerRequiredMixin:
    """فقط مالک اشتراک آژانس (AgencySubscription فعال) — نه override مجوز."""

    def dispatch(self, request, *args, **kwargs):
        from workspace.services.agency_rbac import (
            PERM_LICENSES_MANAGE,
            has_agency_permission,
            rbac_v2_enabled_for_user,
        )

        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()
        membership = get_membership(user)
        agency = membership.agency if membership else None
        if is_expired_agency_owner(user):
            return HttpResponseRedirect(reverse('workspace:agency_locked'))
        if not can_manage_agency(user, agency):
            return self._deny(request)
        if rbac_v2_enabled_for_user(user) and not has_agency_permission(
            user, PERM_LICENSES_MANAGE, member=membership,
        ):
            return self._deny(request)
        return super().dispatch(request, *args, **kwargs)

    def _deny(self, request):
        messages.error(request, 'دسترسی مدیریت آژانس ندارید.')
        return HttpResponseRedirect(reverse('workspace:crm_dashboard'))


class AgencySettingsAccessMixin:
    """تنظیمات آژانس — منشی بدون مجوز settings.manage مسدود."""

    def dispatch(self, request, *args, **kwargs):
        from workspace.services.agency_rbac import (
            PERM_SETTINGS_MANAGE,
            has_agency_permission,
            rbac_v2_enabled_for_user,
        )

        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()
        if rbac_v2_enabled_for_user(user):
            if not has_agency_permission(user, PERM_SETTINGS_MANAGE):
                messages.error(request, 'دسترسی تنظیمات آژانس ندارید.')
                return HttpResponseRedirect(reverse('workspace:agency_hub_dashboard'))
        elif not (can_manage_team(user) or can_manage_agency(user)):
            messages.error(request, 'دسترسی تنظیمات آژانس ندارید.')
            return HttpResponseRedirect(reverse('workspace:agency_hub_dashboard'))
        return super().dispatch(request, *args, **kwargs)


class AgencyTeamManageRequiredMixin(AgencyHubAccessMixin):
    """مدیریت تیم — مالک اشتراک، مدیر legacy، یا RBAC v2 با team.manage."""

    def dispatch(self, request, *args, **kwargs):
        from workspace.services.agency_rbac import (
            PERM_TEAM_MANAGE,
            has_agency_permission,
            rbac_v2_enabled_for_user,
        )

        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()
        if rbac_v2_enabled_for_user(user):
            if not has_agency_permission(user, PERM_TEAM_MANAGE):
                return self._deny_team(request)
        elif not (can_manage_team(user) or can_manage_agency(user)):
            return self._deny_team(request)
        return super().dispatch(request, *args, **kwargs)

    def _deny_team(self, request):
        messages.error(request, 'دسترسی مدیریت تیم ندارید.')
        return HttpResponseRedirect(reverse('workspace:crm_dashboard'))


class AgencyTeamPerformanceRequiredMixin(AgencyHubAccessMixin):
    """مشاهده عملکرد/Advisor 360."""

    def dispatch(self, request, *args, **kwargs):
        from workspace.services.agency_rbac import (
            PERM_TEAM_VIEW_PERFORMANCE,
            has_agency_permission,
            rbac_v2_enabled_for_user,
        )

        user = request.user
        if not user.is_authenticated:
            return self.handle_no_permission()
        if rbac_v2_enabled_for_user(user):
            if not has_agency_permission(user, PERM_TEAM_VIEW_PERFORMANCE):
                return self._deny_perf(request)
        elif not (can_manage_team(user) or can_manage_agency(user)):
            return self._deny_perf(request)
        return super().dispatch(request, *args, **kwargs)

    def _deny_perf(self, request):
        messages.error(request, 'دسترسی مشاهده عملکرد تیم ندارید.')
        return HttpResponseRedirect(reverse('workspace:agency_hub_dashboard'))


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
