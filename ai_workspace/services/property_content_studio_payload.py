"""اعتبارسنجی JSON خروجی استودیو محتوا."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ai_workspace.services.parse import parse_json_text

from workspace.services.property_content_studio.constants import DIVAR_AD_DESCRIPTION_MAX_CHARS, DIVAR_AD_TITLE_MAX_CHARS


def _clip(text: str, max_len: int) -> str:
    t = (text or '').strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + '…'


def _str_list(value: Any, max_items: int = 30) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()][:max_items]
    if isinstance(value, str):
        parts = re.split(r'[\s,]+', value.strip())
        return [p for p in parts if p][:max_items]
    return []


def normalize_studio_ai_payload(task: str, data: Optional[Dict[str, Any]], raw_text: str = '') -> Dict[str, Any]:
    payload = dict(data or {})
    if not payload and raw_text:
        parsed = parse_json_text(raw_text)
        if parsed:
            payload = dict(parsed)

    if task == 'divar_titles':
        titles = payload.get('titles') or []
        cleaned = []
        for item in titles if isinstance(titles, list) else []:
            if not isinstance(item, dict):
                continue
            text = _clip(str(item.get('text') or ''), DIVAR_AD_TITLE_MAX_CHARS)
            if text:
                cleaned.append({
                    'style': str(item.get('style') or '').strip()[:40] or 'پیشنهادی',
                    'text': text,
                })
        return {'titles': cleaned[:5]}

    if task == 'divar_body':
        body = _clip(str(payload.get('body') or ''), DIVAR_AD_DESCRIPTION_MAX_CHARS)
        style = str(payload.get('style') or '').strip()[:30]
        return {'body': body, 'style': style}

    if task == 'social_pack':
        captions = []
        for item in payload.get('captions') or []:
            if isinstance(item, dict):
                text = str(item.get('text') or '').strip()
                if text:
                    captions.append({
                        'style': str(item.get('style') or '').strip()[:40] or 'پیشنهادی',
                        'text': text[:2000],
                    })
        hashtags = []
        for tag in _str_list(payload.get('hashtags'), 40):
            t = tag if tag.startswith('#') else f'#{tag.lstrip("#")}'
            hashtags.append(t[:80])
        return {
            'captions': captions[:5],
            'hashtags': hashtags,
            'whatsapp_short': str(payload.get('whatsapp_short') or '').strip()[:1500],
            'whatsapp_full': str(payload.get('whatsapp_full') or '').strip()[:2500],
            'telegram': str(payload.get('telegram') or '').strip()[:2500],
            'ctas': _str_list(payload.get('ctas'), 8),
        }

    return dict(payload)


_FACT_DENY_PATTERNS = {
    'has_parking': re.compile(r'پارکینگ\s*(دارد|موجود|ویژه)', re.I),
    'has_storage': re.compile(r'انبار(?:ی)?\s*(دارد|موجود)', re.I),
    'has_elevator': re.compile(r'آسانسور\s*(دارد|موجود)', re.I),
}


def _scrub_text_for_facts(prop, text: str) -> str:
    out = text or ''
    for field, pattern in _FACT_DENY_PATTERNS.items():
        if not getattr(prop, field, False):
            out = pattern.sub('', out)
    return re.sub(r'\s{2,}', ' ', out).strip()


def enforce_property_facts(prop, task: str, data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """حذف ادعاهای قطعی درباره امکاناتی که در ملک ثبت نشده‌اند."""
    payload = dict(data or {})
    if task == 'divar_titles':
        titles = []
        for item in payload.get('titles') or []:
            if not isinstance(item, dict):
                continue
            text = _scrub_text_for_facts(prop, str(item.get('text') or ''))
            if text:
                titles.append({**item, 'text': text})
        payload['titles'] = titles
    elif task == 'divar_body':
        payload['body'] = _scrub_text_for_facts(prop, str(payload.get('body') or ''))
    elif task == 'social_pack':
        caps = []
        for item in payload.get('captions') or []:
            if not isinstance(item, dict):
                continue
            text = _scrub_text_for_facts(prop, str(item.get('text') or ''))
            if text:
                caps.append({**item, 'text': text})
        payload['captions'] = caps
        for key in ('whatsapp_short', 'whatsapp_full', 'telegram'):
            if key in payload:
                payload[key] = _scrub_text_for_facts(prop, str(payload.get(key) or ''))
    return payload


def validate_studio_ai_payload(task: str, data: Optional[Dict[str, Any]]) -> bool:
    if not data:
        return False
    if task == 'divar_titles':
        titles = data.get('titles') or []
        return isinstance(titles, list) and len(titles) >= 1
    if task == 'divar_body':
        return bool((data.get('body') or '').strip())
    if task == 'social_pack':
        return bool((data.get('captions') or []) or (data.get('hashtags') or []))
    return True
