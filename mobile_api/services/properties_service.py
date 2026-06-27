"""سرویس املاک CRM برای API موبایل."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.core.paginator import Paginator
from django.utils import timezone

from mobile_api.serializers import property_to_dict
from workspace.constants import CRM_PROPERTIES, PROPERTY_DEAL_MODES, PROPERTY_TX_STATUSES
from workspace.models import CRMProperty, Customer, PropertyContact
from workspace.services.crm import filter_properties, update_property_transaction_status
from workspace.services.crm_scope import get_agency, properties_qs, property_for_user


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


def get_property_detail(user, property_id: int) -> Optional[dict]:
    prop = properties_qs(user).filter(pk=property_id).first()
    if not prop:
        return None
    return property_to_dict(prop, detailed=True)


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

    prop.save()
    return prop


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
