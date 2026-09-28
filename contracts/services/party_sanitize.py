"""نرمال‌سازی فیلدهای طرف قرارداد برای تطابق با محدودیت مدل."""
from __future__ import annotations

from typing import Any, Dict

from contracts.constants import PERSON_TYPE_LEGAL, PERSON_TYPE_NATURAL


def _digits(value: str) -> str:
    return ''.join(c for c in (value or '') if c.isdigit())


def sanitize_personal_national_id(value: str) -> str:
    return _digits(value)[:10]


def sanitize_company_national_id(value: str) -> str:
    return _digits(value)[:20]


def sanitize_postal_code(value: str) -> str:
    return _digits(value)[:10]


def sanitize_party_payload(party: Dict[str, Any]) -> Dict[str, Any]:
    """مقادیر طرف قرارداد را قبل از ذخیره در ContractParty نرمال می‌کند."""
    data = dict(party)
    person_type = (data.get('person_type') or PERSON_TYPE_NATURAL).strip()
    if person_type not in (PERSON_TYPE_NATURAL, PERSON_TYPE_LEGAL):
        person_type = PERSON_TYPE_NATURAL
    data['person_type'] = person_type

    national_id = (data.get('national_id') or '').strip()
    company_national_id = (data.get('company_national_id') or '').strip()

    if person_type == PERSON_TYPE_LEGAL:
        if national_id and not company_national_id:
            company_national_id = national_id
            national_id = ''
        elif national_id and len(_digits(national_id)) > 10:
            if not company_national_id:
                company_national_id = national_id
            national_id = ''

    data['national_id'] = sanitize_personal_national_id(national_id)
    data['company_national_id'] = sanitize_company_national_id(company_national_id)
    data['representative_national_id'] = sanitize_personal_national_id(
        data.get('representative_national_id', ''),
    )
    data['postal_code'] = sanitize_postal_code(data.get('postal_code', ''))
    cid = data.get('customer_id')
    if cid in (None, '', 0, '0'):
        data.pop('customer_id', None)
    else:
        try:
            data['customer_id'] = int(cid)
        except (TypeError, ValueError):
            data.pop('customer_id', None)
    return data


def sanitize_witness_payload(witness: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(witness)
    data['national_id'] = sanitize_personal_national_id(data.get('national_id', ''))
    return data
