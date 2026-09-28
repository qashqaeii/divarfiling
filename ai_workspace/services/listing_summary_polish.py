"""پولیش خروجی خلاصه هوشمند — خوانایی و یکدستی برای UI."""
from __future__ import annotations

import re
from typing import Any, Dict, List

_SUMMARY_MAX_CHARS = 420
_HIGHLIGHT_MAX_ITEMS = 6
_HIGHLIGHT_MAX_WORDS = 14
_NEGOTIATION_MAX_WORDS = 26

_CLICHE_RE = re.compile(
    r'(فرصت\s*طلایی|بی[\u200c\s]*نظیر|فوق[\u200c\s]*العاده|استثنایی|حتما\s*ببینید|عالی\s*برای)',
    re.IGNORECASE,
)
_PREFIX_RE = re.compile(
    r'^(مالی|ملک|موقعیت|بازار|ویژگی|امکانات|معامله|تحلیل)\s*[—\-–:]\s*',
    re.IGNORECASE,
)
_BULLET_RE = re.compile(r'^[\s•\-\*·]+')
_WS_RE = re.compile(r'\s+')


def _word_count(text: str) -> int:
    return len([w for w in (text or '').split() if w])


def _trim_words(text: str, max_words: int) -> str:
    words = (text or '').split()
    if len(words) <= max_words:
        return text.strip()
    return ' '.join(words[:max_words]).rstrip('،,.') + '…'


def _clean_line(text: str) -> str:
    line = (text or '').strip()
    line = _BULLET_RE.sub('', line)
    line = _PREFIX_RE.sub('', line)
    line = _WS_RE.sub(' ', line)
    return line.strip()


def _polish_summary(text: str) -> str:
    raw = (text or '').strip()
    if not raw:
        return ''
    # چندخطی مدل را به پاراگراف روان تبدیل کن
    parts = [p.strip() for p in re.split(r'[\n\r]+', raw) if p.strip()]
    merged = ' '.join(parts)
    merged = _WS_RE.sub(' ', merged).strip()
    merged = re.sub(r'\s*([،؛])\s*', r'\1 ', merged)
    if len(merged) > _SUMMARY_MAX_CHARS:
        merged = merged[: _SUMMARY_MAX_CHARS - 1].rstrip() + '…'
    return merged


def _polish_highlight(item: str) -> str:
    line = _clean_line(item)
    line = _CLICHE_RE.sub('', line).strip()
    line = _trim_words(line, _HIGHLIGHT_MAX_WORDS)
    if line and not line.endswith(('۔', '.', '!', '؟')):
        line = line.rstrip('،,')
    return line


def _polish_negotiation(text: str) -> str:
    line = _clean_line(text)
    line = _trim_words(line, _NEGOTIATION_MAX_WORDS)
    if line and not line.endswith(('۔', '.', '!', '؟')):
        line += '۔'
    return line


def _dedupe_highlights(items: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for item in items:
        key = re.sub(r'\s+', ' ', item.lower())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= _HIGHLIGHT_MAX_ITEMS:
            break
    return out


def polish_listing_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """نرمال‌سازی نهایی برای نمایش در CRM."""
    out = dict(data)
    out['summary'] = _polish_summary(str(out.get('summary') or ''))
    highlights = [_polish_highlight(str(h)) for h in _coerce_list(out.get('highlights'))]
    highlights = [h for h in highlights if h and len(h) >= 4]
    out['highlights'] = _dedupe_highlights(highlights)
    tip = _polish_negotiation(str(out.get('negotiation_tip') or ''))
    out['negotiation_tip'] = tip
    return out


def _coerce_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [value]
    return []
