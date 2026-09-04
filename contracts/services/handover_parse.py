"""پارس فرم صورت‌جلسه تحویل."""
from __future__ import annotations

from typing import Any, Dict

from django.http import QueryDict

from contracts.constants import HANDOVER_CONDITION_ITEMS, HANDOVER_CONDITION_STATUSES


def _get(post: QueryDict, key: str, default: str = '') -> str:
    return (post.get(key) or default).strip()


def parse_handover_step(post: QueryDict, step: str, handover) -> Dict[str, Any]:
    snap = handover.snapshot_json or {}
    parties = snap.get('parties') or []

    if step == 'basic':
        delivered_idx = _get(post, 'delivered_by_idx')
        received_idx = _get(post, 'received_by_idx')
        delivered = parties[int(delivered_idx)] if delivered_idx.isdigit() and int(delivered_idx) < len(parties) else {}
        received = parties[int(received_idx)] if received_idx.isdigit() and int(received_idx) < len(parties) else {}
        return {
            'handover_date': _get(post, 'handover_date') or None,
            'handover_time': _get(post, 'handover_time') or None,
            'delivered_by': delivered,
            'received_by': received,
            'notes': _get(post, 'notes'),
        }
    if step == 'keys':
        keys = []
        for key in post:
            if key.startswith('key_') and key.endswith('_type'):
                idx = key.split('_')[1]
                if idx.isdigit():
                    keys.append({
                        'type': _get(post, f'key_{idx}_type'),
                        'count': int(_get(post, f'key_{idx}_count', '1') or 1),
                        'notes': _get(post, f'key_{idx}_notes'),
                    })
        return {'keys': keys or snap.get('keys') or []}
    if step == 'meters':
        meters = []
        for util in ('water', 'electricity', 'gas'):
            meters.append({
                'utility': util,
                'meter_number': _get(post, f'meter_{util}_number'),
                'reading': _get(post, f'meter_{util}_reading'),
            })
        return {'meters': meters}
    if step == 'conditions':
        items = []
        for name in HANDOVER_CONDITION_ITEMS:
            status = _get(post, f'cond_{name}_status', 'unchecked')
            items.append({
                'item': name,
                'status': status,
                'note': _get(post, f'cond_{name}_note'),
            })
        return {'conditions': items}
    if step == 'equipment':
        equipment = []
        for key in post:
            if key.startswith('eq_') and key.endswith('_name'):
                idx = key.split('_')[1]
                if idx.isdigit():
                    equipment.append({
                        'name': _get(post, f'eq_{idx}_name'),
                        'count': _get(post, f'eq_{idx}_count', '1'),
                        'status': _get(post, f'eq_{idx}_status'),
                        'notes': _get(post, f'eq_{idx}_notes'),
                    })
        return {'equipment': equipment}
    return {}
