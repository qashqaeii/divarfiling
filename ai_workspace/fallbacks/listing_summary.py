"""Fallback خلاصه آگهی — rule-based / مدل داخلی سیستم."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

_AMENITY_KEYS = (
    'پارکینگ', 'انباری', 'آسانسور', 'بالکن', 'استخر', 'سونا',
    'جکوزی', 'مبله', 'بازسازی', 'حیاط', 'انشعاب', 'گرمایش', 'سرمایش',
)


def _first_line_block(text: str) -> List[str]:
    return [line.strip() for line in str(text or '').splitlines() if line.strip()]


def _dedupe(items: List[str], limit: int = 8) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
        if len(out) >= limit:
            break
    return out


def _labeled_lines(block: str, prefix: str, limit: int = 4) -> List[str]:
    lines: List[str] = []
    for raw in _first_line_block(block):
        if ':' in raw:
            lines.append(raw)
        else:
            lines.append(f'{prefix}{raw}')
        if len(lines) >= limit:
            break
    return lines


def _amenity_highlights(context: Dict[str, Any], feature_lines: List[str]) -> List[str]:
    found: List[str] = []
    haystack = '\n'.join([
        context.get('tab_features') or '',
        context.get('tab_property') or '',
        context.get('tab_extra') or '',
    ])
    for key in _AMENITY_KEYS:
        if re.search(rf'\b{re.escape(key)}\b', haystack, flags=re.IGNORECASE):
            if key not in found:
                found.append(key)
    for line in feature_lines:
        for key in _AMENITY_KEYS:
            if key in line and key not in found:
                found.append(key)
    positive = [a for a in found if 'ندارد' not in a and 'بدون' not in a]
    return positive[:5]


def _market_highlight(bench: Dict[str, Any], verdict: str) -> str:
    median = bench.get('market_median') or bench.get('market_median_fmt') or ''
    diff = bench.get('diff_pct') or ''
    metric = bench.get('metric_label') or bench.get('label') or 'موقعیت قیمت'
    listing_val = bench.get('listing_value') or bench.get('price_per_sqm_fmt') or ''
    parts: List[str] = []
    if listing_val:
        parts.append(f'{metric}: {listing_val}')
    if median:
        parts.append(f'میانه بازار: {median}')
    if diff not in (None, '', '—'):
        parts.append(f'اختلاف: {diff}')
    if verdict and verdict not in parts:
        parts.append(verdict)
    return ' · '.join(str(p) for p in parts if p)


def _build_intro(context: Dict[str, Any]) -> str:
    title = (context.get('title') or 'ملک').strip() or 'ملک'
    neighborhood = (context.get('neighborhood') or '').strip()
    city = (context.get('city') or '').strip()
    deal_mode = (context.get('deal_mode') or '').strip()
    loc = '، '.join(p for p in (neighborhood, city) if p)
    head = title
    if loc:
        head += f' — {loc}'
    if deal_mode:
        head += f' ({deal_mode})'
    return head


def _build_specs_sentence(context: Dict[str, Any], property_lines: List[str]) -> str:
    bits: List[str] = []
    if context.get('area_label'):
        bits.append(f"متراژ {context['area_label']}")
    elif context.get('area'):
        bits.append(f"متراژ {context['area']}")
    if context.get('rooms'):
        bits.append(f"{context['rooms']} خواب")
    if context.get('floor'):
        bits.append(f"طبقه {context['floor']}")
    if context.get('build_year'):
        bits.append(f"ساخت {context['build_year']}")
    if not bits:
        for line in property_lines[:3]:
            if ':' in line:
                bits.append(line.split(':', 1)[1].strip())
            else:
                bits.append(line)
    if not bits:
        return ''
    return 'مشخصات: ' + ' · '.join(bits[:5])


def _build_financial_sentence(financial_lines: List[str], context: Dict[str, Any]) -> str:
    if financial_lines:
        return 'معامله: ' + ' · '.join(financial_lines[:3])
    price = (context.get('price_label') or '').strip()
    if price:
        return f'معامله: {price}'
    pps = (context.get('price_per_sqm_label') or '').strip()
    if pps:
        return f'قیمت هر متر: {pps}'
    return ''


def build(context: Dict[str, Any]) -> Dict[str, Any]:
    verdict = (context.get('benchmark_verdict') or '').strip()
    bench = context.get('benchmark') or {}

    financial_lines = _first_line_block(context.get('tab_financial') or '')
    if not financial_lines and context.get('price_label'):
        financial_lines = [str(context['price_label'])]
    property_lines = _first_line_block(context.get('tab_property') or '')
    location_lines = _first_line_block(context.get('tab_location') or '')
    feature_lines = _first_line_block(context.get('tab_features') or '')

    intro = _build_intro(context)
    specs = _build_specs_sentence(context, property_lines).replace('مشخصات: ', '')
    financial = _build_financial_sentence(financial_lines, context).replace('معامله: ', '')

    amenities = _amenity_highlights(context, feature_lines)
    market_line = _market_highlight(bench, verdict) or (verdict if verdict else '')

    summary_sentences: List[str] = []
    head = intro
    if specs:
        head += f' با {specs}'
    summary_sentences.append(head.rstrip(' .') + '.')
    if financial:
        summary_sentences.append(f'شرایط معامله: {financial.rstrip(".")}.')
    if market_line:
        summary_sentences.append(f'نسبت به فایلینگ شما: {market_line.rstrip(".")}.')
    elif amenities:
        summary_sentences.append(
            'امکانات قابل‌توجه: ' + '، '.join(amenities[:4]) + '.'
        )

    excerpt = (context.get('description_excerpt') or context.get('tab_text') or '').strip()
    if excerpt and len(excerpt) > 40 and len(summary_sentences) < 3:
        first_sentence = excerpt.split('\n')[0].strip()
        if len(first_sentence) > 160:
            first_sentence = first_sentence[:157].rstrip() + '…'
        if first_sentence:
            summary_sentences.append(first_sentence.rstrip('.') + '.')

    summary = ' '.join(summary_sentences[:3])

    highlights: List[str] = []
    for line in financial_lines[:2]:
        text = line if ':' in line else f'قیمت و معامله: {line}'
        highlights.append(text)
    for line in property_lines[:3]:
        text = line if ':' in line else line
        highlights.append(text)
    for line in location_lines[:2]:
        text = line if ':' in line else f'موقعیت: {line}'
        highlights.append(text)
    for amenity in amenities[:3]:
        highlights.append(f'امکانات شامل {amenity}')
    for feat in feature_lines[:2]:
        if feat not in highlights:
            highlights.append(feat)
    if market_line:
        highlights.append(f'وضعیت بازار: {market_line}')
    note = (context.get('benchmark_note') or bench.get('note') or '').strip()
    if note and note not in highlights:
        highlights.append(note)

    highlights = _dedupe(highlights, limit=7)

    negotiation = ''
    if 'زیر' in verdict:
        negotiation = (
            'این فایل نسبت به میانه بازار مقرون‌به‌صرفه‌تر است — '
            'قبل از بازدید، شرایط مذاکره و زمان‌بندی تحویل را با مالک هماهنگ کنید.'
        )
    elif 'بالا' in verdict:
        negotiation = (
            'قیمت بالاتر از میانه بازار برآورد شده — '
            'برای جذب مشتری جدی، پیشنهاد تخفیف مرحله‌ای یا اصلاح شرایط پرداخت را مدنظر داشته باشید.'
        )
    elif 'متعارف' in verdict or 'محدوده' in verdict:
        negotiation = (
            'فایل در محدوده متعارف بازار قرار دارد — '
            'برای تمایز، روی نقاط قوت ملک (موقعیت، نور، امکانات) در ارائه به مشتری تأکید کنید.'
        )
    elif bench.get('note'):
        negotiation = str(bench['note'])
    elif amenities:
        negotiation = (
            f"امکانات {', '.join(amenities[:3])} از نقاط قوت این فایل برای معرفی به مشتری است — "
            'در پیام اولیه حتماً ذکر شوند.'
        )
    elif financial_lines:
        negotiation = 'قیمت و شرایط معامله را قبل از بازدید با مشتری شفاف کنید تا پیگیری سریع‌تر انجام شود.'

    payload = {
        'summary': summary,
        'highlights': highlights,
        'negotiation_tip': negotiation,
    }
    return {
        'data': payload,
        'raw_text': json.dumps(payload, ensure_ascii=False),
        'is_fallback': True,
    }
