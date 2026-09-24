"""Serialization امن Agency Space — phone masking در backend."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model

from workspace.models import AgencySpaceItem, CRMProperty, Customer
from workspace.services.user_display import user_display_name
from workspace.services.agency_space_access import (
    can_copy_from_agency_space,
    can_view_space_item,
    can_view_space_item_content,
)
from workspace.services.agency_space_copy import space_copy_target_url
from workspace.models import AgencySpaceCopy
from workspace.services.crm_scope import get_membership
from workspace.services.display import to_jalali_display
from workspace.services.formatting import format_area, format_toman

User = get_user_model()


def _viewer_owns_space_source(viewer: User, item: AgencySpaceItem) -> bool:
    """انتشار از همان فایل/مخاطب CRM خود کاربر — کپی جدا لازم نیست."""
    if item.property_id and item.property:
        return item.property.user_id == viewer.id
    if item.customer_id and item.customer:
        return item.customer.user_id == viewer.id
    return False


def _property_price_label(prop: CRMProperty) -> str:
    parts = []
    if prop.deposit:
        parts.append(f'رهن {format_toman(prop.deposit)}')
    if prop.monthly_rent:
        parts.append(f'اجاره {format_toman(prop.monthly_rent)}')
    if parts:
        return ' · '.join(parts)
    if prop.sale_price:
        return format_toman(prop.sale_price)
    return ''


def _customer_budget_label(customer: Customer) -> str:
    if customer.budget_min and customer.budget_max:
        return f'{format_toman(customer.budget_min)} تا {format_toman(customer.budget_max)}'
    if customer.budget_max:
        return f'تا {format_toman(customer.budget_max)}'
    if customer.budget_min:
        return f'از {format_toman(customer.budget_min)}'
    return ''


def _format_published_at(dt) -> str:
    if not dt:
        return ''
    return to_jalali_display(dt)


def _publisher_payload(user: User) -> Dict[str, Any]:
    pref = getattr(user, '_space_pub_membership', None)
    if pref:
        membership = pref[0] if pref else None
    else:
        membership = (
            user.crm_agency_memberships.filter(is_active=True).select_related('agency').first()
        )
    role = membership.role if membership else ''
    role_label = ''
    if membership:
        role_label = dict(membership._meta.get_field('role').choices).get(role, role)
    return {
        'id': user.pk,
        'name': user_display_name(user),
        'role': role,
        'role_label': role_label,
    }


def _property_card(prop: CRMProperty, *, include_sensitive: bool) -> Dict[str, Any]:
    images: List[str] = []
    if prop.images and isinstance(prop.images, list):
        images = [u for u in prop.images if isinstance(u, str) and u.strip()][:12]
    thumb = images[0] if images else ''
    area = prop.area
    area_label = format_area(area) if area not in (None, '') else ''
    region = ' · '.join(p for p in (prop.neighborhood, prop.district, prop.city) if p)
    data = {
        'id': prop.pk,
        'title': prop.title,
        'thumbnail_url': thumb,
        'images': images if include_sensitive else ([thumb] if thumb else []),
        'price_label': _property_price_label(prop),
        'area': area,
        'area_label': area_label,
        'region': region,
        'property_type': prop.property_type,
        'deal_mode': prop.deal_mode,
        'transaction_status': prop.transaction_status,
        'rooms': prop.rooms or '',
        'floor': prop.floor,
        'total_floors': prop.total_floors,
        'build_year': prop.build_year,
        'city': prop.city or '',
        'district': prop.district or '',
        'neighborhood': prop.neighborhood or '',
    }
    if include_sensitive:
        data['address'] = prop.address
        data['phone'] = prop.phone
        data['notes'] = prop.notes
        data['amenities'] = (prop.amenities or '')[:1200]
        data['has_parking'] = prop.has_parking
        data['has_elevator'] = prop.has_elevator
        data['has_storage'] = prop.has_storage
        data['is_vacant'] = prop.is_vacant
    return data


def _customer_payload(
    customer: Customer,
    item: AgencySpaceItem,
    viewer: User,
    *,
    detail: bool,
) -> Dict[str, Any]:
    can_full = (
        item.contact_share_level == AgencySpaceItem.CONTACT_FULL
        and can_view_space_item_content(viewer, item)
    )
    region = ' · '.join(p for p in (customer.district, customer.city, customer.areas) if p)
    data = {
        'id': customer.pk,
        'name': customer.name,
        'customer_type': customer.customer_type,
        'need_summary': (customer.notes or '')[:300] if detail else (customer.notes or '')[:120],
        'budget_label': _customer_budget_label(customer),
        'region': region,
        'status': customer.status,
    }
    if can_full:
        data['phone'] = customer.phone
        data['phone_alt'] = customer.phone_alt
        data['email'] = customer.email
    else:
        data['phone'] = ''
        data['phone_alt'] = ''
        data['email'] = ''
    data['contact_share_level'] = item.contact_share_level
    data['contact_share_level_label'] = dict(
        AgencySpaceItem.CONTACT_SHARE_LEVEL_CHOICES,
    ).get(item.contact_share_level, item.contact_share_level)
    if detail:
        data['notes'] = (customer.notes or '')[:800]
    return data


def visibility_label(visibility: str) -> str:
    return dict(AgencySpaceItem.VISIBILITY_CHOICES).get(visibility, visibility)


def serialize_space_item(
    item: AgencySpaceItem,
    viewer: User,
    *,
    detail: bool = False,
) -> Optional[Dict[str, Any]]:
    if not can_view_space_item(viewer, item):
        return None
    include_sensitive = detail and item.content_kind() == 'property'
    payload: Dict[str, Any] = {
        'id': item.pk,
        'agency_id': item.agency_id,
        'source_kind': item.content_kind(),
        'visibility': item.visibility,
        'visibility_label': visibility_label(item.visibility),
        'status': item.status,
        'status_label': dict(AgencySpaceItem.STATUS_CHOICES).get(item.status, item.status),
        'archived_at': item.archived_at.isoformat() if item.archived_at else '',
        'archived_reason': item.archived_reason or '',
        'archived_reason_label': (
            dict(AgencySpaceItem.ARCHIVED_REASON_CHOICES).get(item.archived_reason, '')
            if item.archived_reason else ''
        ),
        'note': item.note,
        'published_at': item.published_at.isoformat() if item.published_at else '',
        'published_at_display': _format_published_at(item.published_at),
        'updated_at': item.updated_at.isoformat() if item.updated_at else '',
        'updated_at_display': _format_published_at(item.updated_at),
        'archived_at_display': _format_published_at(item.archived_at) if item.archived_at else '',
        'publisher': _publisher_payload(item.publisher),
        'is_publisher': item.publisher_id == viewer.id,
        'can_edit': item.publisher_id == viewer.id and item.status == AgencySpaceItem.STATUS_ACTIVE,
        'can_unpublish': item.publisher_id == viewer.id and item.status == AgencySpaceItem.STATUS_ACTIVE,
    }
    membership = get_membership(viewer)
    from workspace.services.agency_space_access import can_moderate_agency_space, can_unpublish_space_item

    payload['can_unpublish'] = can_unpublish_space_item(viewer, item)
    payload['can_moderate'] = (
        can_moderate_agency_space(viewer, item.agency)
        and item.status == AgencySpaceItem.STATUS_ACTIVE
        and item.visibility == AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC
    )
    if item.property_id and item.property:
        payload['property'] = _property_card(item.property, include_sensitive=include_sensitive)
    elif item.property_id:
        payload['property'] = {'id': item.property_id, 'missing': True}
    if item.customer_id and item.customer:
        payload['customer'] = _customer_payload(item.customer, item, viewer, detail=detail)
    elif item.customer_id:
        payload['customer'] = {'id': item.customer_id, 'missing': True}
    if detail and item.visibility == AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS:
        payload['audience_member_ids'] = list(
            item.audience_members.values_list('member_id', flat=True)
        )

    owns_source = _viewer_owns_space_source(viewer, item)
    payload['owns_source_in_crm'] = owns_source
    payload['source_crm_url'] = ''
    if owns_source:
        if item.property_id:
            payload['source_crm_url'] = space_copy_target_url('property', item.property_id)
        elif item.customer_id:
            payload['source_crm_url'] = space_copy_target_url('customer', item.customer_id)

    payload['can_copy'] = can_copy_from_agency_space(viewer, item) and not owns_source
    already = bool(getattr(item, 'viewer_has_live_copy', False))
    if not already and detail:
        rec = AgencySpaceCopy.objects.filter(item=item, copied_by=viewer).first()
        already = bool(rec and (rec.copied_property_id or rec.copied_customer_id))
    payload['already_copied'] = already
    payload['copy_target_id'] = None
    payload['copy_target_url'] = ''
    payload['copy_created_at'] = ''
    payload['copy_created_at_display'] = ''
    copy_dt = getattr(item, 'viewer_copy_created_at', None)
    if copy_dt:
        payload['copy_created_at'] = (
            copy_dt.isoformat() if hasattr(copy_dt, 'isoformat') else str(copy_dt)
        )
        payload['copy_created_at_display'] = _format_published_at(copy_dt)
    if already:
        tid = getattr(item, 'viewer_copy_property_id', None) or getattr(
            item, 'viewer_copy_customer_id', None,
        )
        if not tid and detail:
            rec = AgencySpaceCopy.objects.filter(item=item, copied_by=viewer).first()
            if rec:
                tid = rec.copied_property_id or rec.copied_customer_id
                if rec.created_at:
                    payload['copy_created_at'] = rec.created_at.isoformat()
                    payload['copy_created_at_display'] = _format_published_at(rec.created_at)
        if tid:
            payload['copy_target_id'] = tid
            payload['copy_target_url'] = space_copy_target_url(item.content_kind(), tid)
    if item.publisher_id == viewer.id:
        payload['copy_count'] = int(getattr(item, 'space_copy_count', 0) or 0)
    else:
        payload['copy_count'] = None

    return payload


def serialize_space_item_safe_metadata(item: AgencySpaceItem, viewer: User) -> Optional[Dict[str, Any]]:
    from workspace.services.agency_space_access import can_view_space_item_safe_metadata

    if not can_view_space_item_safe_metadata(viewer, item):
        return None
    return {
        'id': item.pk,
        'source_kind': item.content_kind(),
        'visibility': item.visibility,
        'visibility_label': visibility_label(item.visibility),
        'status': item.status,
        'status_label': dict(AgencySpaceItem.STATUS_CHOICES).get(item.status, item.status),
        'published_at': item.published_at.isoformat() if item.published_at else '',
        'publisher': _publisher_payload(item.publisher),
    }
