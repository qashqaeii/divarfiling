"""Post-process Management AI Persian text for product terminology."""
from __future__ import annotations

import re
from typing import Any, Dict

# Longer phrases first
_LICENSE_TERM_REPLACEMENTS = (
    ('پروانه فعالیت', 'لایسنس'),
    ('پروانه کسب‌وکار', 'لایسنس'),
    ('پروانه کسب', 'لایسنس'),
    ('مجوز فعالیت', 'لایسنس'),
    ('بدون پروانه', 'بدون لایسنس'),
    ('فاقد پروانه', 'فاقد لایسنس'),
    ('پروانه', 'لایسنس'),
)


def polish_management_text(text: str) -> str:
    if not text:
        return text
    out = text
    for src, dst in _LICENSE_TERM_REPLACEMENTS:
        out = out.replace(src, dst)
    return out


def polish_analysis_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    data['summary'] = polish_management_text(str(data.get('summary') or ''))

    for key in ('insights', 'actions', 'risks', 'opportunities'):
        block = data.get(key)
        if not isinstance(block, list):
            continue
        for item in block:
            if not isinstance(item, dict):
                continue
            for field in ('title', 'description'):
                if field in item:
                    item[field] = polish_management_text(str(item[field] or ''))
    return data


def contains_forbidden_license_terms(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r'پروانه|مجوز فعالیت', text))
