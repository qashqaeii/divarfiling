"""پارس خروجی JSON از LLM — مقاوم در برابر markdown و متن اضافه."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

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
