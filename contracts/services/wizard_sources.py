"""جستجو و نگاشت مخاطب / فایل شخصی برای ویزارد قرارداد."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db.models import Q

from contracts.services.party_sanitize import sanitize_party_payload
from contracts.constants import PERSON_TYPE_LEGAL, PERSON_TYPE_NATURAL
from workspace.models import CRMProperty, Customer
from workspace.services.crm_scope import customer_for_user, customers_qs, properties_qs, property_for_user


def _mask_phone(phone: str) -> str:
    phone = (phone or '').strip()
    if len(phone) < 6:
        return phone
    return phone[:4] + '••••' + phone[-3:]


def _display_customer_name(customer: Customer) -> str:
    if customer.is_legal_entity and customer.company_name:
        if customer.name:
            return f'{customer.company_name} — {customer.name}'
        return customer.company_name
    return customer.name or ''


def customer_wizard_party_fields(customer: Customer) -> Dict[str, Any]:
    """فیلدهای طرف قرارداد از مخاطب — بدون نقش."""
    person_type = PERSON_TYPE_LEGAL if customer.is_legal_entity else PERSON_TYPE_NATURAL
    name = (customer.name or '').strip()
    parts = name.split() if name else []
    first_name = parts[0] if parts else ''
    last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
    if person_type == PERSON_TYPE_LEGAL and customer.company_name:
        if not first_name and not last_name:
            first_name = customer.company_name
    mobile = (customer.phone or customer.phone_alt or '').strip()
    payload = {
        'customer_id': customer.pk,
        'person_type': person_type,
        'first_name': first_name,
        'last_name': last_name,
        'father_name': '',
        'national_id': '' if person_type == PERSON_TYPE_LEGAL else (customer.national_id or ''),
        'company_national_id': (customer.national_id or '') if person_type == PERSON_TYPE_LEGAL else '',
        'mobile': mobile,
        'address': '',
        'postal_code': '',
        'company_name': customer.company_name or '',
        'representative_name': '',
        'representative_national_id': '',
        'representative_mobile': '',
        'ownership_share': '',
    }
    return sanitize_party_payload(payload)


def serialize_wizard_customer_summary(customer: Customer) -> Dict[str, Any]:
    phone = (customer.phone or customer.phone_alt or '').strip()
    meta_parts = []
    if customer.customer_type:
        meta_parts.append(customer.customer_type)
    if customer.is_legal_entity and customer.company_name:
        meta_parts.append(customer.company_name)
    return {
        'id': customer.pk,
        'name': _display_customer_name(customer),
        'phone': phone,
        'phone_masked': _mask_phone(phone),
        'meta': ' · '.join(meta_parts),
        'is_legal': bool(customer.is_legal_entity),
    }


def search_wizard_customers(user, query: str = '', limit: int = 20) -> List[Dict[str, Any]]:
    q = (query or '').strip()
    qs = customers_qs(user).order_by('-updated_at')
    if q:
        if len(q) < 2:
            return []
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(phone__icontains=q)
            | Q(phone_alt__icontains=q)
            | Q(company_name__icontains=q)
            | Q(national_id__icontains=q),
        )
    else:
        qs = qs[:limit]
        return [serialize_wizard_customer_summary(c) for c in qs]
    return [serialize_wizard_customer_summary(c) for c in qs[:limit]]


def wizard_customer_party_payload(user, customer_id: int) -> Optional[Dict[str, Any]]:
    customer = customer_for_user(user, customer_id)
    if not customer:
        return None
    return customer_wizard_party_fields(customer)


def _rooms_to_bedrooms(rooms: str) -> str:
    rooms = (rooms or '').strip()
    if not rooms:
        return ''
    if rooms.isdigit():
        return rooms
    return rooms


def _feature(fd: dict, *keys: str) -> str:
    for key in keys:
        val = fd.get(key)
        if val not in (None, '', 'ندارد'):
            return str(val).strip()
    return ''


def crm_property_wizard_payload(prop: CRMProperty) -> Dict[str, Any]:
    """نگاشت فایل شخصی به داده مرحله ملک ویزارد."""
    fd = prop.feature_data if isinstance(prop.feature_data, dict) else {}
    data = {
        'crm_property_id': prop.pk,
        'property_type': prop.property_type or '',
        'usage': prop.business_type or _feature(fd, 'نوع کاربری ملک', 'نوع کاربری'),
        'address': prop.address or '',
        'postal_code': _feature(fd, 'کد پستی'),
        'province': '',
        'city': prop.city or '',
        'district': prop.district or '',
        'neighborhood': prop.neighborhood or '',
        'area': prop.area,
        'floor': prop.floor,
        'unit': _feature(fd, 'واحد', 'شماره واحد'),
        'total_floors': prop.total_floors,
        'units_per_floor': _feature(fd, 'تعداد واحد در طبقه'),
        'bedrooms': _rooms_to_bedrooms(prop.rooms),
        'build_year': prop.build_year,
        'has_parking': bool(prop.has_parking),
        'has_storage': bool(prop.has_storage),
        'has_elevator': bool(prop.has_elevator),
        'is_vacant': bool(prop.is_vacant),
        'unit_direction': _feature(fd, 'جهت واحد', 'جهت'),
        'building_direction': _feature(fd, 'جهت ساختمان'),
        'facade_type': _feature(fd, 'نوع نما', 'نما'),
        'floor_type': _feature(fd, 'جنس کف'),
        'kitchen_type': _feature(fd, 'نوع آشپزخانه', 'آشپزخانه'),
        'heating_system': _feature(fd, 'گرمایش', 'سیستم گرمایش'),
        'cooling_system': _feature(fd, 'سرمایش', 'سیستم سرمایش'),
        'deed_type': _feature(fd, 'نوع سند', 'وضعیت سند'),
        'deed_number': _feature(fd, 'شماره سند'),
        'main_plaque': _feature(fd, 'پلاک اصلی', 'پلاک'),
        'sub_plaque': _feature(fd, 'پلاک فرعی'),
        'tenant_status': 'خالی' if prop.is_vacant else ('دارای مستأجر' if prop.tenant_name else ''),
        'declared_by_parties': True,
        'crm_property_title': prop.title or '',
    }
    # نرمال‌سازی مقادیر عددی برای فرم
    for key in ('area', 'floor', 'total_floors', 'build_year'):
        val = data.get(key)
        if val is not None and val != '':
            data[key] = val
    return data


def serialize_wizard_property_summary(prop: CRMProperty) -> Dict[str, Any]:
    chips = []
    if prop.area:
        chips.append(f'{prop.area:g} م²' if isinstance(prop.area, float) else f'{prop.area} م²')
    if prop.rooms:
        chips.append(prop.rooms)
    loc = ' · '.join(filter(None, [prop.neighborhood, prop.district, prop.city]))
    price = ''
    if prop.sale_price:
        price = f'فروش {prop.sale_price:,}'
    elif prop.monthly_rent:
        price = f'اجاره {prop.monthly_rent:,}'
    elif prop.deposit:
        price = f'رهن {prop.deposit:,}'
    return {
        'id': prop.pk,
        'title': prop.title or f'ملک #{prop.pk}',
        'property_type': prop.property_type or '',
        'location': loc,
        'chips': chips,
        'price_hint': price,
        'deal_mode': prop.deal_mode or '',
    }


def search_wizard_properties(user, query: str = '', limit: int = 20) -> List[Dict[str, Any]]:
    q = (query or '').strip()
    qs = properties_qs(user).filter(deleted_at__isnull=True).order_by('-updated_at')
    if q:
        if len(q) < 2:
            return []
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(address__icontains=q)
            | Q(neighborhood__icontains=q)
            | Q(district__icontains=q)
            | Q(city__icontains=q)
            | Q(property_type__icontains=q)
            | Q(owner_name__icontains=q),
        )
    else:
        qs = qs[:limit]
        return [serialize_wizard_property_summary(p) for p in qs]
    return [serialize_wizard_property_summary(p) for p in qs[:limit]]


def wizard_property_payload(user, property_id: int) -> Optional[Dict[str, Any]]:
    prop = property_for_user(user, property_id)
    if not prop or prop.deleted_at:
        return None
    return crm_property_wizard_payload(prop)
