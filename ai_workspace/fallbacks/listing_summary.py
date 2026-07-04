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
    verdict = context.get('benchmark_verdict') or ''
    advertiser = context.get('advertiser_label') or ''

    loc = ' — '.join(p for p in (neighborhood, city) if p)
    summary_parts = [f'{title}']
    if loc:
        summary_parts.append(f'در {loc}')
    if price_label:
        summary_parts.append(f'قیمت: {price_label}')
    if area_label:
        summary_parts.append(f'متراژ: {area_label}')

    highlights: List[str] = []
    if verdict:
        highlights.append(verdict)
    if advertiser:
        highlights.append(f'نوع آگهی‌دهنده: {advertiser}')

    negotiation = ''
    if 'زیر' in verdict:
        negotiation = 'قیمت نسبت به بازار مناسب‌تر است — فرصت مذاکره قبل از بازدید.'
    elif 'بالا' in verdict:
        negotiation = 'قیمت بالاتر از میانه بازار — قبل از بازدید با مالک مذاکره کنید.'

    advertiser_note = ''
    if 'پنهان' in advertiser or 'مشاور' in advertiser:
        advertiser_note = 'در تماس، نوع آگهی‌دهنده را در نظر بگیرید.'

    payload = {
        'summary': ' · '.join(summary_parts),
        'highlights': highlights,
        'negotiation_tip': negotiation,
        'advertiser_note': advertiser_note,
    }
    return {
        'data': payload,
        'raw_text': json.dumps(payload, ensure_ascii=False),
        'is_fallback': True,
    }
