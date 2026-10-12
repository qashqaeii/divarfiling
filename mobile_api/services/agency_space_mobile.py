"""Agency Space — Mobile API payloads (reuse workspace services)."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from workspace.models import CRMProperty, Customer
from workspace.services.agency_space_access import (
    can_access_agency_space,
    can_moderate_agency_space,
    can_publish_to_agency_space,
    get_user_space_agency,
)
from workspace.services.agency_space_analytics import can_view_space_analytics
from workspace.services.agency_space_provenance import provenance_for_customer, provenance_for_property
from workspace.services.agency_space_query import get_active_space_item_for_source
from workspace.services.agency_space_serialize import serialize_space_item, serialize_space_item_safe_metadata
from workspace.services.crm_agency_features import is_agency_feature_enabled
from workspace.services.crm_scope import agency_members, get_membership, is_customer_owner, is_property_owner


def agency_space_capabilities(user, agency=None) -> Dict[str, bool]:
    agency = agency or get_user_space_agency(user)
    enabled = is_agency_feature_enabled('agency_space', agency) if agency else False
    if not enabled or not agency:
        return {
            'agency_space_enabled': False,
            'can_access_agency_space': False,
            'can_publish_agency_space': False,
            'can_view_space_analytics': False,
            'can_moderate_agency_space': False,
        }
    return {
        'agency_space_enabled': True,
        'can_access_agency_space': can_access_agency_space(user, agency),
        'can_publish_agency_space': can_publish_to_agency_space(user, agency),
        'can_view_space_analytics': can_view_space_analytics(user, agency),
        'can_moderate_agency_space': can_moderate_agency_space(user, agency),
    }


def require_agency_space_access(user) -> Tuple[Optional[Any], Optional[Dict[str, Any]]]:
    """Returns (agency, error_payload) where error_payload is api_error kwargs dict."""
    agency = get_user_space_agency(user)
    if not is_agency_feature_enabled('agency_space', agency):
        return None, {'message': 'قابلیت فعال نیست.', 'code': 'NOT_FOUND', 'status': 404}
    if not can_access_agency_space(user, agency):
        return None, {'message': 'دسترسی مجاز نیست.', 'code': 'FORBIDDEN', 'status': 403}
    return agency, None


def mobile_provenance_for_property(prop: CRMProperty, viewer) -> Optional[Dict[str, Any]]:
    raw = provenance_for_property(prop, viewer)
    if not raw:
        return None
    return {
        'label': raw.get('label', ''),
        'publisher_name': raw.get('publisher_name', ''),
        'copied_at': raw.get('copied_at', ''),
        'space_item_id': raw.get('space_item_id'),
    }


def mobile_provenance_for_customer(customer: Customer, viewer) -> Optional[Dict[str, Any]]:
    raw = provenance_for_customer(customer, viewer)
    if not raw:
        return None
    return {
        'label': raw.get('label', ''),
        'publisher_name': raw.get('publisher_name', ''),
        'copied_at': raw.get('copied_at', ''),
        'space_item_id': raw.get('space_item_id'),
    }


def mobile_source_context(
    user,
    *,
    property: Optional[CRMProperty] = None,
    customer: Optional[Customer] = None,
) -> Dict[str, Any]:
    agency = get_user_space_agency(user)
    caps = agency_space_capabilities(user, agency)
    base: Dict[str, Any] = {
        **caps,
        'source_kind': '',
        'property_id': None,
        'customer_id': None,
        'can_publish': False,
        'active_item_id': None,
        'active_item': None,
        'team_members': [],
    }
    if not caps['agency_space_enabled'] or not agency:
        return base

    active = None
    if property is not None:
        base['source_kind'] = 'property'
        base['property_id'] = property.pk
        if is_property_owner(user, property):
            active = get_active_space_item_for_source(user, property_id=property.pk)
            base['can_publish'] = can_publish_to_agency_space(user, agency)
    elif customer is not None:
        base['source_kind'] = 'customer'
        base['customer_id'] = customer.pk
        if is_customer_owner(user, customer):
            active = get_active_space_item_for_source(user, customer_id=customer.pk)
            base['can_publish'] = can_publish_to_agency_space(user, agency)

    if active:
        base['active_item_id'] = active.pk
        base['active_item'] = serialize_space_item_safe_metadata(active, user)

    membership = get_membership(user)
    if membership and base['can_publish']:
        base['team_members'] = [
            {
                'id': m.pk,
                'user_id': m.user_id,
                'name': m.user.get_full_name() or m.user.phone or m.user.username,
                'role': m.role,
            }
            for m in agency_members(agency)
            if m.is_active and m.user_id != user.id
        ]
    return base


def space_item_payload(item, user, *, detail: bool = False, request=None) -> Optional[Dict[str, Any]]:
    return serialize_space_item(item, user, detail=detail, request=request)
