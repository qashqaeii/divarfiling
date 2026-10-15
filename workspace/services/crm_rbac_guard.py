"""محدودیت CRM برای نقش منشی — فقط با agency_rbac_v2 فعال."""
from __future__ import annotations

from django.core.exceptions import PermissionDenied

from workspace.services.agency_rbac import NAV_PROFILE_SECRETARY, is_agency_rbac_v2_enabled, resolve_nav_profile
from workspace.services.crm_scope import get_membership


def assert_crm_deals_access_allowed(user) -> None:
    m = get_membership(user)
    if not m or not is_agency_rbac_v2_enabled(m.agency):
        return
    if resolve_nav_profile(user) == NAV_PROFILE_SECRETARY:
        raise PermissionDenied('دسترسی قیف معاملات برای منشی مجاز نیست')


def assert_crm_contracts_access_allowed(user) -> None:
    m = get_membership(user)
    if not m or not is_agency_rbac_v2_enabled(m.agency):
        return
    if resolve_nav_profile(user) == NAV_PROFILE_SECRETARY:
        raise PermissionDenied('دسترسی قراردادها برای منشی مجاز نیست')


def assert_crm_finance_dashboard_allowed(user) -> None:
    """مالی تیم — منشی ممنوع؛ مشاور مالی شخصی؛ مالک/مدیر با مجوز."""
    from workspace.services.agency_rbac import (
        NAV_PROFILE_ADVISOR,
        NAV_PROFILE_SECRETARY,
        PERM_FINANCE_VIEW,
        has_agency_permission,
    )

    m = get_membership(user)
    if not m or not is_agency_rbac_v2_enabled(m.agency):
        return
    profile = resolve_nav_profile(user)
    if profile == NAV_PROFILE_SECRETARY:
        raise PermissionDenied('دسترسی مالی معاملات مجاز نیست')
    if profile == NAV_PROFILE_ADVISOR:
        return
    if not has_agency_permission(user, PERM_FINANCE_VIEW, member=m):
        raise PermissionDenied('دسترسی مالی معاملات مجاز نیست')
