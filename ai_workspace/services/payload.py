"""نرمال‌سازی و اعتبارسنجی payload خروجی JSON."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from ai_workspace.constants import (
    FEATURE_LISTING_SUMMARY,
    FEATURE_NL_COMMAND,
    FEATURE_PROPERTY_CONTENT_STUDIO,
    FEATURE_UPLOAD_BRIEF,
    NL_COMMAND_ALLOWED_INTENTS,
    NL_COMMAND_INTENT_CREATE_CONTACT,
    NL_COMMAND_INTENT_CREATE_PERSONAL_PROPERTY,
    NL_COMMAND_INTENT_CREATE_REMINDER,
)
from ai_workspace.services.property_content_studio_payload import (
    normalize_studio_ai_payload,
    validate_studio_ai_payload,
)
from ai_workspace.services.listing_summary_polish import polish_listing_payload
from ai_workspace.services.parse import parse_json_text, salvage_listing_json

_STRING_FIELD_RE = re.compile(r'"(summary|negotiation_tip|advertiser_note|executive_summary|outliers_note|duplicates_note)"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
_LIST_FIELD_RE = re.compile(r'"(highlights|opportunities|action_items)"\s*:\s*\[', re.DOTALL)


def _looks_like_json_blob(value: str) -> bool:
    text = (value or '').strip()
    return text.startswith('{') or text.startswith('[')


def _coerce_str_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _merge_listing_fields(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(target)
    for key in ('summary', 'negotiation_tip'):
        val = source.get(key)
        if isinstance(val, str) and val.strip() and not _looks_like_json_blob(val):
            merged[key] = val.strip()
    for key in ('highlights',):
        items = _coerce_str_list(source.get(key))
        if items:
            merged[key] = items
    return merged


def normalize_listing_payload(data: Optional[Dict[str, Any]], raw_text: str = '') -> Dict[str, Any]:
    payload = dict(data or {})
    raw_candidates = [
        raw_text,
        payload.get('raw') if isinstance(payload.get('raw'), str) else '',
        payload.get('summary') if isinstance(payload.get('summary'), str) and _looks_like_json_blob(payload.get('summary')) else '',
    ]

    for candidate in raw_candidates:
        if not candidate or not candidate.strip():
            continue
        parsed = parse_json_text(candidate) or salvage_listing_json(candidate)
        if parsed:
            payload = _merge_listing_fields(payload, parsed)

    for key in ('summary', 'negotiation_tip'):
        val = payload.get(key)
        if isinstance(val, str):
            payload[key] = val.strip()
    payload['highlights'] = _coerce_str_list(payload.get('highlights'))
    payload.pop('advertiser_note', None)
    payload.pop('raw', None)
    return polish_listing_payload(payload)


def is_valid_listing_payload(data: Optional[Dict[str, Any]]) -> bool:
    if not data or not isinstance(data, dict):
        return False
    summary = data.get('summary')
    if not isinstance(summary, str) or not summary.strip():
        return False
    if _looks_like_json_blob(summary):
        return False
    if len(summary) < 20:
        return False
    return True


def normalize_upload_brief_payload(data: Optional[Dict[str, Any]], raw_text: str = '') -> Dict[str, Any]:
    payload = dict(data or {})
    raw_candidates = [
        raw_text,
        payload.get('raw') if isinstance(payload.get('raw'), str) else '',
        payload.get('executive_summary') if isinstance(payload.get('executive_summary'), str) and _looks_like_json_blob(payload.get('executive_summary')) else '',
    ]
    for candidate in raw_candidates:
        if not candidate or not candidate.strip():
            continue
        parsed = parse_json_text(candidate) or _salvage_upload_brief_json(candidate)
        if parsed:
            for key, val in parsed.items():
                if key.endswith('_note') or key == 'executive_summary':
                    if isinstance(val, str) and val.strip():
                        payload[key] = val.strip()
                elif key in ('opportunities', 'action_items'):
                    items = _coerce_str_list(val)
                    if items:
                        payload[key] = items
    for key in ('executive_summary', 'outliers_note', 'duplicates_note'):
        val = payload.get(key)
        if isinstance(val, str):
            payload[key] = val.strip()
    for key in ('opportunities', 'action_items'):
        payload[key] = _coerce_str_list(payload.get(key))
    payload.pop('raw', None)
    return payload


def _salvage_upload_brief_json(text: str) -> Optional[Dict[str, Any]]:
    text = (text or '').strip()
    if not text:
        return None
    result: Dict[str, Any] = {}
    for match in _STRING_FIELD_RE.finditer(text):
        result[match.group(1)] = match.group(2)
    for match in _LIST_FIELD_RE.finditer(text):
        key = match.group(1)
        start = match.end()
        chunk = text[start:]
        items: List[str] = []
        for item_match in re.finditer(r'"((?:[^"\\]|\\.)*)"', chunk):
            val = item_match.group(1).strip()
            if val and val not in result:
                items.append(val)
            if len(items) >= 8:
                break
        if items:
            result[key] = items
    return result if result.get('executive_summary') else None


def is_valid_upload_brief_payload(data: Optional[Dict[str, Any]]) -> bool:
    if not data or not isinstance(data, dict):
        return False
    summary = data.get('executive_summary')
    if not isinstance(summary, str) or not summary.strip():
        return False
    if _looks_like_json_blob(summary):
        return False
    return len(summary) >= 20


def _nullable_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _nullable_int(value: Any) -> Optional[int]:
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _nullable_float(value: Any) -> Optional[float]:
    if value is None or value == '':
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_contact_preferences(inner: Dict[str, Any]) -> Dict[str, Any]:
    prefs = inner.get('preferences') if isinstance(inner.get('preferences'), dict) else {}
    areas_raw = prefs.get('areas')
    if areas_raw is None:
        areas_raw = inner.get('areas')
    if isinstance(areas_raw, list):
        areas = [str(x).strip() for x in areas_raw if str(x).strip()] or None
    else:
        areas = _nullable_str(areas_raw)
    amenities = prefs.get('required_amenities')
    if isinstance(amenities, list):
        amenities_norm = [str(x).strip() for x in amenities if str(x).strip()] or None
    else:
        amenities_norm = amenities
    rooms_raw = prefs.get('rooms')
    rooms = _nullable_str(rooms_raw) if rooms_raw is not None else None
    return {
        'areas': areas,
        'property_type': _nullable_str(prefs.get('property_type')),
        'min_area': _nullable_int(prefs.get('min_area') if prefs.get('min_area') is not None else prefs.get('area_min')),
        'max_area': _nullable_int(prefs.get('max_area') if prefs.get('max_area') is not None else prefs.get('area_max')),
        'rooms_min': _nullable_int(prefs.get('rooms_min')),
        'rooms_max': _nullable_int(prefs.get('rooms_max')),
        'year_min': _nullable_int(prefs.get('year_min') if prefs.get('year_min') is not None else prefs.get('build_year_min')),
        'year_max': _nullable_int(prefs.get('year_max') if prefs.get('year_max') is not None else prefs.get('build_year_max')),
        'floor_min': _nullable_int(prefs.get('floor_min')),
        'floor_max': _nullable_int(prefs.get('floor_max')),
        'budget_min': _nullable_int(prefs.get('budget_min')),
        'budget_max': _nullable_int(prefs.get('budget_max')),
        'deposit_min': _nullable_int(prefs.get('deposit_min')),
        'deposit_max': _nullable_int(prefs.get('deposit_max')),
        'rent_min': _nullable_int(prefs.get('rent_min')),
        'rent_max': _nullable_int(prefs.get('rent_max')),
        'rooms': rooms,
        'required_amenities': amenities_norm,
    }


def _normalize_reminder_data(inner: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'contact_name': _nullable_str(inner.get('contact_name')),
        'title': _nullable_str(inner.get('title')),
        'note': _nullable_str(inner.get('note')),
        'date_text': _nullable_str(inner.get('date_text')),
        'time_text': _nullable_str(inner.get('time_text')),
    }


def _nullable_bool(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return value


def _normalize_property_location(inner: Dict[str, Any]) -> Dict[str, Any]:
    loc = inner.get('location') if isinstance(inner.get('location'), dict) else {}
    return {
        'city': _nullable_str(loc.get('city') if loc.get('city') is not None else inner.get('city')),
        'district': _nullable_str(loc.get('district') if loc.get('district') is not None else inner.get('district')),
        'neighborhood': _nullable_str(
            loc.get('neighborhood') if loc.get('neighborhood') is not None else inner.get('neighborhood')
        ),
        'address': _nullable_str(loc.get('address') if loc.get('address') is not None else inner.get('address')),
    }


def _normalize_property_data(inner: Dict[str, Any]) -> Dict[str, Any]:
    loc = _normalize_property_location(inner)
    specs = inner.get('specs') if isinstance(inner.get('specs'), dict) else {}
    features = inner.get('features') if isinstance(inner.get('features'), dict) else {}
    financial = inner.get('financial') if isinstance(inner.get('financial'), dict) else {}
    crm = inner.get('crm') if isinstance(inner.get('crm'), dict) else {}
    owner = inner.get('owner') if isinstance(inner.get('owner'), dict) else {}

    amenities = inner.get('amenities')
    if amenities is None:
        amenities = features.get('amenity_labels')
    if isinstance(amenities, list):
        amenities_norm = [str(x).strip() for x in amenities if str(x).strip()]
    else:
        amenities_norm = amenities

    def _pick(*keys):
        for key in keys:
            if key[0] is not None and key[0].get(key[1]) is not None:
                return key[0].get(key[1])
            if key[2] is not None:
                return key[2]
        return None

    return {
        'title': _nullable_str(inner.get('title')),
        'property_type': _nullable_str(inner.get('property_type')),
        'deal_mode': _nullable_str(inner.get('deal_mode')),
        'location': loc,
        'specs': {
            'area': _nullable_float(_pick((specs, 'area', inner.get('area')))),
            'rooms': _nullable_str(_pick((specs, 'rooms', inner.get('rooms')))),
            'floor': _nullable_int(_pick((specs, 'floor', inner.get('floor')))),
            'total_floors': _nullable_int(_pick((specs, 'total_floors', inner.get('total_floors')))),
            'build_year': _nullable_int(_pick((specs, 'build_year', inner.get('build_year')))),
        },
        'features': {
            'has_parking': _nullable_bool(
                features.get('has_parking') if features.get('has_parking') is not None else inner.get('has_parking')
            ),
            'has_storage': _nullable_bool(
                features.get('has_storage') if features.get('has_storage') is not None else inner.get('has_storage')
            ),
            'has_elevator': _nullable_bool(
                features.get('has_elevator') if features.get('has_elevator') is not None else inner.get('has_elevator')
            ),
            'is_vacant': _nullable_bool(
                features.get('is_vacant') if features.get('is_vacant') is not None else inner.get('is_vacant')
            ),
            'amenity_labels': amenities_norm if isinstance(amenities_norm, list) else None,
        },
        'financial': {
            'sale_price': _nullable_int(
                financial.get('sale_price') if financial.get('sale_price') is not None else inner.get('sale_price')
            ),
            'deposit': _nullable_int(
                financial.get('deposit') if financial.get('deposit') is not None else inner.get('deposit')
            ),
            'monthly_rent': _nullable_int(
                financial.get('monthly_rent') if financial.get('monthly_rent') is not None else inner.get('monthly_rent')
            ),
        },
        'crm': {
            'transaction_status': _nullable_str(
                crm.get('transaction_status') if crm.get('transaction_status') is not None else inner.get('transaction_status')
            ),
            'publish_status': _nullable_str(
                crm.get('publish_status') if crm.get('publish_status') is not None else inner.get('publish_status')
            ),
            'business_type': _nullable_str(
                crm.get('business_type') if crm.get('business_type') is not None else inner.get('business_type')
            ),
        },
        'owner': {
            'phone': _nullable_str(owner.get('phone') if owner.get('phone') is not None else inner.get('phone')),
            'owner_name': _nullable_str(
                owner.get('owner_name') if owner.get('owner_name') is not None else inner.get('owner_name')
            ),
        },
        'area': _nullable_float(inner.get('area') if inner.get('area') is not None else specs.get('area')),
        'rooms': _nullable_str(inner.get('rooms')) if inner.get('rooms') is not None else _nullable_str(specs.get('rooms')),
        'floor': _nullable_int(inner.get('floor') if inner.get('floor') is not None else specs.get('floor')),
        'total_floors': _nullable_int(
            inner.get('total_floors') if inner.get('total_floors') is not None else specs.get('total_floors')
        ),
        'build_year': _nullable_int(
            inner.get('build_year') if inner.get('build_year') is not None else specs.get('build_year')
        ),
        'has_parking': _nullable_bool(inner.get('has_parking')),
        'has_storage': _nullable_bool(inner.get('has_storage')),
        'has_elevator': _nullable_bool(inner.get('has_elevator')),
        'sale_price': _nullable_int(inner.get('sale_price')),
        'deposit': _nullable_int(inner.get('deposit')),
        'monthly_rent': _nullable_int(inner.get('monthly_rent')),
        'amenities': amenities_norm,
        'notes': _nullable_str(inner.get('notes')),
    }


def _normalize_contact_subgroup(inner: Dict[str, Any], key: str) -> Dict[str, Any]:
    block = inner.get(key)
    return dict(block) if isinstance(block, dict) else {}


def _normalize_contact_data(inner: Dict[str, Any]) -> Dict[str, Any]:
    contact = _normalize_contact_subgroup(inner, 'contact')
    location = _normalize_contact_subgroup(inner, 'location')
    profile = _normalize_contact_subgroup(inner, 'profile')
    financial = _normalize_contact_subgroup(inner, 'financial')
    crm = _normalize_contact_subgroup(inner, 'crm')
    prefs = _normalize_contact_preferences(inner)

    phone = _nullable_str(inner.get('phone'))
    if phone is None:
        phone = _nullable_str(contact.get('phone'))

    source = _nullable_str(inner.get('source'))
    if source is None:
        source = _nullable_str(crm.get('source'))

    tags = crm.get('tags')
    if isinstance(tags, list):
        tags_norm = [str(x).strip() for x in tags if str(x).strip()] or None
    else:
        tags_norm = _nullable_str(tags)

    return {
        'name': _nullable_str(inner.get('name')),
        'phone': phone,
        'customer_type': _nullable_str(inner.get('customer_type')),
        'source': source,
        'contact': {
            'phone': phone,
            'phone_alt': _nullable_str(contact.get('phone_alt')),
            'email': _nullable_str(contact.get('email')),
        },
        'location': {
            'city': _nullable_str(location.get('city')),
            'district': _nullable_str(location.get('district')),
        },
        'profile': {
            'job': _nullable_str(profile.get('job')),
            'gender': _nullable_str(profile.get('gender')),
            'is_legal_entity': _nullable_bool(profile.get('is_legal_entity')),
            'company_name': _nullable_str(profile.get('company_name')),
        },
        'financial': {
            'budget_min': _nullable_int(financial.get('budget_min')),
            'budget_max': _nullable_int(financial.get('budget_max')),
            'deposit_min': _nullable_int(financial.get('deposit_min')),
            'deposit_max': _nullable_int(financial.get('deposit_max')),
            'rent_min': _nullable_int(financial.get('rent_min')),
            'rent_max': _nullable_int(financial.get('rent_max')),
        },
        'preferences': prefs,
        'crm': {
            'status': _nullable_str(crm.get('status')),
            'priority': _nullable_str(crm.get('priority')),
            'source': source,
            'next_followup_date_text': _nullable_str(
                crm.get('next_followup_date_text')
                if crm.get('next_followup_date_text') is not None
                else crm.get('next_followup')
            ),
            'tags': tags_norm,
        },
        'notes': _nullable_str(inner.get('notes')),
    }


def normalize_nl_command_payload(data: Optional[Dict[str, Any]], raw_text: str = '') -> Dict[str, Any]:
    payload = dict(data or {})
    if not payload and raw_text:
        parsed = parse_json_text(raw_text)
        if parsed:
            payload = dict(parsed)
    intent = str(payload.get('intent') or '').strip()
    if intent not in NL_COMMAND_ALLOWED_INTENTS:
        intent = 'unknown'
    inner = payload.get('data') if isinstance(payload.get('data'), dict) else {}
    if intent == NL_COMMAND_INTENT_CREATE_CONTACT:
        normalized_data = _normalize_contact_data(inner)
    elif intent == NL_COMMAND_INTENT_CREATE_PERSONAL_PROPERTY:
        normalized_data = _normalize_property_data(inner)
    else:
        normalized_data = _normalize_reminder_data(inner)
    missing = payload.get('missing_fields')
    ambiguous = payload.get('ambiguous_fields')
    return {
        'intent': intent,
        'confidence': float(payload.get('confidence') or 0.0),
        'data': normalized_data,
        'missing_fields': _coerce_str_list(missing),
        'ambiguous_fields': _coerce_str_list(ambiguous),
        'requires_confirmation': bool(payload.get('requires_confirmation', True)),
    }


def is_valid_nl_command_payload(data: Optional[Dict[str, Any]]) -> bool:
    if not data or not isinstance(data, dict):
        return False
    intent = data.get('intent')
    if intent not in NL_COMMAND_ALLOWED_INTENTS:
        return False
    if not isinstance(data.get('data'), dict):
        return False
    return True


def normalize_property_content_studio_payload(
    data: Optional[Dict[str, Any]],
    raw_text: str = '',
) -> Dict[str, Any]:
    parsed = dict(data or {})
    if not parsed and raw_text:
        parsed = parse_json_text(raw_text) or {}
    for task in ('divar_titles', 'poster_headlines', 'divar_body', 'social_pack'):
        norm = normalize_studio_ai_payload(task, parsed, raw_text)
        if validate_studio_ai_payload(task, norm):
            return norm
    return normalize_studio_ai_payload('divar_body', parsed, raw_text)


def is_valid_property_content_studio_payload(data: Optional[Dict[str, Any]]) -> bool:
    if not data:
        return False
    for task in ('divar_titles', 'poster_headlines', 'divar_body', 'social_pack'):
        if validate_studio_ai_payload(task, data):
            return True
    return False


def normalize_payload(feature: str, data: Optional[Dict[str, Any]], raw_text: str = '') -> Dict[str, Any]:
    if feature == FEATURE_LISTING_SUMMARY:
        return normalize_listing_payload(data, raw_text)
    if feature == FEATURE_UPLOAD_BRIEF:
        return normalize_upload_brief_payload(data, raw_text)
    if feature == FEATURE_NL_COMMAND:
        return normalize_nl_command_payload(data, raw_text)
    if feature == FEATURE_PROPERTY_CONTENT_STUDIO:
        return normalize_property_content_studio_payload(data, raw_text)
    return dict(data or {})


def is_valid_payload(feature: str, data: Optional[Dict[str, Any]]) -> bool:
    if feature == FEATURE_LISTING_SUMMARY:
        return is_valid_listing_payload(data)
    if feature == FEATURE_UPLOAD_BRIEF:
        return is_valid_upload_brief_payload(data)
    if feature == FEATURE_NL_COMMAND:
        return is_valid_nl_command_payload(data)
    if feature == FEATURE_PROPERTY_CONTENT_STUDIO:
        return is_valid_property_content_studio_payload(data)
    return bool(data)


def dumps_payload(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)
