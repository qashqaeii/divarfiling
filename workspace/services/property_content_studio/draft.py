"""Draft Storage — ذخیره و بازیابی پیش‌نویس."""
from __future__ import annotations

import copy
from typing import Any, Dict, Optional, Tuple

from workspace.models import CRMProperty, CRMPropertyContentStudioDraft
from workspace.services.property_content_studio.constants import DRAFT_VERSION
from workspace.services.property_content_studio.fingerprint import property_content_fingerprint


def empty_draft_payload() -> Dict[str, Any]:
    return {
        'version': DRAFT_VERSION,
        'active_tab': 'posters',
        'format': 'story',
        'brand_override': {},
        'posters': {},
        'storyboard': {'slides': [], 'order': []},
        'ai': {
            'divar': {
                'titles': [],
                'selected_title_index': 0,
                'body': '',
                'body_style': 'formal',
            },
            'social': {
                'captions': [],
                'hashtags': [],
                'whatsapp_short': '',
                'whatsapp_full': '',
                'telegram': '',
                'ctas': [],
            },
        },
        'editor': {'open': False, 'template_id': 'luxury'},
    }


def _merge_payload(stored: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    base = empty_draft_payload()
    if not stored or not isinstance(stored, dict):
        return base
    merged = copy.deepcopy(base)
    for key in merged:
        if key in stored:
            if isinstance(merged[key], dict) and isinstance(stored[key], dict):
                merged[key].update(stored[key])
            else:
                merged[key] = stored[key]
    return merged


def get_or_create_draft(user, prop: CRMProperty) -> Tuple[CRMPropertyContentStudioDraft, Dict[str, Any]]:
    fp = property_content_fingerprint(prop)
    draft, created = CRMPropertyContentStudioDraft.objects.get_or_create(
        property=prop,
        user=user,
        defaults={'payload': empty_draft_payload(), 'property_fingerprint': fp},
    )
    payload = _merge_payload(draft.payload)
    stale = bool(draft.property_fingerprint and draft.property_fingerprint != fp)
    if created:
        draft.property_fingerprint = fp
        draft.payload = payload
        draft.save(update_fields=['payload', 'property_fingerprint'])
    return draft, {'payload': payload, 'stale': stale, 'fingerprint': fp}


def save_draft(user, prop: CRMProperty, payload: Dict[str, Any]) -> Dict[str, Any]:
    fp = property_content_fingerprint(prop)
    merged = _merge_payload(payload)
    merged['version'] = DRAFT_VERSION
    draft, _ = CRMPropertyContentStudioDraft.objects.get_or_create(
        property=prop,
        user=user,
        defaults={'payload': merged, 'property_fingerprint': fp},
    )
    draft.payload = merged
    draft.property_fingerprint = fp
    draft.save(update_fields=['payload', 'property_fingerprint', 'updated_at'])
    return merged


def delete_draft(user, prop: CRMProperty) -> None:
    CRMPropertyContentStudioDraft.objects.filter(property=prop, user=user).delete()
