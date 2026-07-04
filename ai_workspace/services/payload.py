"""نرمال‌سازی و اعتبارسنجی payload خروجی JSON."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from ai_workspace.constants import FEATURE_LISTING_SUMMARY, FEATURE_UPLOAD_BRIEF
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
    for key in ('summary', 'negotiation_tip', 'advertiser_note'):
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

    for key in ('summary', 'negotiation_tip', 'advertiser_note'):
        val = payload.get(key)
        if isinstance(val, str):
            payload[key] = val.strip()
    payload['highlights'] = _coerce_str_list(payload.get('highlights'))
    payload.pop('raw', None)
    return payload


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


def normalize_payload(feature: str, data: Optional[Dict[str, Any]], raw_text: str = '') -> Dict[str, Any]:
    if feature == FEATURE_LISTING_SUMMARY:
        return normalize_listing_payload(data, raw_text)
    if feature == FEATURE_UPLOAD_BRIEF:
        return normalize_upload_brief_payload(data, raw_text)
    return dict(data or {})


def is_valid_payload(feature: str, data: Optional[Dict[str, Any]]) -> bool:
    if feature == FEATURE_LISTING_SUMMARY:
        return is_valid_listing_payload(data)
    if feature == FEATURE_UPLOAD_BRIEF:
        return is_valid_upload_brief_payload(data)
    return bool(data)


def dumps_payload(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)
