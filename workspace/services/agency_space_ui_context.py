"""Context helpers for CRM detail + Agency Hub Space UI."""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.urls import reverse

from workspace.models import CRMProperty, Customer
from workspace.services.agency_space_access import (
    can_publish_to_agency_space,
    get_user_space_agency,
)
from workspace.services.agency_space_query import get_active_space_item_for_source
from workspace.services.crm_agency_features import is_agency_feature_enabled
from workspace.services.crm_scope import agency_members, get_membership, is_customer_owner, is_property_owner


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
