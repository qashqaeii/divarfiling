"""پارس خروجی JSON از LLM — مقاوم در برابر markdown و متن اضافه."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

_JSON_FENCE_RE = re.compile(
    r'```(?:json|JSON)?\s*([\s\S]*?)```',
    re.MULTILINE,
)


def _try_load(candidate: str) -> Optional[Dict[str, Any]]:
    candidate = (candidate or '').strip().lstrip('\ufeff')
    if not candidate:
        return None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_braced_object(text: str) -> Optional[Dict[str, Any]]:
    start = text.find('{')
    while start >= 0:
        depth = 0
        for idx in range(start, len(text)):
            ch = text[idx]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    parsed = _try_load(text[start : idx + 1])
                    if parsed:
                        return parsed
                    break
        start = text.find('{', start + 1)
    return None


def parse_json_text(text: str) -> Optional[Dict[str, Any]]:
    text = (text or '').strip()
    if not text:
        return None

    direct = _try_load(text)
    if direct:
        return direct

    for match in _JSON_FENCE_RE.finditer(text):
        parsed = _try_load(match.group(1))
        if parsed:
            return parsed

    # بعضی مدل‌ها فقط یک ``` باز می‌گذارند
    if text.startswith('```'):
        stripped = re.sub(r'^```(?:json|JSON)?\s*', '', text)
        stripped = re.sub(r'\s*```\s*$', '', stripped)
        parsed = _try_load(stripped)
        if parsed:
            return parsed

    return _extract_braced_object(text)


_SUMMARY_FIELD_RE = re.compile(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
_NEGOTIATION_FIELD_RE = re.compile(r'"negotiation_tip"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
_ADVERTISER_FIELD_RE = re.compile(r'"advertiser_note"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
_HIGHLIGHTS_BLOCK_RE = re.compile(r'"highlights"\s*:\s*\[([\s\S]*)', re.DOTALL)
_HIGHLIGHT_ITEM_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def salvage_listing_json(text: str) -> Optional[Dict[str, Any]]:
    """استخراج فیلدها از JSON ناقص/بریده‌شده."""
    text = (text or '').strip()
    if not text:
        return None

    summary_match = _SUMMARY_FIELD_RE.search(text)
    if not summary_match:
        return None

    result: Dict[str, Any] = {'summary': summary_match.group(1).strip()}
    highlights: List[str] = []
    highlights_match = _HIGHLIGHTS_BLOCK_RE.search(text)
    if highlights_match:
        chunk = highlights_match.group(1)
        for item_match in _HIGHLIGHT_ITEM_RE.finditer(chunk):
            val = item_match.group(1).strip()
            if not val or val in ('summary', 'highlights', 'negotiation_tip', 'advertiser_note'):
                continue
            highlights.append(val)
            if len(highlights) >= 8:
                break
    if highlights:
        result['highlights'] = highlights

    negotiation_match = _NEGOTIATION_FIELD_RE.search(text)
    if negotiation_match:
        result['negotiation_tip'] = negotiation_match.group(1).strip()

    advertiser_match = _ADVERTISER_FIELD_RE.search(text)
    if advertiser_match:
        result['advertiser_note'] = advertiser_match.group(1).strip()

    return result
