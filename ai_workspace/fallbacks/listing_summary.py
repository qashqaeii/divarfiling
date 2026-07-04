"""Fallback خلاصه آگهی — rule-based."""
from __future__ import annotations

import json
from typing import Any, Dict, List


def _first_line_block(text: str) -> List[str]:
    return [line.strip() for line in str(text or '').splitlines() if line.strip()]


def build(context: Dict[str, Any]) -> Dict[str, Any]:
    title = context.get('title') or 'ملک'
    neighborhood = context.get('neighborhood') or ''
    city = context.get('city') or ''
    deal_mode = context.get('deal_mode') or ''
    verdict = context.get('benchmark_verdict') or ''
    bench = context.get('benchmark') or {}

    loc = ' — '.join(p for p in (neighborhood, city) if p)
    summary_parts = [title]
    if loc:
        summary_parts.append(f'در {loc}')
    if deal_mode:
        summary_parts.append(f'({deal_mode})')

    financial_lines = _first_line_block(context.get('tab_financial') or context.get('price_label') or '')
    property_lines = _first_line_block(context.get('tab_property') or '')
    if financial_lines:
        summary_parts.append(financial_lines[0])
    elif context.get('price_label'):
        summary_parts.append(str(context['price_label']))
    if property_lines:
        summary_parts.append(property_lines[0])
    elif context.get('area_label'):
        summary_parts.append(f"متراژ: {context['area_label']}")
    if verdict:
        summary_parts.append(verdict)

    highlights: List[str] = []
    for block in (
        context.get('tab_property') or '',
        context.get('tab_financial') or '',
        context.get('tab_features') or '',
    ):
        for line in _first_line_block(block):
            if line not in highlights:
                highlights.append(line)
            if len(highlights) >= 5:
                break
        if len(highlights) >= 5:
            break
    if verdict and verdict not in highlights:
        highlights.append(verdict)
    if bench.get('diff_pct') and bench.get('market_median'):
        bench_line = f"میانه بازار: {bench['market_median']} (اختلاف {bench['diff_pct']})"
        if bench_line not in highlights:
            highlights.append(bench_line)

    negotiation = ''
    if 'زیر' in verdict:
        negotiation = 'نسبت به میانه بازار ارزان‌تر است — قبل از بازدید برای تثبیت شرایط مذاکره کنید.'
    elif 'بالا' in verdict:
        negotiation = 'قیمت بالاتر از میانه بازار — برای تخفیف منطقی مذاکره کنید.'
    elif bench.get('note'):
        negotiation = str(bench['note'])

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
