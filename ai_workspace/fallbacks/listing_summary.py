"""Fallback خلاصه آگهی — rule-based."""
from __future__ import annotations

import json
from typing import Any, Dict, List


def build(context: Dict[str, Any]) -> Dict[str, Any]:
    title = context.get('title') or 'ملک'
    neighborhood = context.get('neighborhood') or ''
    city = context.get('city') or ''
    price_label = context.get('price_label') or ''
    area_label = context.get('area_label') or ''
    price_per_sqm = context.get('price_per_sqm_label') or ''
    rooms = context.get('rooms') or ''
    deal_mode = context.get('deal_mode') or ''
    verdict = context.get('benchmark_verdict') or ''

    loc = ' — '.join(p for p in (neighborhood, city) if p)
    summary_parts = [title]
    if loc:
        summary_parts.append(f'در {loc}')
    if deal_mode:
        summary_parts.append(f'({deal_mode})')
    if price_label:
        summary_parts.append(f'قیمت: {price_label}')
    if area_label:
        summary_parts.append(f'متراژ: {area_label}')

    highlights: List[str] = []
    if area_label:
        highlights.append(f'متراژ: {area_label}')
    if rooms:
        highlights.append(f'اتاق: {rooms}')
    if price_per_sqm:
        highlights.append(f'قیمت هر متر: {price_per_sqm}')
    if verdict:
        highlights.append(verdict)

    negotiation = ''
    if 'زیر' in verdict:
        negotiation = 'قیمت نسبت به بازار مناسب‌تر است — فرصت مذاکره قبل از بازدید.'
    elif 'بالا' in verdict:
        negotiation = 'قیمت بالاتر از میانه بازار — قبل از بازدید برای تخفیف منطقی مذاکره کنید.'

    payload = {
        'summary': ' · '.join(summary_parts),
        'highlights': highlights[:6],
        'negotiation_tip': negotiation,
    }
    return {
        'data': payload,
        'raw_text': json.dumps(payload, ensure_ascii=False),
        'is_fallback': True,
    }
