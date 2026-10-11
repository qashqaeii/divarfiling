"""اعتبارسنجی و نرمال‌سازی payload ویزارد قرارداد برای API موبایل (JSON)."""
from __future__ import annotations

from typing import Any, Dict, List, Set

from contracts.constants import (
    CONTRACT_TYPE_JV,
    CONTRACT_TYPE_LEASE,
    CONTRACT_TYPE_SALE,
    COST_RESPONSIBILITY_OPTIONS,
    PARTY_ROLES_BY_TYPE,
    PERSON_TYPES,
    WIZARD_DISPLAY_STEPS,
)
from contracts.services.money import parse_toman_amount
from contracts.services.party_sanitize import sanitize_party_payload, sanitize_witness_payload

PATCHABLE_WIZARD_STEPS: Set[str] = frozenset({
    'parties',
    'property',
    'financial',
    'witnesses',
    'clauses',
})


class WizardJsonError(ValueError):
    """خطای اعتبارسنجی payload ویزارد."""


def display_step_keys(contract_type: str) -> List[str]:
    steps = WIZARD_DISPLAY_STEPS.get(contract_type) or WIZARD_DISPLAY_STEPS[CONTRACT_TYPE_LEASE]
    return [key for key, _ in steps]


def assert_patchable_step(step: str, contract_type: str) -> None:
    step = (step or '').strip()
    if step not in PATCHABLE_WIZARD_STEPS:
        raise WizardJsonError('مرحله ویزارد نامعتبر است.')
    allowed = display_step_keys(contract_type)
    if step not in allowed:
        raise WizardJsonError('این مرحله برای نوع قرارداد انتخاب‌شده مجاز نیست.')


def _as_str(value: Any, *, max_len: int = 2000) -> str:
    if value is None:
        return ''
    text = str(value).strip()
    if len(text) > max_len:
        text = text[:max_len]
    return text


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = _as_str(value).lower()
    return text in ('1', 'true', 'yes', 'on')


def _normalize_amount(value: Any) -> Any:
    if value is None or value == '':
        return value
    if isinstance(value, (int, float)):
        return int(value)
    parsed = parse_toman_amount(_as_str(value))
    return parsed if parsed is not None else _as_str(value)


PROPERTY_ALLOWED_KEYS = frozenset({
    'crm_property_id', 'crm_property_title', 'property_type', 'usage',
    'province', 'city', 'county', 'district', 'neighborhood', 'address', 'postal_code',
    'area', 'build_year', 'total_floors', 'units_per_floor', 'floor', 'unit', 'bedrooms',
    'building_direction', 'unit_direction', 'facade_type', 'floor_type', 'kitchen_type',
    'bathroom_type', 'heating_system', 'cooling_system', 'has_parking', 'parking_number',
    'has_storage', 'storage_number', 'has_elevator', 'deed_type', 'deed_number',
    'main_plaque', 'sub_plaque', 'registration_section', 'utilities', 'common_areas',
    'has_mortgage', 'has_tenant', 'has_loan', 'has_debt', 'has_completion_cert',
    'has_separation_minutes', 'declared_by_parties',
})

PROPERTY_BOOL_KEYS = frozenset({
    'has_parking', 'has_storage', 'has_elevator', 'has_mortgage', 'has_tenant',
    'has_loan', 'has_debt', 'has_completion_cert', 'has_separation_minutes', 'declared_by_parties',
})

LEASE_FINANCIAL_AMOUNT_KEYS = frozenset({
    'deposit', 'monthly_rent', 'delivery_delay_penalty', 'previous_deposit_amount',
})

SALE_FINANCIAL_AMOUNT_KEYS = frozenset({
    'total_price', 'down_payment', 'earnest_money', 'remaining_amount_at_transfer',
})

JV_AMOUNT_KEYS = frozenset({'owner_contribution', 'builder_contribution'})


def _parse_parties_json(data: Any, contract_type: str) -> List[Dict[str, Any]]:
    if not isinstance(data, list):
        raise WizardJsonError('داده طرفین باید آرایه باشد.')
    allowed_roles = {r[0] for r in PARTY_ROLES_BY_TYPE.get(contract_type, ())}
    parties: List[Dict[str, Any]] = []
    for raw in data[:12]:
        if not isinstance(raw, dict):
            continue
        role = _as_str(raw.get('role'))
        if not role:
            continue
        if allowed_roles and role not in allowed_roles:
            raise WizardJsonError('نقش طرف قرارداد نامعتبر است.')
        parties.append(sanitize_party_payload({
            'role': role,
            'customer_id': _as_str(raw.get('customer_id')),
            'person_type': _as_str(raw.get('person_type'), max_len=32) or 'natural',
            'first_name': _as_str(raw.get('first_name'), max_len=120),
            'last_name': _as_str(raw.get('last_name'), max_len=120),
            'father_name': _as_str(raw.get('father_name'), max_len=120),
            'national_id': _as_str(raw.get('national_id'), max_len=20),
            'mobile': _as_str(raw.get('mobile'), max_len=20),
            'address': _as_str(raw.get('address'), max_len=500),
            'postal_code': _as_str(raw.get('postal_code'), max_len=20),
            'ownership_share': _as_str(raw.get('ownership_share'), max_len=32),
            'company_name': _as_str(raw.get('company_name'), max_len=200),
            'company_national_id': _as_str(raw.get('company_national_id'), max_len=20),
            'representative_name': _as_str(raw.get('representative_name'), max_len=200),
            'representative_national_id': _as_str(raw.get('representative_national_id'), max_len=20),
            'representative_mobile': _as_str(raw.get('representative_mobile'), max_len=20),
        }))
    if not parties:
        raise WizardJsonError('حداقل یک طرف باید ثبت شود.')
    return parties


def _parse_property_json(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise WizardJsonError('داده ملک باید شیء باشد.')
    out: Dict[str, Any] = {}
    for key, val in data.items():
        if key not in PROPERTY_ALLOWED_KEYS:
            continue
        if key in PROPERTY_BOOL_KEYS:
            out[key] = _as_bool(val)
        elif key == 'crm_property_id':
            cid = _as_str(val)
            out[key] = int(cid) if cid.isdigit() else None
        elif key == 'common_areas':
            if isinstance(val, list):
                out[key] = [_as_str(x, max_len=64) for x in val if _as_str(x)][:30]
            else:
                out[key] = []
        elif key == 'utilities' and isinstance(val, dict):
            util_out = {}
            for util_key, util_val in val.items():
                if not isinstance(util_val, dict):
                    continue
                util_out[_as_str(util_key, max_len=32)] = {
                    'connection_type': _as_str(util_val.get('connection_type'), max_len=64),
                    'subscription_no': _as_str(util_val.get('subscription_no'), max_len=64),
                    'bill_id': _as_str(util_val.get('bill_id'), max_len=64),
                }
            out[key] = util_out
        else:
            out[key] = _as_str(val, max_len=500) if not isinstance(val, (int, float, bool)) else val
    if out.get('crm_property_id') in (None, '', 0):
        out.pop('crm_property_id', None)
    return out


def _normalize_financial_dict(data: Dict[str, Any], amount_keys: Set[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, val in data.items():
        if key == 'payments' and isinstance(val, list):
            payments = []
            for idx, item in enumerate(val[:40]):
                if not isinstance(item, dict):
                    continue
                payments.append({
                    'label': _as_str(item.get('label'), max_len=120) or f'قسط {idx + 1}',
                    'amount': _normalize_amount(item.get('amount')),
                    'due_date': _as_str(item.get('due_date'), max_len=32),
                    'payment_method': _as_str(item.get('payment_method'), max_len=64),
                    'notes': _as_str(item.get('notes'), max_len=500),
                })
            out['payments'] = payments
        elif key == 'penalties' and isinstance(val, dict):
            penalties = {}
            for pen_key, pen_val in val.items():
                if not isinstance(pen_val, dict):
                    continue
                penalties[_as_str(pen_key, max_len=64)] = {
                    'enabled': _as_bool(pen_val.get('enabled')),
                    'amount_per_day': _normalize_amount(pen_val.get('amount_per_day')),
                    'unit': _as_str(pen_val.get('unit'), max_len=32) or 'daily',
                }
            out['penalties'] = penalties
        elif key == 'costs' and isinstance(val, dict):
            costs = {}
            for cost_key, cost_val in val.items():
                c = _as_str(cost_val, max_len=32)
                if c in COST_RESPONSIBILITY_OPTIONS:
                    costs[_as_str(cost_key, max_len=64)] = c
            out['costs'] = costs
        elif key == 'sale_costs' and isinstance(val, dict):
            sale_costs = {}
            for sc_key, sc_val in val.items():
                c = _as_str(sc_val, max_len=32)
                if c in ('seller', 'buyer', 'shared'):
                    sale_costs[_as_str(sc_key, max_len=64)] = c
            out['sale_costs'] = sale_costs
        elif key == 'contributions' and isinstance(val, dict):
            out['contributions'] = {
                'owner': _as_str(val.get('owner'), max_len=500),
                'builder': _as_str(val.get('builder'), max_len=500),
            }
        elif key in ('milestones', 'unit_allocations', 'guarantees') and isinstance(val, list):
            out[key] = val[:50]
        elif key in amount_keys:
            out[key] = _normalize_amount(val)
        else:
            out[key] = _as_str(val, max_len=500) if not isinstance(val, (int, float, bool, dict, list)) else val
    return out


def _parse_financial_json(data: Any, contract_type: str) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise WizardJsonError('داده مالی باید شیء باشد.')
    if contract_type == CONTRACT_TYPE_LEASE:
        return _normalize_financial_dict(data, LEASE_FINANCIAL_AMOUNT_KEYS)
    if contract_type == CONTRACT_TYPE_SALE:
        return _normalize_financial_dict(data, SALE_FINANCIAL_AMOUNT_KEYS)
    if contract_type == CONTRACT_TYPE_JV:
        return _normalize_financial_dict(data, JV_AMOUNT_KEYS)
    return _normalize_financial_dict(data, SALE_FINANCIAL_AMOUNT_KEYS)


def _parse_witnesses_json(data: Any) -> List[Dict[str, Any]]:
    if data is None:
        return []
    if not isinstance(data, list):
        raise WizardJsonError('داده شاهدان باید آرایه باشد.')
    witnesses = []
    for idx, raw in enumerate(data[:2], start=1):
        if not isinstance(raw, dict):
            continue
        if not (_as_str(raw.get('first_name')) or _as_str(raw.get('mobile'))):
            continue
        witnesses.append(sanitize_witness_payload({
            'witness_number': int(raw.get('witness_number') or idx),
            'witness_role': _as_str(raw.get('witness_role'), max_len=120) or f'شاهد {idx}',
            'first_name': _as_str(raw.get('first_name'), max_len=120),
            'last_name': _as_str(raw.get('last_name'), max_len=120),
            'national_id': _as_str(raw.get('national_id'), max_len=20),
            'mobile': _as_str(raw.get('mobile'), max_len=20),
        }))
    return witnesses


def _parse_clauses_json(data: Any, contract_type: str) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise WizardJsonError('داده بندها باید شیء باشد.')
    optional = []
    for item in data.get('optional_clauses') or []:
        if isinstance(item, str) and item.strip():
            optional.append({'code': item.strip()})
        elif isinstance(item, dict) and _as_str(item.get('code')):
            optional.append({'code': _as_str(item.get('code'), max_len=64)})
    custom_agreements = []
    for item in data.get('custom_agreements') or []:
        if not isinstance(item, dict):
            continue
        body = _as_str(item.get('body'), max_len=8000)
        if not body:
            continue
        custom_agreements.append({
            'title': _as_str(item.get('title'), max_len=200) or 'توافق اختصاصی',
            'body': body,
        })
    result: Dict[str, Any] = {
        'optional_clauses': optional,
        'custom_agreements': custom_agreements,
    }
    if contract_type == CONTRACT_TYPE_LEASE:
        transfer = _as_str(data.get('transfer_choice'), max_len=32)
        if transfer:
            result['transfer_choice'] = transfer
        usage = _as_str(data.get('usage_type'), max_len=32)
        if usage:
            result['usage_type'] = usage
        occ = _as_str(data.get('occupants_count'), max_len=16)
        if occ:
            result['occupants_count'] = occ
        if isinstance(data.get('costs'), dict):
            result['costs'] = _parse_financial_json({'costs': data['costs']}, CONTRACT_TYPE_LEASE).get('costs', {})
        if isinstance(data.get('penalties'), dict):
            result['penalties'] = _parse_financial_json({'penalties': data['penalties']}, CONTRACT_TYPE_LEASE).get('penalties', {})
    elif contract_type == CONTRACT_TYPE_SALE:
        if isinstance(data.get('penalties'), dict):
            result['penalties'] = _parse_financial_json({'penalties': data['penalties']}, CONTRACT_TYPE_SALE).get('penalties', {})
        if isinstance(data.get('sale_costs'), dict):
            result['sale_costs'] = _parse_financial_json({'sale_costs': data['sale_costs']}, CONTRACT_TYPE_SALE).get('sale_costs', {})
        result['property_has_tenant'] = _as_bool(data.get('property_has_tenant'))
    return result


def parse_wizard_json_step(step: str, data: Any, contract_type: str) -> Any:
    """اعتبارسنجی و نرمال‌سازی payload یک مرحله — خروجی آماده save_wizard_step."""
    assert_patchable_step(step, contract_type)
    if step == 'parties':
        return _parse_parties_json(data, contract_type)
    if step == 'property':
        return _parse_property_json(data)
    if step == 'financial':
        return _parse_financial_json(data, contract_type)
    if step == 'witnesses':
        return _parse_witnesses_json(data)
    if step == 'clauses':
        return _parse_clauses_json(data, contract_type)
    raise WizardJsonError('مرحله پشتیبانی نمی‌شود.')


def wizard_choices_payload(contract_type: str) -> Dict[str, Any]:
    from contracts.constants import WIZARD_UNIT_DIRECTIONS
    from workspace.services.property_features import (
        CHOICES_COOLING,
        CHOICES_DIRECTION,
        CHOICES_FACADE,
        CHOICES_FLOORING,
        CHOICES_HEATING,
        CHOICES_KITCHEN,
    )

    return {
        'party_roles': [
            {'value': code, 'label': label}
            for code, label in PARTY_ROLES_BY_TYPE.get(contract_type, ())
        ],
        'person_types': [{'value': code, 'label': label} for code, label in PERSON_TYPES],
        'cost_responsibility': list(COST_RESPONSIBILITY_OPTIONS),
        'property': {
            'unit_direction': WIZARD_UNIT_DIRECTIONS,
            'building_direction': CHOICES_DIRECTION,
            'facade_type': CHOICES_FACADE,
            'floor_type': CHOICES_FLOORING,
            'kitchen_type': CHOICES_KITCHEN,
            'heating_type': CHOICES_HEATING,
            'cooling_type': CHOICES_COOLING,
        },
    }
