"""Draft Storage — ذخیره و بازیابی پیش‌نویس."""
from __future__ import annotations

import copy
from typing import Any, Dict, Optional, Tuple

from workspace.models import CRMProperty, CRMPropertyContentStudioDraft
from workspace.services.property_content_studio.constants import DRAFT_VERSION
from workspace.services.property_content_studio.draft_validate import DraftValidationError, validate_and_merge_draft
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
    try:
        merged, _ = validate_and_merge_draft(stored, {})
    except DraftValidationError:
        merged = copy.deepcopy(base)
        for key in base:
            if key in stored:
                if isinstance(base[key], dict) and isinstance(stored[key], dict):
                    merged[key] = {**copy.deepcopy(base[key]), **stored[key]}
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


def save_draft(
    user,
    prop: CRMProperty,
    payload: Dict[str, Any],
    *,
    sync_property: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    fp = property_content_fingerprint(prop)
    stored = None
    existing = CRMPropertyContentStudioDraft.objects.filter(property=prop, user=user).first()
    if existing:
        stored = existing.payload
    merged, _ = validate_and_merge_draft(stored, payload)
    merged['version'] = DRAFT_VERSION
    draft, _ = CRMPropertyContentStudioDraft.objects.get_or_create(
        property=prop,
        user=user,
        defaults={'payload': merged, 'property_fingerprint': fp},
    )
    draft.payload = merged
    update_fields = ['payload', 'updated_at']
    if sync_property or not draft.property_fingerprint:
        draft.property_fingerprint = fp
        update_fields.append('property_fingerprint')
    draft.save(update_fields=update_fields)
    stale = bool(draft.property_fingerprint and draft.property_fingerprint != fp)
    return merged, {'stale': stale, 'fingerprint': fp, 'synced': sync_property}


def sync_draft_with_property(user, prop: CRMProperty) -> Dict[str, Any]:
    fp = property_content_fingerprint(prop)
    draft = CRMPropertyContentStudioDraft.objects.filter(property=prop, user=user).first()
    if not draft:
        return {'stale': False, 'fingerprint': fp}
    draft.property_fingerprint = fp
    draft.save(update_fields=['property_fingerprint', 'updated_at'])
    return {'stale': False, 'fingerprint': fp}


def delete_draft(user, prop: CRMProperty) -> None:
    CRMPropertyContentStudioDraft.objects.filter(property=prop, user=user).delete()
