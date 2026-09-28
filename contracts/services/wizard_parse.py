"""پارس داده ویزارد از فرم HTML — بدون JSON خام برای کاربر."""
from __future__ import annotations

from typing import Any, Dict, List

from django.http import QueryDict

from contracts.constants import COMMON_AREAS, COST_RESPONSIBILITY_OPTIONS
from contracts.services.money import parse_toman_amount
from contracts.services.party_sanitize import sanitize_party_payload, sanitize_witness_payload


def _get(post: QueryDict, key: str, default: str = '') -> str:
    return (post.get(key) or default).strip()


def _int_or_raw(val: str):
    if val.isdigit():
        return int(val)
    return val


def parse_parties(post: QueryDict) -> List[Dict[str, Any]]:
    parties = []
    indices = set()
    for key in post:
        if key.startswith('party_') and '_role' in key:
            idx = key.split('_')[1]
            if idx.isdigit():
                indices.add(int(idx))
    for idx in sorted(indices):
        prefix = f'party_{idx}_'
        if not _get(post, f'{prefix}role'):
            continue
        parties.append(sanitize_party_payload({
            'role': _get(post, f'{prefix}role'),
            'customer_id': _get(post, f'{prefix}customer_id'),
            'person_type': _get(post, f'{prefix}person_type', 'natural'),
            'first_name': _get(post, f'{prefix}first_name'),
            'last_name': _get(post, f'{prefix}last_name'),
            'father_name': _get(post, f'{prefix}father_name'),
            'national_id': _get(post, f'{prefix}national_id'),
            'mobile': _get(post, f'{prefix}mobile'),
            'address': _get(post, f'{prefix}address'),
            'postal_code': _get(post, f'{prefix}postal_code'),
            'ownership_share': _get(post, f'{prefix}ownership_share'),
            'company_name': _get(post, f'{prefix}company_name'),
            'company_national_id': _get(post, f'{prefix}company_national_id'),
            'representative_name': _get(post, f'{prefix}representative_name'),
            'representative_national_id': _get(post, f'{prefix}representative_national_id'),
            'representative_mobile': _get(post, f'{prefix}representative_mobile'),
        }))
    return parties


def _parse_utilities(post: QueryDict) -> Dict[str, Any]:
    utilities = {}
    for util in ('water', 'electricity', 'gas', 'phone', 'sewage'):
        utilities[util] = {
            'connection_type': _get(post, f'util_{util}_type'),
            'subscription_no': _get(post, f'util_{util}_sub'),
            'bill_id': _get(post, f'util_{util}_bill'),
        }
    return utilities


def _optional_int(val: str):
    val = (val or '').strip()
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        return None


def parse_property(post: QueryDict) -> Dict[str, Any]:
    common_areas = [a for a in COMMON_AREAS if post.get(f'common_{a}') == 'on']
    crm_property_id = _optional_int(_get(post, 'prop_crm_property_id'))
    data = {
        'crm_property_id': crm_property_id,
        'crm_property_title': _get(post, 'prop_crm_title'),
        'property_type': _get(post, 'prop_property_type'),
        'usage': _get(post, 'prop_usage'),
        'province': _get(post, 'prop_province'),
        'city': _get(post, 'prop_city'),
        'county': _get(post, 'prop_county'),
        'district': _get(post, 'prop_district'),
        'neighborhood': _get(post, 'prop_neighborhood'),
        'address': _get(post, 'prop_address'),
        'postal_code': _get(post, 'prop_postal_code'),
        'area': _get(post, 'prop_area'),
        'build_year': _get(post, 'prop_build_year'),
        'total_floors': _get(post, 'prop_total_floors'),
        'units_per_floor': _get(post, 'prop_units_per_floor'),
        'floor': _get(post, 'prop_floor'),
        'unit': _get(post, 'prop_unit'),
        'bedrooms': _get(post, 'prop_bedrooms'),
        'building_direction': _get(post, 'prop_building_direction'),
        'unit_direction': _get(post, 'prop_unit_direction'),
        'facade_type': _get(post, 'prop_facade_type'),
        'floor_type': _get(post, 'prop_floor_type'),
        'kitchen_type': _get(post, 'prop_kitchen_type'),
        'bathroom_type': _get(post, 'prop_bathroom_type'),
        'heating_system': _get(post, 'prop_heating'),
        'cooling_system': _get(post, 'prop_cooling'),
        'has_parking': post.get('prop_has_parking') == 'on',
        'parking_number': _get(post, 'prop_parking_number'),
        'has_storage': post.get('prop_has_storage') == 'on',
        'storage_number': _get(post, 'prop_storage_number'),
        'has_elevator': post.get('prop_has_elevator') == 'on',
        'deed_type': _get(post, 'prop_deed_type'),
        'deed_number': _get(post, 'prop_deed_number'),
        'main_plaque': _get(post, 'prop_main_plaque'),
        'sub_plaque': _get(post, 'prop_sub_plaque'),
        'registration_section': _get(post, 'prop_registration_section'),
        'utilities': _parse_utilities(post),
        'common_areas': common_areas,
        'has_mortgage': post.get('prop_has_mortgage') == 'on',
        'has_tenant': post.get('prop_has_tenant') == 'on',
        'has_loan': post.get('prop_has_loan') == 'on',
        'has_debt': post.get('prop_has_debt') == 'on',
        'has_completion_cert': post.get('prop_has_completion_cert') == 'on',
        'has_separation_minutes': post.get('prop_has_separation_minutes') == 'on',
        'declared_by_parties': True,
    }
    if not data.get('crm_property_id'):
        data.pop('crm_property_id', None)
    return data


def _parse_costs(post: QueryDict) -> Dict[str, str]:
    costs = {}
    for key in ('water', 'electricity', 'gas', 'phone', 'charge', 'minor_repairs', 'major_repairs', 'property_tax'):
        val = _get(post, f'cost_{key}')
        if val in COST_RESPONSIBILITY_OPTIONS:
            costs[key] = val
    return costs


def _parse_penalties(post: QueryDict) -> Dict[str, Any]:
    penalties = {}
    for key, prefix in (
        ('landlord_delivery_delay', 'pen_landlord_delivery'),
        ('tenant_vacate_delay', 'pen_tenant_vacate'),
        ('deposit_return_delay', 'pen_deposit_return'),
    ):
        if post.get(f'{prefix}_enabled') == 'on':
            penalties[key] = {
                'enabled': True,
                'amount_per_day': parse_toman_amount(_get(post, f'{prefix}_amount')),
            }
    return penalties


def parse_financial_lease(post: QueryDict) -> Dict[str, Any]:
    deposit = _get(post, 'fin_deposit')
    rent = _get(post, 'fin_monthly_rent')
    data = {
        'lease_start': _get(post, 'fin_lease_start'),
        'lease_end': _get(post, 'fin_lease_end'),
        'deposit': parse_toman_amount(deposit) if deposit else deposit,
        'monthly_rent': parse_toman_amount(rent) if rent else rent,
        'rent_payment_day': int(_get(post, 'fin_rent_day', '1') or 1),
        'payment_method': _get(post, 'fin_payment_method', 'transfer'),
        'payment_destination': _get(post, 'fin_payment_destination'),
        'payment_card': _get(post, 'fin_payment_card'),
        'payment_account': _get(post, 'fin_payment_account'),
        'payment_iban': _get(post, 'fin_payment_iban'),
        'delivery_date': _get(post, 'fin_delivery_date'),
        'delivery_delay_penalty': parse_toman_amount(_get(post, 'fin_delivery_penalty')),
        'vacate_date': _get(post, 'fin_vacate_date'),
        'deposit_mode': _get(post, 'fin_deposit_mode', 'new'),
        'deposit_payment_date': _get(post, 'fin_deposit_pay_date'),
        'deposit_payment_method': _get(post, 'fin_deposit_pay_method'),
        'previous_deposit_amount': parse_toman_amount(_get(post, 'fin_prev_deposit')),
        'previous_contract_ref': _get(post, 'fin_prev_contract_ref'),
        'previous_contract_date': _get(post, 'fin_prev_contract_date'),
        'usage_type': _get(post, 'fin_usage_type', 'residential'),
        'occupants_count': _get(post, 'fin_occupants'),
        'transfer_to_third_party_allowed': post.get('fin_transfer_allowed') == 'on',
        'costs': _parse_costs(post),
        'penalties': _parse_penalties(post),
    }
    return data


def parse_financial_sale(post: QueryDict) -> Dict[str, Any]:
    total = _get(post, 'fin_total_price')
    payments = []
    pay_indices = set()
    for key in post:
        if key.startswith('pay_') and key.endswith('_amount'):
            idx = key.split('_')[1]
            if idx.isdigit():
                pay_indices.add(int(idx))
    for idx in sorted(pay_indices):
        amt = _get(post, f'pay_{idx}_amount')
        payments.append({
            'label': _get(post, f'pay_{idx}_label', f'قسط {idx}'),
            'amount': parse_toman_amount(amt) if amt else amt,
            'due_date': _get(post, f'pay_{idx}_due_date'),
            'payment_method': _get(post, f'pay_{idx}_method'),
            'notes': _get(post, f'pay_{idx}_notes'),
        })
    return {
        'total_price': parse_toman_amount(total) if total else total,
        'down_payment': parse_toman_amount(_get(post, 'fin_down_payment')),
        'earnest_money': parse_toman_amount(_get(post, 'fin_earnest_money')),
        'delivery_date': _get(post, 'fin_delivery_date'),
        'transfer_date': _get(post, 'fin_transfer_date'),
        'transfer_place': _get(post, 'fin_transfer_place'),
        'notary_office_number': _get(post, 'fin_notary_number'),
        'remaining_amount_at_transfer': parse_toman_amount(_get(post, 'fin_remaining_at_transfer')),
        'official_transfer_date': _get(post, 'fin_official_transfer_date'),
        'payments': payments,
    }


def parse_jv(post: QueryDict) -> Dict[str, Any]:
    milestones = []
    for key in post:
        if key.startswith('ms_') and key.endswith('_title'):
            idx = key.split('_')[1]
            if idx.isdigit():
                milestones.append({
                    'title': _get(post, f'ms_{idx}_title'),
                    'due_date': _get(post, f'ms_{idx}_due_date'),
                    'notes': _get(post, f'ms_{idx}_notes'),
                })
    units = []
    for key in post:
        if key.startswith('ua_') and key.endswith('_floor'):
            idx = key.split('_')[1]
            if idx.isdigit():
                units.append({
                    'floor': _get(post, f'ua_{idx}_floor'),
                    'unit': _get(post, f'ua_{idx}_unit'),
                    'owner_type': _get(post, f'ua_{idx}_owner_type'),
                    'notes': _get(post, f'ua_{idx}_notes'),
                })
    guarantees = []
    for key in post:
        if key.startswith('gv_') and key.endswith('_type'):
            idx = key.split('_')[1]
            if idx.isdigit():
                guarantees.append({
                    'type': _get(post, f'gv_{idx}_type'),
                    'amount': parse_toman_amount(_get(post, f'gv_{idx}_amount')),
                    'notes': _get(post, f'gv_{idx}_notes'),
                })
    return {
        'owner_percent': _get(post, 'jv_owner_percent'),
        'builder_percent': _get(post, 'jv_builder_percent'),
        'start_date': _get(post, 'jv_start_date'),
        'duration_estimate': _get(post, 'jv_duration'),
        'delivery_date': _get(post, 'jv_delivery_date'),
        'contributions': {
            'owner': _get(post, 'jv_owner_contribution'),
            'builder': _get(post, 'jv_builder_contribution'),
        },
        'unit_allocations': units,
        'milestones': milestones,
        'guarantees': guarantees,
    }


def parse_witnesses(post: QueryDict) -> List[Dict[str, Any]]:
    witnesses = []
    for n in (1, 2):
        if _get(post, f'witness_{n}_first_name') or _get(post, f'witness_{n}_mobile'):
            witnesses.append(sanitize_witness_payload({
                'witness_number': n,
                'witness_role': _get(post, f'witness_{n}_role', f'شاهد {n}'),
                'first_name': _get(post, f'witness_{n}_first_name'),
                'last_name': _get(post, f'witness_{n}_last_name'),
                'national_id': _get(post, f'witness_{n}_national_id'),
                'mobile': _get(post, f'witness_{n}_mobile'),
            }))
    return witnesses


def _parse_costs(post: QueryDict) -> Dict[str, str]:
    costs = {}
    for key in ('water', 'electricity', 'gas', 'phone', 'charge', 'minor_repairs', 'major_repairs', 'property_tax'):
        val = _get(post, f'cost_{key}')
        if val in COST_RESPONSIBILITY_OPTIONS:
            costs[key] = val
    return costs


def _parse_penalties_from_prefixes(
    post: QueryDict,
    fields: tuple,
) -> Dict[str, Any]:
    penalties = {}
    for row in fields:
        key, prefix = row[0], row[1]
        if post.get(f'{prefix}_enabled') == 'on':
            penalties[key] = {
                'enabled': True,
                'amount_per_day': parse_toman_amount(_get(post, f'{prefix}_amount')),
                'unit': _get(post, f'{prefix}_unit', 'daily'),
            }
    return penalties


def parse_clauses(post: QueryDict, contract_type: str = '') -> Dict[str, Any]:
    """پارس مرحله بندها — تصمیمات ساختاریافته + توافقات اختصاصی."""
    from contracts.services.clause_ux import LEASE_PENALTY_FIELDS, SALE_PENALTY_FIELDS

    optional = [{'code': code} for code in post.getlist('clause_optional')]
    custom_agreements = []
    indices = set()
    for key in post:
        if key.startswith('custom_agreement_') and key.endswith('_body'):
            idx = key.split('_')[2]
            if idx.isdigit():
                indices.add(int(idx))
    for idx in sorted(indices):
        body = _get(post, f'custom_agreement_{idx}_body')
        if body.strip():
            custom_agreements.append({
                'title': _get(post, f'custom_agreement_{idx}_title', 'توافق اختصاصی'),
                'body': body.strip(),
            })
    custom_title = _get(post, 'custom_clause_title')
    custom_body = _get(post, 'custom_clause_body')
    if custom_body.strip():
        legacy_body = custom_body.strip()
        if not any(
            (a.get('body') or '').strip() == legacy_body for a in custom_agreements
        ):
            custom_agreements.append({
                'title': custom_title or 'توافق اختصاصی',
                'body': legacy_body,
            })

    result: Dict[str, Any] = {
        'optional_clauses': optional,
        'custom_agreements': custom_agreements,
    }
    if contract_type == 'lease':
        result['transfer_choice'] = _get(post, 'clause_transfer', 'denied')
        result['usage_type'] = _get(post, 'clause_usage', 'residential')
        occ = _get(post, 'clause_occupants')
        if occ:
            result['occupants_count'] = occ
        result['costs'] = _parse_costs(post)
        result['penalties'] = _parse_penalties_from_prefixes(post, LEASE_PENALTY_FIELDS)
    elif contract_type == 'sale':
        result['penalties'] = _parse_penalties_from_prefixes(post, SALE_PENALTY_FIELDS)
        result['sale_costs'] = _parse_sale_costs(post)
        result['property_has_tenant'] = _get(post, 'clause_has_tenant') == 'yes'
    return result


def _parse_sale_costs(post: QueryDict) -> Dict[str, str]:
    costs = {}
    for key in ('transfer_costs', 'notary_costs', 'pre_delivery_costs', 'post_delivery_costs', 'other_costs'):
        val = _get(post, f'sale_cost_{key}')
        if val in ('seller', 'buyer', 'shared'):
            costs[key] = val
    return costs


def parse_wizard_step(post: QueryDict, step: str, contract_type: str) -> Dict[str, Any]:
    if step == 'parties':
        return parse_parties(post)
    if step == 'property':
        return parse_property(post)
    if step == 'financial':
        if contract_type == 'lease':
            return parse_financial_lease(post)
        if contract_type == 'sale':
            return parse_financial_sale(post)
        if contract_type == 'jv':
            return parse_jv(post)
        return parse_financial_sale(post)
    if step == 'jv':
        return parse_jv(post)
    if step == 'witnesses':
        return parse_witnesses(post)
    if step == 'clauses':
        return parse_clauses(post, contract_type)
    return {}
