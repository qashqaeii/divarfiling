"""سرویس املاک CRM برای API موبایل."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.core.paginator import Paginator
from django.utils import timezone

from mobile_api.serializers import property_detail_to_dict, property_to_dict
from workspace.constants import CRM_PROPERTIES, PROPERTY_DEAL_MODES, PROPERTY_TX_STATUSES
from workspace.models import CRMProperty, Customer, CustomerActivity, CustomerDocument, PropertyContact
from workspace.services.crm import filter_properties, link_customer_property, resolve_listing_for_property, update_property_transaction_status
from workspace.services.crm_property_share import build_property_share_context
from workspace.services.crm_scope import can_edit_property, customers_qs, get_agency, properties_qs, property_for_user
from workspace.services.features import extract_listing_features
from workspace.services.listing_features import build_listing_feature_profile


def list_properties_paginated(
    user,
    *,
    page: int = 1,
    page_size: int = 20,
    query: Optional[Dict[str, Any]] = None,
) -> Tuple[List[dict], dict]:
    params = {k: str(v) for k, v in (query or {}).items() if v is not None and str(v).strip()}
    qs = filter_properties(user, params)
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    items = [property_to_dict(p) for p in page_obj.object_list]
    meta = {'page': page, 'page_size': page_size, 'total': paginator.count}
    return items, meta


def get_property_detail(user, property_id: int, *, request=None) -> Optional[dict]:
    prop = properties_qs(user).filter(pk=property_id).first()
    if not prop:
        return None

    share_ctx = build_property_share_context(user, prop)
    contacts = list(
        prop.contact_links.select_related('customer').all()
    ) if not share_ctx.mask_sensitive else []
    activities = list(
        CustomerActivity.objects.filter(property=prop)
        .select_related('customer')
        .order_by('-created_at')[:30]
    ) if not share_ctx.mask_sensitive else []
    documents = list(
        CustomerDocument.objects.filter(user=user, property=prop).order_by('-uploaded_at')
    ) if not share_ctx.mask_sensitive else []

    feature_profile = {'has_details': False, 'core': [], 'groups': []}
    listing_highlights: List[str] = []
    source_listing = resolve_listing_for_property(user, prop)
    if source_listing:
        feat = extract_listing_features(source_listing)
        feature_profile = build_listing_feature_profile(source_listing, feat)
        listing_highlights = feat.get('highlights') or []

    return property_detail_to_dict(
        prop,
        contacts=contacts,
        activities=activities,
        documents=documents,
        feature_profile=feature_profile,
        listing_highlights=listing_highlights,
        can_edit=can_edit_property(user, prop),
        mask_sensitive=share_ctx.mask_sensitive,
        request=request,
    )


def _parse_int(value) -> Optional[int]:
    if value in (None, ''):
        return None
    return int(value)


def _parse_float(value) -> Optional[float]:
    if value in (None, ''):
        return None
    return float(value)


def create_property_from_mobile(user, data: Dict[str, Any]) -> CRMProperty:
    title = (data.get('title') or '').strip()
    if not title:
        raise ValueError('عنوان ملک الزامی است.')

    deal_mode = (data.get('deal_mode') or 'فروش').strip()
    if deal_mode not in PROPERTY_DEAL_MODES:
        deal_mode = 'فروش'

    property_type = (data.get('property_type') or 'آپارتمان').strip()
    if property_type not in CRM_PROPERTIES:
        property_type = 'آپارتمان'

    tx_status = (data.get('transaction_status') or 'فعال').strip()
    if tx_status not in PROPERTY_TX_STATUSES:
        tx_status = 'فعال'

    prop = CRMProperty(
        user=user,
        agency=get_agency(user),
        title=title,
        property_type=property_type,
        deal_mode=deal_mode,
        transaction_status=tx_status,
        city=(data.get('city') or '')[:100],
        district=(data.get('district') or '')[:100],
        neighborhood=(data.get('neighborhood') or '')[:200],
        address=(data.get('address') or ''),
        area=_parse_float(data.get('area')),
        rooms=(data.get('rooms') or '')[:20],
        sale_price=_parse_int(data.get('sale_price')),
        deposit=_parse_int(data.get('deposit')),
        monthly_rent=_parse_int(data.get('rent') if 'rent' in data else data.get('monthly_rent')),
        token=(data.get('token') or '')[:100],
        link=(data.get('link') or '')[:500],
        notes=(data.get('notes') or ''),
    )
    prop.save()

    contact_id = data.get('contact_id') or data.get('customer_id')
    if contact_id:
        from workspace.services.crm_scope import customers_qs
        customer = customers_qs(user).filter(pk=int(contact_id)).first()
        if customer:
            PropertyContact.objects.get_or_create(
                customer=customer,
                property=prop,
                role=(data.get('role') or 'مالک'),
                defaults={'deal_type': 'فروش'},
            )
    return prop


def update_property_from_mobile(user, property_id: int, data: Dict[str, Any]) -> Optional[CRMProperty]:
    prop = property_for_user(user, property_id)
    if not prop:
        return None

    simple_fields = {
        'title': 'title',
        'deal_mode': 'deal_mode',
        'transaction_status': 'transaction_status',
        'property_type': 'property_type',
        'city': 'city',
        'district': 'district',
        'neighborhood': 'neighborhood',
        'address': 'address',
        'rooms': 'rooms',
        'token': 'token',
        'link': 'link',
        'notes': 'notes',
        'amenities': 'amenities',
    }
    for api_key, model_field in simple_fields.items():
        if api_key in data:
            setattr(prop, model_field, data.get(api_key) or '')

    if 'area' in data:
        prop.area = _parse_float(data.get('area'))
    if 'sale_price' in data:
        prop.sale_price = _parse_int(data.get('sale_price'))
    if 'deposit' in data:
        prop.deposit = _parse_int(data.get('deposit'))
    if 'rent' in data or 'monthly_rent' in data:
        prop.monthly_rent = _parse_int(data.get('rent', data.get('monthly_rent')))
    if 'floor' in data:
        prop.floor = _parse_int(data.get('floor'))
    if 'build_year' in data:
        prop.build_year = _parse_int(data.get('build_year'))
    for bool_field in ('has_parking', 'has_storage', 'has_elevator'):
        if bool_field in data:
            setattr(prop, bool_field, bool(data.get(bool_field)))
    if 'publish_status' in data:
        prop.publish_status = (data.get('publish_status') or prop.publish_status)[:30]

    prop.save()
    return prop


def link_property_contact(user, property_id: int, data: Dict[str, Any]) -> PropertyContact:
    prop = property_for_user(user, property_id)
    if not prop:
        raise ValueError('ملک یافت نشد.')
    if not can_edit_property(user, prop):
        raise ValueError('امکان ویرایش این ملک را ندارید.')

    customer_id = data.get('customer_id') or data.get('contact_id')
    if not customer_id:
        raise ValueError('مخاطب الزامی است.')
    customer = customers_qs(user).filter(pk=int(customer_id)).first()
    if not customer:
        raise ValueError('مخاطب یافت نشد.')

    return link_customer_property(
        customer,
        prop,
        (data.get('role') or 'پیشنهادی').strip(),
        (data.get('deal_type') or 'سایر').strip(),
        interest_level=(data.get('interest_level') or '').strip(),
        is_primary=bool(data.get('is_primary', False)),
        notes=(data.get('notes') or '').strip(),
    )


def change_property_status(user, property_id: int, status: str) -> Optional[CRMProperty]:
    prop = property_for_user(user, property_id)
    if not prop:
        return None
    update_property_transaction_status(prop, status, user=user)
    return prop


def soft_delete_property(user, property_id: int) -> bool:
    prop = property_for_user(user, property_id)
    if not prop:
        return False
    prop.deleted_at = timezone.now()
    prop.save(update_fields=['deleted_at', 'updated_at'])
    return True
