"""پیش‌پر کردن داده قرارداد از معامله/ملک/مخاطب."""
from __future__ import annotations

from typing import Any, Dict, List

from contracts.constants import (
    CONTRACT_TYPE_JV,
    CONTRACT_TYPE_LEASE,
    CONTRACT_TYPE_SALE,
    PARTY_ROLE_BUILDER,
    PARTY_ROLE_BUYER,
    PARTY_ROLE_LANDLORD,
    PARTY_ROLE_OWNER,
    PARTY_ROLE_SELLER,
    PARTY_ROLE_TENANT,
)
from contracts.constants import PERSON_TYPE_LEGAL, PERSON_TYPE_NATURAL
from contracts.services.party_sanitize import sanitize_party_payload
from workspace.models import CRMDeal, Customer


def _customer_to_party_data(customer: Customer, role: str) -> Dict[str, Any]:
    from contracts.services.wizard_sources import customer_wizard_party_fields

    payload = customer_wizard_party_fields(customer)
    payload['role'] = role
    return sanitize_party_payload(payload)


def prefill_parties_from_deal(deal: CRMDeal, contract_type: str) -> List[Dict[str, Any]]:
    parties: List[Dict[str, Any]] = []
    customer = deal.customer
    prop = deal.property

    if contract_type == CONTRACT_TYPE_LEASE:
        if prop and prop.owner_name:
            parties.append({
                'role': PARTY_ROLE_LANDLORD,
                'person_type': 'natural',
                'first_name': prop.owner_name.split()[0] if prop.owner_name else '',
                'last_name': ' '.join(prop.owner_name.split()[1:]) if prop.owner_name else '',
                'mobile': prop.phone or '',
            })
        if customer:
            parties.append(_customer_to_party_data(customer, PARTY_ROLE_TENANT))
        elif prop and prop.tenant_name:
            parties.append({
                'role': PARTY_ROLE_TENANT,
                'person_type': 'natural',
                'first_name': prop.tenant_name.split()[0] if prop.tenant_name else '',
                'last_name': ' '.join(prop.tenant_name.split()[1:]) if prop.tenant_name else '',
                'mobile': prop.tenant_phone or '',
            })
    elif contract_type == CONTRACT_TYPE_SALE:
        if prop and prop.owner_name:
            parties.append({
                'role': PARTY_ROLE_SELLER,
                'person_type': 'natural',
                'first_name': prop.owner_name.split()[0] if prop.owner_name else '',
                'last_name': ' '.join(prop.owner_name.split()[1:]) if prop.owner_name else '',
                'mobile': prop.phone or '',
            })
        if customer:
            parties.append(_customer_to_party_data(customer, PARTY_ROLE_BUYER))
    elif contract_type == CONTRACT_TYPE_JV:
        if prop and prop.owner_name:
            parties.append({
                'role': PARTY_ROLE_OWNER,
                'person_type': 'natural',
                'first_name': prop.owner_name.split()[0] if prop.owner_name else '',
                'last_name': ' '.join(prop.owner_name.split()[1:]) if prop.owner_name else '',
                'mobile': prop.phone or '',
            })
        if customer:
            parties.append(_customer_to_party_data(customer, PARTY_ROLE_OWNER))

    return ensure_default_parties(parties, contract_type)


def prefill_property_from_deal(deal: CRMDeal) -> Dict[str, Any]:
    prop = deal.property
    if not prop:
        return {}
    return {
        'property_type': prop.property_type or '',
        'usage': prop.business_type or '',
        'address': prop.address or '',
        'postal_code': '',
        'province': '',
        'city': prop.city or '',
        'district': prop.district or '',
        'neighborhood': prop.neighborhood or '',
        'area': prop.area,
        'floor': prop.floor,
        'unit': '',
        'total_floors': prop.total_floors,
        'has_parking': prop.has_parking,
        'has_storage': prop.has_storage,
        'has_elevator': prop.has_elevator,
        'is_vacant': prop.is_vacant,
        'build_year': prop.build_year,
        'deed_type': '',
        'deed_number': '',
        'main_plaque': '',
        'sub_plaque': '',
        'registration_section': '',
        'ownership_status': '',
        'owner_count': 1,
        'mortgage_status': '',
        'seizure_status': '',
        'tenant_status': 'خالی' if prop.is_vacant else 'دارای مستأجر',
        'declared_by_parties': True,
    }


def _empty_financial(contract_type: str) -> Dict[str, Any]:
    if contract_type == CONTRACT_TYPE_LEASE:
        return {
            'deposit': None,
            'monthly_rent': None,
            'rent_payment_day': 1,
            'payment_method': 'transfer',
        }
    if contract_type == CONTRACT_TYPE_SALE:
        return {
            'total_price': None,
            'down_payment': None,
            'earnest_money': None,
            'payments': [],
        }
    return {}


def _empty_party(role: str) -> Dict[str, Any]:
    return sanitize_party_payload({
        'role': role,
        'person_type': PERSON_TYPE_NATURAL,
        'first_name': '',
        'last_name': '',
        'father_name': '',
        'national_id': '',
        'mobile': '',
        'address': '',
        'postal_code': '',
        'ownership_share': '',
    })


def default_parties_for_type(contract_type: str) -> List[Dict[str, Any]]:
    """دو طرف خالی پیش‌فرض متناسب با نوع قرارداد."""
    if contract_type == CONTRACT_TYPE_LEASE:
        return [_empty_party(PARTY_ROLE_LANDLORD), _empty_party(PARTY_ROLE_TENANT)]
    if contract_type == CONTRACT_TYPE_SALE:
        return [_empty_party(PARTY_ROLE_SELLER), _empty_party(PARTY_ROLE_BUYER)]
    if contract_type == CONTRACT_TYPE_JV:
        return [_empty_party(PARTY_ROLE_OWNER), _empty_party(PARTY_ROLE_BUILDER)]
    return []


def ensure_default_parties(parties: List[Dict[str, Any]], contract_type: str) -> List[Dict[str, Any]]:
    """نقش‌های الزامی را در صورت نبود، به‌صورت فرم خالی اضافه می‌کند."""
    required = {
        CONTRACT_TYPE_LEASE: (PARTY_ROLE_LANDLORD, PARTY_ROLE_TENANT),
        CONTRACT_TYPE_SALE: (PARTY_ROLE_SELLER, PARTY_ROLE_BUYER),
        CONTRACT_TYPE_JV: (PARTY_ROLE_OWNER, PARTY_ROLE_BUILDER),
    }.get(contract_type, ())
    result = list(parties or [])
    existing = {p.get('role') for p in result}
    for role in required:
        if role not in existing:
            result.append(_empty_party(role))
    return result


def empty_wizard_data(contract_type: str) -> Dict[str, Any]:
    """داده خالی ویزارد برای قرارداد بدون معامله."""
    return {
        'parties': default_parties_for_type(contract_type),
        'property': {},
        'financial': _empty_financial(contract_type),
        'jv': {} if contract_type == CONTRACT_TYPE_JV else None,
        'witnesses': [],
        'selected_clauses': [],
        'clause_optional': [],
        'custom_agreements': [],
    }


def prefill_financial_from_deal(deal: CRMDeal, contract_type: str) -> Dict[str, Any]:
    prop = deal.property
    if contract_type == CONTRACT_TYPE_LEASE:
        return {
            'deposit': prop.deposit if prop else None,
            'monthly_rent': prop.monthly_rent if prop else None,
            'rent_payment_day': 1,
            'payment_method': 'transfer',
        }
    if contract_type == CONTRACT_TYPE_SALE:
        total = deal.value or (prop.sale_price if prop else None)
        return {
            'total_price': total,
            'down_payment': None,
            'earnest_money': None,
            'payments': [],
        }
    return {}
