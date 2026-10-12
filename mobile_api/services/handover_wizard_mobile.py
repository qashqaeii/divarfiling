"""API موبایل — ویزارد صورت‌جلسه تحویل (GET/PATCH/ایجاد)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db import transaction

from contracts.constants import (
    CONTRACT_TYPE_LEASE,
    HANDOVER_CONDITION_ITEMS,
    HANDOVER_CONDITION_STATUSES,
)
from contracts.services.handover import HandoverError, create_handover, publish_handover, save_handover_step
from contracts.services.handover_wizard import VALID_STEPS, build_handover_wizard_context, sync_handover_delivery_parties
from contracts.services.scope import contract_for_user
from mobile_api.services.contracts_mobile import assert_mobile_contract_license, handover_summary


class HandoverJsonError(ValueError):
    pass


_VALID_STATUSES = {value for value, _ in HANDOVER_CONDITION_STATUSES}


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip() or default)
    except (TypeError, ValueError):
        return default


def _as_str(value, max_len: int = 500) -> str:
    text = (value or '').strip() if isinstance(value, str) else str(value or '').strip()
    return text[:max_len]


def parse_handover_json_step(step: str, data: Any, handover) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise HandoverJsonError('داده مرحله باید شیء باشد.')
    snap = handover.snapshot_json or {}
    parties: List[dict] = list(snap.get('parties') or [])

    if step == 'basic':
        delivered_idx = data.get('delivered_by_idx')
        received_idx = data.get('received_by_idx')
        delivered = {}
        received = {}
        if isinstance(delivered_idx, int) and 0 <= delivered_idx < len(parties):
            delivered = parties[delivered_idx]
        elif isinstance(delivered_idx, str) and delivered_idx.isdigit():
            idx = int(delivered_idx)
            if 0 <= idx < len(parties):
                delivered = parties[idx]
        if isinstance(received_idx, int) and 0 <= received_idx < len(parties):
            received = parties[received_idx]
        elif isinstance(received_idx, str) and received_idx.isdigit():
            idx = int(received_idx)
            if 0 <= idx < len(parties):
                received = parties[idx]
        return {
            'handover_date': _as_str(data.get('handover_date'), 32) or None,
            'handover_time': _as_str(data.get('handover_time'), 16) or None,
            'delivered_by': delivered,
            'received_by': received,
            'notes': _as_str(data.get('notes'), 4000),
        }
    if step == 'keys':
        keys = []
        for item in data.get('keys') or []:
            if not isinstance(item, dict):
                continue
            key_type = _as_str(item.get('type'), 120)
            count = _safe_int(item.get('count'), 0)
            notes = _as_str(item.get('notes'), 500)
            if not key_type or (count <= 0 and not notes):
                continue
            keys.append({'type': key_type, 'count': max(count, 0), 'notes': notes})
        return {'keys': keys}
    if step == 'meters':
        meters = []
        for item in data.get('meters') or []:
            if not isinstance(item, dict):
                continue
            util = _as_str(item.get('utility'), 32)
            if not util:
                continue
            meters.append({
                'utility': util,
                'meter_number': _as_str(item.get('meter_number'), 64),
                'reading': _as_str(item.get('reading'), 64),
                'notes': _as_str(item.get('notes'), 500),
            })
        if not meters:
            for util in ('electricity', 'water', 'gas'):
                meters.append({
                    'utility': util,
                    'meter_number': _as_str(data.get(f'meter_{util}_number'), 64),
                    'reading': _as_str(data.get(f'meter_{util}_reading'), 64),
                    'notes': _as_str(data.get(f'meter_{util}_notes'), 500),
                })
        return {'meters': meters}
    if step == 'conditions':
        items = []
        incoming = {row.get('item'): row for row in (data.get('conditions') or []) if isinstance(row, dict)}
        for name in HANDOVER_CONDITION_ITEMS:
            row = incoming.get(name) or {}
            status = _as_str(row.get('status') or data.get(f'cond_{name}_status'), 32) or 'unchecked'
            if status not in _VALID_STATUSES:
                status = 'unchecked'
            items.append({
                'item': name,
                'status': status,
                'note': _as_str(row.get('note') or data.get(f'cond_{name}_note'), 500),
            })
        return {'conditions': items}
    if step == 'equipment':
        equipment = []
        for item in data.get('equipment') or []:
            if not isinstance(item, dict):
                continue
            name = _as_str(item.get('name'), 200)
            if not name:
                continue
            status = _as_str(item.get('status'), 32) or 'ok'
            if status not in _VALID_STATUSES:
                status = 'ok'
            equipment.append({
                'name': name,
                'count': _as_str(item.get('count'), 16) or '1',
                'status': status,
                'notes': _as_str(item.get('notes'), 500),
            })
        return {'equipment': equipment}
    raise HandoverJsonError('مرحله پشتیبانی نمی‌شود.')


def _serialize_attachment(att) -> Dict[str, Any]:
    return {
        'id': att.pk,
        'title': att.title or '',
        'mime_type': att.mime_type or '',
        'created_at': att.created_at.isoformat() if att.created_at else None,
    }


def _serialize_party_card(card: Optional[dict]) -> Optional[Dict[str, Any]]:
    if not card:
        return None
    return {
        'index': card.get('index'),
        'first_name': card.get('first_name') or '',
        'last_name': card.get('last_name') or '',
        'name': card.get('name') or '',
        'role': card.get('role') or '',
        'role_label': card.get('role_label') or '',
        'mobile': card.get('mobile') or '',
        'national_id': card.get('national_id') or '',
        'is_delivered': bool(card.get('is_delivered')),
        'is_received': bool(card.get('is_received')),
    }


def _serialize_review(review: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(review)
    out['delivered'] = _serialize_party_card(out.get('delivered'))
    out['received'] = _serialize_party_card(out.get('received'))
    photos = []
    for att in out.pop('photos', []) or []:
        if hasattr(att, 'pk'):
            photos.append(_serialize_attachment(att))
        elif isinstance(att, dict):
            photos.append(att)
    out['photos'] = photos
    keys = []
    for row in out.get('keys') or []:
        if isinstance(row, dict):
            keys.append({
                'type': row.get('type') or '',
                'count': row.get('count') or 0,
                'notes': row.get('notes') or '',
            })
    out['keys'] = keys
    meters = []
    for row in out.get('meters') or []:
        if isinstance(row, dict):
            meters.append({
                'utility': row.get('utility') or '',
                'label': row.get('label') or '',
                'reading': row.get('reading') or '',
                'meter_number': row.get('meter_number') or '',
                'notes': row.get('notes') or '',
            })
    out['meters'] = meters
    equipment = []
    for row in out.get('equipment') or []:
        if isinstance(row, dict):
            equipment.append({
                'name': row.get('name') or '',
                'count': row.get('count') or '',
                'status': row.get('status') or '',
                'status_label': row.get('status_label') or '',
                'notes': row.get('notes') or '',
            })
    out['equipment'] = equipment
    conditions = []
    for row in out.get('conditions') or []:
        if isinstance(row, dict):
            conditions.append({
                'item': row.get('item') or '',
                'status': row.get('status') or '',
                'status_label': row.get('status_label') or '',
                'note': row.get('note') or '',
            })
    out['conditions'] = conditions
    return out


def _serialize_wizard_context(ctx: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(ctx)
    photos = []
    for att in out.pop('photos', []) or []:
        photos.append(_serialize_attachment(att))
    out['photos'] = photos
    review = out.get('review')
    if isinstance(review, dict):
        out['review'] = _serialize_review(review)
    out['condition_statuses'] = [
        {'value': value, 'label': label}
        for value, label in (out.get('condition_statuses') or HANDOVER_CONDITION_STATUSES)
    ]
    out['display_steps'] = [
        {'key': key, 'label': label}
        for key, label in (out.get('display_steps') or [])
    ]
    for list_key in ('party_cards', 'deliverer_party_cards', 'receiver_party_cards'):
        cards = []
        for card in out.get(list_key) or []:
            serialized = _serialize_party_card(card)
            if serialized:
                cards.append(serialized)
        out[list_key] = cards
    return out


def _handover_pdf_flags(handover) -> Dict[str, bool]:
    has_stored = bool(handover.pdf_file)
    preview_ok = handover.status in ('draft', 'pending', 'sent', 'finalized')
    return {
        'pdf_available': has_stored or preview_ok,
        'pdf_stored': has_stored,
    }


def handover_create_payload(user, contract_id: int, *, request=None) -> Dict[str, Any]:
    assert_mobile_contract_license(user)
    contract = contract_for_user(user, contract_id)
    if not contract:
        raise ValueError('قرارداد یافت نشد.')
    try:
        handover = create_handover(user, contract.pk, request=request)
    except HandoverError as exc:
        raise ValueError(str(exc)) from exc
    sync_handover_delivery_parties(handover)
    ctx = build_handover_wizard_context(handover, step='basic')
    return {
        'handover_id': handover.pk,
        'contract_id': contract.pk,
        'summary': handover_summary(contract),
        'wizard': _serialize_wizard_context(ctx),
    }


def handover_wizard_get_payload(
    user,
    contract_id: int,
    handover_id: int,
    *,
    step: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    assert_mobile_contract_license(user)
    contract = contract_for_user(user, contract_id)
    if not contract:
        return None
    handover = contract.handovers.filter(pk=handover_id).first()
    if not handover:
        return None
    sync_handover_delivery_parties(handover)
    step_key = (step or 'basic').strip()
    if step_key not in VALID_STEPS:
        step_key = 'basic'
    ctx = build_handover_wizard_context(handover, step=step_key)
    pdf_flags = _handover_pdf_flags(handover)
    review = ctx.get('review') or {}
    return {
        'handover_id': handover.pk,
        'contract_id': contract.pk,
        'status': handover.status,
        'status_label': handover.get_status_display(),
        'can_edit': handover.status in ('draft', 'pending'),
        'send_disabled': bool(review.get('send_disabled')) if step_key == 'review' else False,
        **pdf_flags,
        'wizard': _serialize_wizard_context(ctx),
    }


@transaction.atomic
def handover_wizard_patch_payload(
    user,
    contract_id: int,
    handover_id: int,
    *,
    step: str,
    data: Any,
    publish: bool = False,
    request=None,
) -> Dict[str, Any]:
    assert_mobile_contract_license(user)
    contract = contract_for_user(user, contract_id)
    if not contract:
        raise ValueError('قرارداد یافت نشد.')
    handover = contract.handovers.filter(pk=handover_id).first()
    if not handover:
        raise ValueError('صورت‌جلسه یافت نشد.')
    if handover.status not in ('draft', 'pending'):
        raise ValueError('این صورت‌جلسه قابل ویرایش نیست.')
    step_key = (step or 'basic').strip()
    if step_key not in VALID_STEPS:
        raise HandoverJsonError('مرحله نامعتبر است.')
    parsed = parse_handover_json_step(step_key, data, handover)
    try:
        save_handover_step(handover, step_key, parsed, user=user)
    except HandoverError as exc:
        raise ValueError(str(exc)) from exc
    if publish:
        try:
            publish_handover(handover, user=user, request=request)
        except HandoverError as exc:
            raise ValueError(str(exc)) from exc
    handover.refresh_from_db()
    sync_handover_delivery_parties(handover)
    ctx = build_handover_wizard_context(handover, step=step_key)
    pdf_flags = _handover_pdf_flags(handover)
    review = ctx.get('review') or {}
    return {
        'handover_id': handover.pk,
        'contract_id': contract.pk,
        'status': handover.status,
        'status_label': handover.get_status_display(),
        'can_edit': handover.status in ('draft', 'pending'),
        'published': publish,
        'send_disabled': bool(review.get('send_disabled')) if step_key == 'review' else False,
        **pdf_flags,
        'wizard': _serialize_wizard_context(ctx),
    }
