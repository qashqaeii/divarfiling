"""Canonical hash — deterministic representation of all contract-effective data."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from contracts.models import ContractVersion


def _norm_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value.normalize())
    if isinstance(value, float):
        return format(value, '.8f')
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return value.strip()
    return value


def _norm_dict(data: Any) -> Any:
    if isinstance(data, dict):
        return {str(k): _norm_dict(v) for k, v in sorted(data.items())}
    if isinstance(data, list):
        return [_norm_dict(v) for v in data]
    return _norm_scalar(data)


def _canonical_json(data: Any) -> str:
    normalized = _norm_dict(data)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _party_snapshot(version: ContractVersion) -> List[Dict]:
    return list(
        version.parties.order_by('sort_order', 'pk').values(
            'role', 'person_type', 'first_name', 'last_name', 'father_name',
            'national_id', 'birth_date', 'mobile', 'address', 'postal_code',
            'ownership_share',
            'company_name', 'company_national_id', 'company_registration_no',
            'representative_name', 'representative_national_id', 'representative_mobile',
            'sort_order',
        )
    )


def _witness_snapshot(version: ContractVersion) -> List[Dict]:
    return list(
        version.witnesses.order_by('witness_number').values(
            'witness_number', 'witness_role', 'first_name', 'last_name', 'national_id', 'mobile',
        )
    )


def _clause_snapshot(version: ContractVersion) -> List[Dict]:
    return list(
        version.clauses.filter(is_active=True).order_by('sort_order', 'pk').values(
            'code', 'title', 'category', 'body_text', 'inline_values', 'is_custom', 'sort_order',
        )
    )


def _payment_snapshot(version: ContractVersion) -> List[Dict]:
    rows = []
    for sched in version.payment_schedules.prefetch_related('payments').all():
        for p in sched.payments.order_by('sort_order', 'pk'):
            rows.append({
                'schedule_title': sched.title,
                'label': p.label,
                'amount': p.amount,
                'due_date': p.due_date.isoformat() if p.due_date else None,
                'payment_method': p.payment_method,
                'notes': p.notes,
                'sort_order': p.sort_order,
            })
    rows.sort(key=lambda r: (r.get('sort_order', 0), r.get('label', '')))
    return rows


def _attachment_manifest(version: ContractVersion) -> List[Dict]:
    return list(
        version.attachments.order_by('pk').values(
            'attachment_type', 'title', 'mime_type', 'file_size', 'is_visible_to_parties',
        )
    )


def build_version_snapshot(version: ContractVersion) -> Dict[str, Any]:
    contract = version.contract
    prop_snap = {}
    try:
        prop_snap = version.property_snapshot.data
    except Exception:
        pass

    fin = version.financial_data or {}
    jv = version.jv_data or {}

    return {
        'contract_type': contract.contract_type,
        'internal_number': contract.internal_number,
        'version_number': version.version_number,
        'parties': _party_snapshot(version),
        'witnesses': _witness_snapshot(version),
        'property': prop_snap,
        'financial': fin,
        'jv': {
            'owner_percent': jv.get('owner_percent'),
            'builder_percent': jv.get('builder_percent'),
            'contributions': jv.get('contributions') or {},
            'unit_allocations': jv.get('unit_allocations') or [],
            'milestones': jv.get('milestones') or [],
            'guarantees': jv.get('guarantees') or [],
        },
        'clauses': _clause_snapshot(version),
        'payments': _payment_snapshot(version),
        'attachments': _attachment_manifest(version),
        'important_dates': {
            'lease_start': fin.get('lease_start'),
            'lease_end': fin.get('lease_end'),
            'delivery_date': fin.get('delivery_date'),
            'vacate_date': fin.get('vacate_date'),
            'official_transfer_date': fin.get('official_transfer_date'),
        },
    }


def compute_content_hash(version: ContractVersion) -> str:
    snapshot = build_version_snapshot(version)
    return hashlib.sha256(_canonical_json(snapshot).encode('utf-8')).hexdigest()


def acceptance_hash_valid(acceptance, version: Optional[ContractVersion] = None) -> bool:
    version = version or acceptance.version
    expected = version.content_hash or compute_content_hash(version)
    stored = acceptance.accepted_content_hash or acceptance.content_hash
    return stored == expected
