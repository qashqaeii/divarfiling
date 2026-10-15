"""دسترسی فضای آژانس — نقطه مرکزی permission (Phase 1)."""
from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model

from workspace.constants import (
    AGENCY_ROLE_ADVISOR,
    AGENCY_ROLE_MANAGER,
    AGENCY_ROLE_OWNER,
    AGENCY_ROLE_SECRETARY,
)
from workspace.models import AgencySpaceItem, CRMAgency, CRMAgencyMember
from workspace.services.agency_entitlement import (
    can_manage_agency,
    get_subscription_for_agency,
    has_assigned_agency_seat,
)
from workspace.services.crm_scope import can_manage_team, get_membership

User = get_user_model()


def get_user_space_agency(user) -> Optional[CRMAgency]:
    """آژانس فعال کاربر برای Space — membership + subscription آژانس."""
    if not user or not user.is_authenticated:
        return None
    membership = get_membership(user)
    if not membership or not membership.is_active:
        return None
    agency = membership.agency
    if not get_subscription_for_agency(agency):
        return None
    return agency


def can_access_agency_space(user, agency: Optional[CRMAgency] = None) -> bool:
    """عضو فعال با اشتراک آژانس فعال — شامل مشاور بدون seat (read)."""
    agency = agency or get_user_space_agency(user)
    if not agency:
        return False
    membership = get_membership(user)
    if not membership or membership.agency_id != agency.id or not membership.is_active:
        return False
    return get_subscription_for_agency(agency) is not None


def can_publish_to_agency_space(user, agency: Optional[CRMAgency] = None) -> bool:
    if not can_access_agency_space(user, agency):
        return False
    agency = agency or get_user_space_agency(user)
    membership = get_membership(user)
    if not membership:
        return False
    if membership.role == AGENCY_ROLE_SECRETARY:
        return False
    if can_manage_agency(user, agency):
        return True
    if membership.role == AGENCY_ROLE_MANAGER:
        return True
    if membership.role in (AGENCY_ROLE_OWNER, AGENCY_ROLE_ADVISOR):
        if membership.role == AGENCY_ROLE_ADVISOR:
            return has_assigned_agency_seat(user)
        return True
    return False


def can_moderate_agency_space(user, agency: Optional[CRMAgency] = None) -> bool:
    if not can_access_agency_space(user, agency):
        return False
    from workspace.services.agency_rbac import PERM_AGENCY_SPACE_MODERATE, has_agency_permission, is_agency_rbac_v2_enabled

    agency = agency or get_user_space_agency(user)
    if agency and is_agency_rbac_v2_enabled(agency):
        return has_agency_permission(user, PERM_AGENCY_SPACE_MODERATE)
    return can_manage_team(user)


def can_edit_space_item(user, item: AgencySpaceItem) -> bool:
    if not item or item.status != AgencySpaceItem.STATUS_ACTIVE:
        return False
    if not can_access_agency_space(user, item.agency):
        return False
    return item.publisher_id == user.id


def can_unpublish_space_item(user, item: AgencySpaceItem) -> bool:
    if not item or item.status != AgencySpaceItem.STATUS_ACTIVE:
        return False
    if can_edit_space_item(user, item):
        return True
    return can_moderate_agency_space(user, item.agency)


def _user_in_audience(user, item: AgencySpaceItem) -> bool:
    membership = get_membership(user)
    if not membership or membership.agency_id != item.agency_id:
        return False
    return item.audience_members.filter(member_id=membership.pk).exists()


def can_view_space_item(user, item: AgencySpaceItem) -> bool:
    if not item:
        return False
    if not can_access_agency_space(user, item.agency):
        return False
    if item.status == AgencySpaceItem.STATUS_ARCHIVED:
        return item.publisher_id == user.id or can_moderate_agency_space(user, item.agency)
    if item.status == AgencySpaceItem.STATUS_MODERATION_HIDDEN:
        if item.publisher_id == user.id:
            return True
        if can_moderate_agency_space(user, item.agency):
            return True
        return False
    if item.publisher_id == user.id:
        return True
    if item.visibility == AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC:
        return True
    if item.visibility == AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS:
        return _user_in_audience(user, item)
    return False


def can_view_space_item_content(user, item: AgencySpaceItem) -> bool:
    """محتوای کامل — همان can_view برای Phase 1 (moderation بدون leak)."""
    return can_view_space_item(user, item)


def can_view_space_item_safe_metadata(user, item: AgencySpaceItem) -> bool:
    """metadata امن برای moderation بدون دسترسی به confidential content."""
    if not can_access_agency_space(user, item.agency):
        return False
    if not can_moderate_agency_space(user, item.agency):
        return False
    return item.status in (
        AgencySpaceItem.STATUS_ACTIVE,
        AgencySpaceItem.STATUS_MODERATION_HIDDEN,
    )


def can_copy_from_agency_space(user, item: AgencySpaceItem) -> bool:
    """کپی به CRM شخصی — همان محدودیت publish (seat، بدون secretary)."""
    if not item or item.status != AgencySpaceItem.STATUS_ACTIVE:
        return False
    if not can_view_space_item(user, item):
        return False
    if not can_publish_to_agency_space(user, item.agency):
        return False
    if item.property_id and item.property and item.property.user_id == user.id:
        return False
    if item.customer_id and item.customer and item.customer.user_id == user.id:
        return False
    return True


def assert_can_copy_from_agency_space(user, item: AgencySpaceItem) -> None:
    if not can_copy_from_agency_space(user, item):
        raise PermissionError('دسترسی کپی از فضای آژانس ندارید')


def assert_can_publish(user, agency: CRMAgency) -> None:
    if not can_publish_to_agency_space(user, agency):
        raise PermissionError('دسترسی انتشار در فضای آژانس ندارید')


def assert_can_view(user, item: AgencySpaceItem) -> None:
    if not can_view_space_item(user, item):
        raise PermissionError('دسترسی به این آیتم فضای آژانس ندارید')
