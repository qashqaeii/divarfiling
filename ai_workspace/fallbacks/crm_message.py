"""Fallback پیام CRM — rule-based حرفه‌ای با لینک صفحه عمومی."""
from __future__ import annotations

from typing import Any, Dict, List


def build(context: Dict[str, Any]) -> str:
    matches = context.get('top_matches') or []
    if matches or (context.get('top_matches_text') or '').strip():
        return _matches_message(context, matches)
    return _followup_message(context)


def _greeting(context: Dict[str, Any]) -> str:
    name = (context.get('name') or '').strip() or 'مشتری'
    tone = context.get('tone') or 'رسمی'
    if tone == 'صمیمی':
        return f'سلام {name} عزیز،'
    return f'سلام، وقت بخیر؛ خدمت {name}،'


def _closing(context: Dict[str, Any]) -> str:
    tone = context.get('tone') or 'رسمی'
    if tone == 'صمیمی':
        return 'هر وقت سوالی داشتید در خدمتم.'
    return 'با احترام'


def _format_match_body(index: int, match: Dict[str, Any]) -> str:
    title = match.get('title') or 'ملک'
    price = match.get('price_label') or ''
    hood = ' — '.join(
        p for p in (match.get('neighborhood'), match.get('city')) if p
    )
    score = match.get('score')
    deal = match.get('deal_mode') or ''
    public_url = match.get('public_url') or ''

    bits = [f'{index}. {title}']
    if deal:
        bits.append(f'({deal})')
    detail_parts = []
    if hood:
        detail_parts.append(hood)
    if price:
        detail_parts.append(price)
    if score is not None:
        detail_parts.append(f'امتیاز تطابق سیستم: {int(round(float(score)))}٪')
    if detail_parts:
        bits.append(' — '.join(detail_parts))
    line = ' '.join(bits)
    if public_url:
        line += f'\n   مشاهده جزئیات: {public_url}'
    return line


def _matches_message(context: Dict[str, Any], matches: List[Dict[str, Any]]) -> str:
    lines = [_greeting(context), '']

    areas = (context.get('areas') or '').strip()
    customer_type = (context.get('customer_type') or '').strip()
    budget = (context.get('budget_range') or '').strip()

    intro_bits = []
    if customer_type:
        intro_bits.append(f'درخواست {customer_type}')
    if areas:
        intro_bits.append(f'در مناطق {areas}')
    if budget:
        intro_bits.append(f'با بودجه {budget}')
    if intro_bits:
        lines.append(
            'با توجه به ' + ' '.join(intro_bits) + '، '
            f'{len(matches) or 2} پیشنهاد با بالاترین تطابق سیستم را خدمتتان معرفی می‌کنم:'
        )
    else:
        lines.append('پیشنهادهای زیر بیشترین تطابق را با درخواست شما دارند:')
    lines.append('')

    if matches:
        for i, match in enumerate(matches[:2], start=1):
            lines.append(_format_match_body(i, match))
            lines.append('')
    elif context.get('top_matches_text'):
        lines.append(context['top_matches_text'].strip())
        lines.append('')

    channel = context.get('channel') or 'واتساپ'
    if channel == 'تماس':
        lines.append('لطفاً برای هماهنگی بازدید یا دریافت جزئیات بیشتر با من تماس بگیرید.')
    elif channel == 'پیامک':
        lines.append('برای هماهنگی بازدید لطفاً تماس بگیرید.')
    else:
        lines.append(
            'برای هماهنگی بازدید یا پرسش درباره هر ملک، '
            'می‌توانید از لینک‌های بالا جزئیات را ببینید و با من در ارتباط باشید.'
        )
    lines.append('')
    lines.append(_closing(context))
    return '\n'.join(lines).strip()


def _followup_message(context: Dict[str, Any]) -> str:
    lines = [_greeting(context), '']
    areas = (context.get('areas') or '').strip()
    customer_type = (context.get('customer_type') or '').strip()
    status = (context.get('status') or '').strip()

    if customer_type and areas:
        lines.append(
            f'درخواست {customer_type} شما در محدوده {areas} در وضعیت «{status or "پیگیری"}» '
            'همچنان در اولویت پیگیری من است.'
        )
    elif areas:
        lines.append(f'درخواست شما برای منطقه {areas} را با دقت پیگیری می‌کنم.')
    else:
        lines.append('درخواست شما را پیگیری می‌کنم و به‌محض یافتن گزینه مناسب اطلاع می‌دهم.')

    activities = (context.get('recent_activities') or '').strip()
    if activities and activities != '—':
        lines.append('')
        lines.append('آخرین پیگیری‌های ثبت‌شده:')
        lines.append(activities)

    lines.append('')
    lines.append('در صورت تمایل برای هماهنگی بازدید یا به‌روزرسانی نیازمندی‌ها در خدمتم.')
    lines.append('')
    lines.append(_closing(context))
    return '\n'.join(lines).strip()
