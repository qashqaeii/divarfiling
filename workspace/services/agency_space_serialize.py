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
from workspace.constants import AGENCY_ROLE_STYLES
from accounts.avatar_catalog import consultant_portrait_url, resolve_contact_avatar_display

User = get_user_model()


def _viewer_owns_space_source(viewer: User, item: AgencySpaceItem) -> bool:
    """انتشار از همان فایل/مخاطب CRM خود کاربر — کپی جدا لازم نیست."""
    if item.property_id and item.property:
        return item.property.user_id == viewer.id
    if item.customer_id and item.customer:
        return item.customer.user_id == viewer.id
    return False


def _property_price_rows(prop: CRMProperty) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if prop.sale_price:
        rows.append({'label': 'قیمت فروش', 'value': format_toman(prop.sale_price)})
    if prop.deposit:
        rows.append({'label': 'رهن', 'value': format_toman(prop.deposit)})
    if prop.monthly_rent:
        rows.append({'label': 'اجاره ماهانه', 'value': format_toman(prop.monthly_rent)})
    return rows


def _property_amenity_flags(prop: CRMProperty) -> List[Dict[str, str]]:
    mapping = [
        ('has_parking', 'پارکینگ', 'fa-car'),
        ('has_storage', 'انباری', 'fa-box'),
        ('has_elevator', 'آسانسور', 'fa-arrow-up'),
        ('has_wardrobe', 'کمد دیواری', 'fa-door-closed'),
        ('has_two_corner', 'دو نبش', 'fa-vector-square'),
        ('has_two_access', 'دو معبر', 'fa-road'),
        ('has_wallpaper', 'کاغذ دیواری', 'fa-paint-roller'),
        ('has_knauf', 'کناف', 'fa-border-all'),
        ('has_lighting', 'نورپردازی', 'fa-lightbulb'),
        ('is_vacant', 'تخلیه', 'fa-key'),
    ]
    out: List[Dict[str, str]] = []
    for attr, label, icon in mapping:
        if getattr(prop, attr, False):
            out.append({'label': label, 'icon': icon})
    return out


def _property_feature_data_rows(prop: CRMProperty) -> List[Dict[str, str]]:
    raw = prop.feature_data if isinstance(prop.feature_data, dict) else {}
    rows: List[Dict[str, str]] = []
    for key, val in raw.items():
        if val is None or val == '' or val is False:
            continue
        if isinstance(val, bool):
            if not val:
                continue
            display = 'بله'
        else:
            display = str(val)
        rows.append({'label': str(key), 'value': display})
    return rows[:40]


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


def _customer_budget_rows(customer: Customer) -> List[Dict[str, str]]:
    """ردیف‌های بودجه برای UI جزئیات — بدون داده حساس."""
    rows: List[Dict[str, str]] = []
    purchase = _customer_budget_label(customer)
    if purchase:
        rows.append({'label': 'بودجه خرید', 'value': purchase})
    if customer.deposit_min or customer.deposit_max:
        if customer.deposit_min and customer.deposit_max:
            val = f'{format_toman(customer.deposit_min)} تا {format_toman(customer.deposit_max)}'
        elif customer.deposit_max:
            val = f'تا {format_toman(customer.deposit_max)}'
        else:
            val = f'از {format_toman(customer.deposit_min)}'
        rows.append({'label': 'رهن', 'value': val})
    if customer.rent_min or customer.rent_max:
        if customer.rent_min and customer.rent_max:
            val = f'{format_toman(customer.rent_min)} تا {format_toman(customer.rent_max)}'
        elif customer.rent_max:
            val = f'تا {format_toman(customer.rent_max)}'
        else:
            val = f'از {format_toman(customer.rent_min)}'
        rows.append({'label': 'اجاره', 'value': val})
    return rows


def _customer_rent_deposit_label(customer: Customer) -> str:
    parts: List[str] = []
    if customer.deposit_min or customer.deposit_max:
        if customer.deposit_min and customer.deposit_max:
            parts.append(
                f'رهن {format_toman(customer.deposit_min)} تا {format_toman(customer.deposit_max)}',
            )
        elif customer.deposit_max:
            parts.append(f'رهن تا {format_toman(customer.deposit_max)}')
        else:
            parts.append(f'رهن از {format_toman(customer.deposit_min)}')
    if customer.rent_min or customer.rent_max:
        if customer.rent_min and customer.rent_max:
            parts.append(
                f'اجاره {format_toman(customer.rent_min)} تا {format_toman(customer.rent_max)}',
            )
        elif customer.rent_max:
            parts.append(f'اجاره تا {format_toman(customer.rent_max)}')
        else:
            parts.append(f'اجاره از {format_toman(customer.rent_min)}')
    return ' · '.join(parts)


def _customer_area_label(customer: Customer) -> str:
    if customer.min_area and customer.max_area:
        return f'{format_area(customer.min_area)} تا {format_area(customer.max_area)}'
    if customer.max_area:
        return f'تا {format_area(customer.max_area)}'
    if customer.min_area:
        return f'از {format_area(customer.min_area)}'
    return ''


def _customer_rooms_label(customer: Customer) -> str:
    if customer.rooms:
        return customer.rooms if 'خواب' in customer.rooms else f'{customer.rooms} خواب'
    if customer.rooms_min is not None and customer.rooms_max is not None:
        return f'{customer.rooms_min} تا {customer.rooms_max} خواب'
    if customer.rooms_max is not None:
        return f'تا {customer.rooms_max} خواب'
    if customer.rooms_min is not None:
        return f'از {customer.rooms_min} خواب'
    return ''


def _customer_amenity_tags(customer: Customer) -> List[str]:
    tags: List[str] = []
    if customer.want_parking:
        tags.append('پارکینگ')
    if customer.want_storage:
        tags.append('انباری')
    if customer.want_elevator:
        tags.append('آسانسور')
    return tags


def _format_published_at(dt) -> str:
    if not dt:
        return ''
    return to_jalali_display(dt)


def _publisher_payload(user: User, request=None) -> Dict[str, Any]:
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
    role_bg, role_fg = AGENCY_ROLE_STYLES.get(role, ('#f1f5f9', '#64748b'))
    ws = getattr(user, '_space_ws_settings', None)
    if ws is None and request is not None:
        from workspace.models import WorkspaceSettings

        ws = WorkspaceSettings.objects.filter(user_id=user.pk).only('consultant_photo').first()
        user._space_ws_settings = ws
    return {
        'id': user.pk,
        'name': user_display_name(user),
        'role': role,
        'role_label': role_label,
        'role_bg': role_bg,
        'role_fg': role_fg,
        'avatar_url': consultant_portrait_url(user, ws_settings=ws, request=request),
    }


def _property_card(prop: CRMProperty, *, include_sensitive: bool) -> Dict[str, Any]:
    images: List[str] = []
    if prop.images and isinstance(prop.images, list):
        images = [u for u in prop.images if isinstance(u, str) and u.strip()][:12]
    thumb = images[0] if images else ''
    area = prop.area
    area_label = format_area(area) if area not in (None, '') else ''
    region = ' · '.join(p for p in (prop.neighborhood, prop.district, prop.city) if p)
    price_per_meter_label = ''
    if prop.sale_price and area:
        try:
            area_f = float(area)
            if area_f > 0:
                price_per_meter_label = format_toman(int(prop.sale_price / area_f))
        except (TypeError, ValueError):
            price_per_meter_label = ''
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
        'price_per_meter_label': price_per_meter_label,
    }
    if include_sensitive:
        data['address'] = prop.address
        data['phone'] = prop.phone
        data['tenant_phone'] = prop.tenant_phone or ''
        data['owner_name'] = prop.owner_name or ''
        data['notes'] = prop.notes or ''
        data['amenities'] = (prop.amenities or '')[:1200]
        data['land_area'] = prop.land_area
        data['land_area_label'] = format_area(prop.land_area) if prop.land_area not in (None, '') else ''
        data['frontage_width'] = prop.frontage_width
        data['postal_code'] = prop.postal_code or ''
        data['publish_status'] = prop.publish_status or ''
        data['business_type'] = prop.business_type or ''
        data['link'] = prop.link or ''
        data['token'] = prop.token or ''
        data['source_platform'] = prop.source_platform or ''
        data['latitude'] = prop.latitude
        data['longitude'] = prop.longitude
        data['has_map'] = prop.latitude is not None and prop.longitude is not None
        data['price_rows'] = _property_price_rows(prop)
        data['amenity_flags'] = _property_amenity_flags(prop)
        data['feature_data_rows'] = _property_feature_data_rows(prop)
        data['has_parking'] = prop.has_parking
        data['has_elevator'] = prop.has_elevator
        data['has_storage'] = prop.has_storage
        data['is_vacant'] = prop.is_vacant
        data['has_wardrobe'] = prop.has_wardrobe
        data['has_two_corner'] = prop.has_two_corner
        data['has_two_access'] = prop.has_two_access
        data['has_wallpaper'] = prop.has_wallpaper
        data['has_knauf'] = prop.has_knauf
        data['has_lighting'] = prop.has_lighting
    return data


def _customer_payload(
    customer: Customer,
    item: AgencySpaceItem,
    viewer: User,
    *,
    detail: bool,
    request=None,
) -> Dict[str, Any]:
    can_full = (
        item.contact_share_level == AgencySpaceItem.CONTACT_FULL
        and can_view_space_item_content(viewer, item)
    )
    region = ' · '.join(p for p in (customer.district, customer.city, customer.areas) if p)
    need_summary = ''
    if can_full:
        need_summary = (customer.notes or '')[:300] if detail else (customer.notes or '')[:120]
    budget_label = _customer_budget_label(customer)
    rent_deposit_label = _customer_rent_deposit_label(customer)
    finance_label = budget_label or rent_deposit_label
    data = {
        'id': customer.pk,
        'name': customer.name,
        'customer_type': customer.customer_type,
        'need_summary': need_summary,
        'budget_label': budget_label,
        'rent_deposit_label': rent_deposit_label,
        'finance_label': finance_label,
        'region': region,
        'status': customer.status,
        'priority': customer.priority or '',
        'property_type': customer.property_type or '',
        'source': customer.source or '',
        'area_label': _customer_area_label(customer),
        'rooms_label': _customer_rooms_label(customer),
        'areas_display': (customer.areas or '').strip(),
        'amenity_tags': _customer_amenity_tags(customer),
        'has_phone': bool(can_full and customer.phone),
        'budget_rows': _customer_budget_rows(customer),
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
    avatar = resolve_contact_avatar_display(customer, request=request)
    data['avatar_url'] = avatar.get('photo_url') or ''
    if detail and can_full:
        data['notes'] = (customer.notes or '')[:800]
    return data


def visibility_label(visibility: str) -> str:
    return dict(AgencySpaceItem.VISIBILITY_CHOICES).get(visibility, visibility)


def serialize_space_item(
    item: AgencySpaceItem,
    viewer: User,
    *,
    detail: bool = False,
    request=None,
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
        'publisher': _publisher_payload(item.publisher, request=request),
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
        payload['customer'] = _customer_payload(
            item.customer, item, viewer, detail=detail, request=request,
        )
    elif item.customer_id:
        payload['customer'] = {'id': item.customer_id, 'missing': True}
    if detail and item.visibility == AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS:
        payload['audience_member_ids'] = list(
            item.audience_members.values_list('member_id', flat=True)
        )
    if item.visibility == AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS:
        if payload['is_publisher'] or payload.get('can_moderate'):
            payload['audience_count'] = item.audience_members.count()
        else:
            payload['audience_count'] = None

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


def serialize_space_item_safe_metadata(
    item: AgencySpaceItem, viewer: User, *, request=None,
) -> Optional[Dict[str, Any]]:
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
        'publisher': _publisher_payload(item.publisher, request=request),
    }
