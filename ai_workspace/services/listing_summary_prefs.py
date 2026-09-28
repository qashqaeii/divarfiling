"""لحن و سبک خلاصه هوشمند — تزریق به context و پاسخ API."""
from __future__ import annotations

from typing import Any, Dict, Tuple

from ai_workspace.constants import (
    listing_summary_style_meta,
    listing_summary_tone_meta,
)


def parse_listing_summary_preferences(body: Dict[str, Any] | None) -> Tuple[str, str]:
    data = body or {}
    tone = listing_summary_tone_meta(data.get('tone'))['key']
    style = listing_summary_style_meta(data.get('style'))['key']
    return tone, style


def apply_listing_summary_preferences(
    context: Dict[str, Any],
    *,
    tone: str | None,
    style: str | None,
) -> Dict[str, Any]:
    ctx = dict(context)
    tone_info = listing_summary_tone_meta(tone)
    style_info = listing_summary_style_meta(style)
    ctx['tone'] = tone_info['key']
    ctx['tone_label'] = tone_info['label']
    ctx['tone_hint'] = tone_info['hint']
    ctx['tone_guide'] = tone_info['guide']
    ctx['style'] = style_info['key']
    ctx['style_label'] = style_info['label']
    ctx['style_hint'] = style_info['hint']
    ctx['style_guide'] = style_info['guide']
    base_cv = str(ctx.get('content_version') or '').strip()
    suffix = f"t={tone_info['key']}|s={style_info['key']}"
    ctx['content_version'] = f'{base_cv}|{suffix}' if base_cv else suffix
    return ctx


def preference_labels(tone: str, style: str) -> Dict[str, str]:
    t = listing_summary_tone_meta(tone)
    s = listing_summary_style_meta(style)
    return {
        'tone': t['key'],
        'tone_label': t['label'],
        'style': s['key'],
        'style_label': s['label'],
    }
