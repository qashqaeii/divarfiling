"""Fallback پیام CRM — rule-based حرفه‌ای با لینک صفحه عمومی."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from ai_workspace.constants import normalize_crm_tone


def build(context: Dict[str, Any]) -> str:
    matches = context.get('top_matches') or []
    top_matches_text = (context.get('top_matches_text') or '').strip()
    if matches or top_matches_text:
        return _matches_message(context, matches, top_matches_text)
    return _followup_message(context)


def _effective_match_count(
    matches: List[Dict[str, Any]],
    top_matches_text: str,
) -> int:
    if matches:
        return min(len(matches), 2)
    text = (top_matches_text or '').strip()
    if not text:
        return 0
    numbered = re.findall(r'^\d+\.', text, re.MULTILINE)
    return len(numbered) or 1


def _greeting(context: Dict[str, Any]) -> str:
    name = (context.get('name') or '').strip() or 'مشتری'
    tone = normalize_crm_tone(context.get('tone'))
    greetings = {
        'رسمی': f'سلام، وقت بخیر؛ خدمت {name}،',
        'صمیمی': f'سلام {name} عزیز،',
        'کوتاه': f'سلام {name}،',
        'مشاورانه': f'سلام {name}،',
        'پیگیری': f'سلام {name}،',
    }
    return greetings.get(tone, greetings['رسمی'])


def _closing(context: Dict[str, Any]) -> str:
    tone = normalize_crm_tone(context.get('tone'))
    closings = {
        'رسمی': 'با احترام',
        'صمیمی': 'هر وقت سوالی داشتید در خدمتم.',
        'کوتاه': 'در خدمتم.',
        'مشاورانه': 'برای بررسی دقیق‌تر هر گزینه در کنار شما هستم.',
        'پیگیری': 'هر زمان آماده بودید، با خیال راحت اطلاع دهید.',
    }
    return closings.get(tone, closings['رسمی'])


def _intro_line(context: Dict[str, Any], match_count: int, intro_bits: List[str]) -> str:
    tone = normalize_crm_tone(context.get('tone'))
    if not intro_bits:
        defaults = {
            'رسمی': 'پیشنهادهای زیر بیشترین تطابق را با درخواست شما دارند:',
            'صمیمی': 'چند گزینه خوب پیدا کردم که به درخواستتون می‌خوره:',
            'کوتاه': f'{match_count or ""} پیشنهاد مناسب:'.strip(),
            'مشاورانه': 'با توجه به نیاز شما، این گزینه‌ها را پیشنهاد می‌کنم:',
            'پیگیری': 'گزینه‌های زیر هنوز برای شما باز است:',
        }
        return defaults.get(tone, defaults['رسمی'])

    prefix = 'با توجه به ' + ' '.join(intro_bits) + '، '
    if tone == 'کوتاه':
        return prefix + (f'{match_count} پیشنهاد:' if match_count else 'پیشنهادها:')
    if tone == 'صمیمی':
        count_bit = f'{match_count} پیشنهاد' if match_count else 'پیشنهادها'
        return prefix + f'{count_bit} مناسب رو خدمتتون معرفی می‌کنم:'
    if tone == 'مشاورانه':
        count_bit = f'{match_count} گزینه' if match_count else 'گزینه‌های'
        return prefix + f'این {count_bit} را با اولویت تطابق سیستم پیشنهاد می‌کنم:'
    if tone == 'پیگیری':
        count_bit = f'{match_count} پیشنهاد' if match_count else 'پیشنهادهای'
        return prefix + f'{count_bit} زیر هنوز برای بررسی شما آماده است:'
    if match_count:
        return prefix + f'{match_count} پیشنهاد با بالاترین تطابق سیستم را خدمتتان معرفی می‌کنم:'
    return prefix + 'پیشنهادهای زیر را با بالاترین تطابق سیستم خدمتتان معرفی می‌کنم:'


def _cta_line(context: Dict[str, Any]) -> str:
    channel = context.get('channel') or 'واتساپ'
    tone = normalize_crm_tone(context.get('tone'))
    if channel == 'تماس':
        if tone == 'کوتاه':
            return 'برای بازدید تماس بگیرید.'
        return 'لطفاً برای هماهنگی بازدید یا دریافت جزئیات بیشتر با من تماس بگیرید.'
    if channel == 'پیامک':
        return 'برای هماهنگی بازدید لطفاً تماس بگیرید.'
    ctas = {
        'رسمی': (
            'برای هماهنگی بازدید یا پرسش درباره هر ملک، '
            'می‌توانید از لینک‌های بالا جزئیات را ببینید و با من در ارتباط باشید.'
        ),
        'صمیمی': 'برای بازدید یا سوال درباره هر کدوم، از لینک‌ها جزئیات رو ببینید و پیام بدید.',
        'کوتاه': 'جزئیات در لینک‌هاست؛ برای بازدید خبر بدید.',
        'مشاورانه': 'پیشنهاد می‌کنم لینک هر ملک را ببینید تا بتوانیم بهترین گزینه را انتخاب کنیم.',
        'پیگیری': 'هر وقت فرصت کردید لینک‌ها را ببینید؛ برای هماهنگی بازدید در خدمتم.',
    }
    return ctas.get(tone, ctas['رسمی'])


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


def _matches_message(
    context: Dict[str, Any],
    matches: List[Dict[str, Any]],
    top_matches_text: str = '',
) -> str:
    lines = [_greeting(context), '']

    areas = (context.get('areas') or '').strip()
    customer_type = (context.get('customer_type') or '').strip()
    budget = (context.get('budget_range') or '').strip()
    match_count = _effective_match_count(matches, top_matches_text)

    intro_bits = []
    if customer_type:
        intro_bits.append(f'درخواست {customer_type}')
    if areas:
        intro_bits.append(f'در مناطق {areas}')
    if budget:
        intro_bits.append(f'با بودجه {budget}')
    if intro_bits:
        lines.append(_intro_line(context, match_count, intro_bits))
    else:
        lines.append(_intro_line(context, match_count, []))
    lines.append('')

    if matches:
        for i, match in enumerate(matches[:2], start=1):
            lines.append(_format_match_body(i, match))
            lines.append('')
    elif top_matches_text:
        lines.append(top_matches_text.strip())
        lines.append('')

    lines.append(_cta_line(context))
    lines.append('')
    lines.append(_closing(context))
    return '\n'.join(lines).strip()


def _followup_status_line(context: Dict[str, Any]) -> str:
    areas = (context.get('areas') or '').strip()
    customer_type = (context.get('customer_type') or '').strip()
    status = (context.get('status') or '').strip()
    tone = normalize_crm_tone(context.get('tone'))
    status_label = status or 'پیگیری'

    if customer_type and areas:
        bodies = {
            'رسمی': (
                f'درخواست {customer_type} شما در محدوده {areas} در وضعیت «{status_label}» '
                'همچنان در اولویت پیگیری من است.'
            ),
            'صمیمی': (
                f'درخواست {customer_type}تون برای {areas} رو با دقت پیگیری می‌کنم '
                f'(وضعیت: {status_label}).'
            ),
            'کوتاه': f'درخواست {customer_type} در {areas} — وضعیت: {status_label}.',
            'مشاورانه': (
                f'با توجه به درخواست {customer_type} شما در {areas}، '
                f'وضعیت فعلی «{status_label}» است و گزینه‌های مناسب را بررسی می‌کنم.'
            ),
            'پیگیری': (
                f'درخواست {customer_type} شما برای {areas} همچنان باز است '
                f'(وضعیت: {status_label})؛ هر وقت آماده بودید در خدمتم.'
            ),
        }
        return bodies[tone]

    if areas:
        bodies = {
            'رسمی': f'درخواست شما برای منطقه {areas} را با دقت پیگیری می‌کنم.',
            'صمیمی': f'درخواستتون برای {areas} رو پیگیری می‌کنم.',
            'کوتاه': f'پیگیری {areas} — در جریان.',
            'مشاورانه': (
                f'نیازمندی شما در محدوده {areas} را بررسی می‌کنم '
                'و مناسب‌ترین گزینه را پیشنهاد می‌دهم.'
            ),
            'پیگیری': (
                f'درخواست شما برای {areas} هنوز باز است؛ '
                'هر زمان خواستید هماهنگ می‌کنیم.'
            ),
        }
        return bodies[tone]

    bodies = {
        'رسمی': 'درخواست شما را پیگیری می‌کنم و به‌محض یافتن گزینه مناسب اطلاع می‌دهم.',
        'صمیمی': 'درخواستتون رو پیگیری می‌کنم و به‌محض پیدا کردن گزینه خوب خبر می‌دم.',
        'کوتاه': 'در حال پیگیری — به‌محض یافتن گزینه اطلاع می‌دهم.',
        'مشاورانه': (
            'درخواست شما را بررسی می‌کنم و به‌محض یافتن گزینه مناسب '
            'با جزئیات پیشنهاد می‌دهم.'
        ),
        'پیگیری': 'هر وقت آماده بودید، درخواست شما همچنان در صف پیگیری من است.',
    }
    return bodies[tone]


def _followup_invitation(context: Dict[str, Any]) -> str:
    tone = normalize_crm_tone(context.get('tone'))
    invitations = {
        'رسمی': 'در صورت تمایل برای هماهنگی بازدید یا به‌روزرسانی نیازمندی‌ها در خدمتم.',
        'صمیمی': 'هر وقت خواستید برای بازدید یا به‌روزرسانی نیازمندی‌ها خبر بدید.',
        'کوتاه': 'برای بازدید یا به‌روزرسانی در خدمتم.',
        'مشاورانه': 'اگر نیازمندی‌ها تغییر کرده، بگویید تا پیشنهادها را دقیق‌تر تنظیم کنم.',
        'پیگیری': 'هر زمان مناسب بود برای هماهنگی بازدید یا به‌روزرسانی در ارتباط باشیم.',
    }
    return invitations[tone]


def _followup_message(context: Dict[str, Any]) -> str:
    lines = [_greeting(context), '']
    lines.append(_followup_status_line(context))

    activities = (context.get('recent_activities') or '').strip()
    if activities and activities != '—':
        lines.append('')
        lines.append('آخرین پیگیری‌های ثبت‌شده:')
        lines.append(activities)

    lines.append('')
    lines.append(_followup_invitation(context))
    lines.append('')
    lines.append(_closing(context))
    return '\n'.join(lines).strip()
