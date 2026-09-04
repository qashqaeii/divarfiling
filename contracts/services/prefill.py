"""پیش‌پر کردن داده قرارداد از معامله/ملک/مخاطب."""
from __future__ import annotations

from typing import Any, Dict, List

from contracts.constants import (
    CONTRACT_TYPE_JV,
    CONTRACT_TYPE_LEASE,
    CONTRACT_TYPE_SALE,
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
    person_type = PERSON_TYPE_LEGAL if customer.is_legal_entity else PERSON_TYPE_NATURAL
    payload = {
        'role': role,
        'customer_id': customer.pk,
        'person_type': person_type,
        'first_name': customer.name.split()[0] if customer.name else '',
        'last_name': ' '.join(customer.name.split()[1:]) if customer.name else '',
        'national_id': '' if person_type == PERSON_TYPE_LEGAL else (customer.national_id or ''),
        'company_national_id': (customer.national_id or '') if person_type == PERSON_TYPE_LEGAL else '',
        'mobile': customer.phone or '',
        'address': '',
        'company_name': customer.company_name or '',
    }
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

    return parties


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
