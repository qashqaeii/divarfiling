"""Context helpers for CRM detail + Agency Hub Space UI."""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.urls import reverse

from workspace.models import AgencySpaceItem, CRMProperty, Customer
from workspace.services.agency_space_access import (
    can_publish_to_agency_space,
    get_user_space_agency,
)
from workspace.services.agency_space_query import get_active_space_item_for_source
from workspace.services.crm_agency_features import is_agency_feature_enabled
from workspace.services.crm_scope import agency_members, get_membership, is_customer_owner, is_property_owner
from workspace.services.user_display import user_display_name


def build_space_publisher_filter_options(request, agency, selected_publisher_id=None):
    """اعضای فعال آژانس برای فیلتر مشاور — آواتار + badge نقش."""
    if not agency:
        return []
    from accounts.avatar_catalog import consultant_portrait_url
    from workspace.constants import AGENCY_ROLE_STYLES
    from workspace.models import WorkspaceSettings

    members = [m for m in agency_members(agency) if m.is_active]
    user_ids = [m.user_id for m in members]
    ws_map = {
        row.user_id: row
        for row in WorkspaceSettings.objects.filter(user_id__in=user_ids).only(
            'user_id', 'consultant_photo',
        )
    }
    try:
        selected = int(selected_publisher_id) if selected_publisher_id else None
    except (TypeError, ValueError):
        selected = None
    options = []
    for membership in members:
        role = membership.role
        role_bg, role_fg = AGENCY_ROLE_STYLES.get(role, ('#f1f5f9', '#64748b'))
        ws = ws_map.get(membership.user_id)
        options.append({
            'user_id': membership.user_id,
            'name': user_display_name(membership.user),
            'role': role,
            'role_label': membership.get_role_display(),
            'avatar_url': consultant_portrait_url(
                membership.user, ws_settings=ws, request=request,
            ),
            'role_bg': role_bg,
            'role_fg': role_fg,
            'selected': selected == membership.user_id,
        })
    return options


def prefetch_publisher_workspace_for_space_items(items) -> None:
    """یک کوئری WorkspaceSettings برای آواتار منتشرکننده در لیست."""
    from workspace.models import WorkspaceSettings

    user_ids = {item.publisher_id for item in items if getattr(item, 'publisher_id', None)}
    if not user_ids:
        return
    ws_map = {
        row.user_id: row
        for row in WorkspaceSettings.objects.filter(user_id__in=user_ids).only(
            'user_id', 'consultant_photo',
        )
    }
    for item in items:
        pub = getattr(item, 'publisher', None)
        if pub is not None:
            pub._space_ws_settings = ws_map.get(pub.pk)


def apply_agency_space_crm_context(
    ctx: Dict[str, Any],
    user,
    *,
    property: Optional[CRMProperty] = None,
    customer: Optional[Customer] = None,
) -> None:
    agency = get_user_space_agency(user)
    enabled = is_agency_feature_enabled('agency_space', agency)
    ctx['agency_space_enabled'] = enabled
    ctx['agency_space_can_publish'] = False
    ctx['agency_space_item'] = None
    ctx['agency_space_manage_url'] = ''
    ctx['agency_space_api_base'] = reverse('workspace:api_agency_space_items')
    if not enabled or not agency:
        return
    is_owner = False
    ctx['agency_space_source_kind'] = ''
    ctx['agency_space_property_id'] = ''
    ctx['agency_space_customer_id'] = ''
    if property is not None:
        is_owner = is_property_owner(user, property)
        active = get_active_space_item_for_source(user, property_id=property.pk) if is_owner else None
        ctx['agency_space_source_kind'] = 'property'
        ctx['agency_space_property_id'] = property.pk
    elif customer is not None:
        is_owner = is_customer_owner(user, customer)
        active = get_active_space_item_for_source(user, customer_id=customer.pk) if is_owner else None
        ctx['agency_space_source_kind'] = 'customer'
        ctx['agency_space_customer_id'] = customer.pk
    else:
        active = None
    ctx['agency_space_can_publish'] = is_owner and can_publish_to_agency_space(user, agency)
    if active:
        ctx['agency_space_item'] = active
        ctx['agency_space_manage_url'] = reverse(
            'workspace:agency_hub_space_item',
            kwargs={'item_id': active.pk},
        )
    membership = get_membership(user)
    if membership and ctx['agency_space_can_publish']:
        ctx['agency_space_team_members'] = [
            m for m in agency_members(agency)
            if m.is_active and m.user_id != user.id
        ]
    else:
        ctx['agency_space_team_members'] = []


def apply_agency_space_item_detail_context(
    ctx: Dict[str, Any],
    user,
    item: AgencySpaceItem,
    payload: Dict[str, Any],
) -> None:
    """Context for hub space item detail — edit publication modal + API URLs."""
    agency = item.agency
    ctx['agency_space_enabled'] = is_agency_feature_enabled('agency_space', agency)
    ctx['agency_space_edit_mode'] = bool(payload.get('can_edit'))
    ctx['agency_space_can_publish'] = ctx['agency_space_edit_mode']
    ctx['agency_space_item'] = item
    ctx['agency_space_source_kind'] = item.content_kind()
    ctx['agency_space_property_id'] = item.property_id or ''
    ctx['agency_space_customer_id'] = item.customer_id or ''
    ctx['agency_space_api_base'] = reverse('workspace:api_agency_space_items')
    ctx['agency_space_manage_url'] = reverse(
        'workspace:agency_hub_space_item',
        kwargs={'item_id': item.pk},
    )
    if ctx['agency_space_can_publish'] and agency:
        ctx['agency_space_team_members'] = ctx.get('space_team_members') or [
            m for m in agency_members(agency)
            if m.is_active and m.user_id != user.id
        ]
    else:
        ctx['agency_space_team_members'] = []
    ctx['space_edit_config'] = {
        'visibility': item.visibility,
        'contact_share_level': item.contact_share_level or AgencySpaceItem.CONTACT_SUMMARY,
        'note': item.note or '',
        'member_ids': payload.get('audience_member_ids') or [],
    }
