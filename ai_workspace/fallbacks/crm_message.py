"""Fallback پیام CRM — rule-based حرفه‌ای، محاوره‌ای و دقیق با لینک صفحه عمومی."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ai_workspace.constants import normalize_crm_tone

# دلایل منفی/خنثی — برای پیام مشتری نمایش داده نمی‌شوند
_SKIP_REASON_MARKERS = (
    'متفاوت',
    'کمتر از',
    'بیشتر از',
    'بالای بودجه',
)


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


def _first_name(name: str) -> str:
    parts = (name or '').strip().split()
    return parts[0] if parts else ''


def _greeting(context: Dict[str, Any]) -> str:
    name = (context.get('name') or '').strip()
    tone = normalize_crm_tone(context.get('tone'))
    display = name or 'مشتری'
    first = _first_name(name) if name else ''

    if tone == 'صمیمی':
        warm = first or display
        return f'سلام {warm} عزیز، وقتتون بخیر'
    if tone == 'کوتاه':
        return f'سلام {first or display}،'
    if tone == 'مشاورانه':
        return f'سلام {display}، وقت بخیر'
    if tone == 'پیگیری':
        return f'سلام {first or display}، امیدوارم حالتون خوب باشه'
    # رسمی
    if name:
        return f'سلام، وقت بخیر؛ خدمت {display}'
    return 'سلام، وقت بخیر'


def _closing(context: Dict[str, Any]) -> str:
    tone = normalize_crm_tone(context.get('tone'))
    closings = {
        'رسمی': 'با احترام و آمادگی کامل برای هماهنگی',
        'صمیمی': 'هر سوالی بود، راحت پیام بدید — در خدمتم',
        'کوتاه': 'در خدمتم',
        'مشاورانه': 'برای مقایسه دقیق‌تر و انتخاب بهترین گزینه، کنار شما هستم',
        'پیگیری': 'هر زمان آماده بودید، با خیال راحت خبر بدید',
    }
    return closings.get(tone, closings['رسمی'])


def _need_phrase(context: Dict[str, Any]) -> str:
    """عبارت کوتاه و دقیق از نیاز مشتری — بدون تکرار خشک فیلدها."""
    customer_type = (context.get('customer_type') or '').strip()
    areas = (context.get('areas') or '').strip()
    budget = (context.get('budget_range') or '').strip()
    prop_type = (context.get('property_type') or '').strip()

    bits: List[str] = []
    if customer_type:
        bits.append(f'درخواست {customer_type}')
    if prop_type:
        bits.append(f'نوع {prop_type}')
    if areas:
        bits.append(f'محدوده {areas}')
    if budget:
        bits.append(f'بودجه {budget}')
    return '، '.join(bits)


def _intro_line(context: Dict[str, Any], match_count: int) -> str:
    tone = normalize_crm_tone(context.get('tone'))
    need = _need_phrase(context)
    n = match_count

    if tone == 'کوتاه':
        if need:
            return f'با توجه به {need} — {n} پیشنهاد:' if n else f'با توجه به {need}:'
        return f'{n} پیشنهاد مناسب:' if n else 'پیشنهادها:'

    if tone == 'صمیمی':
        if need:
            count_bit = f'{n} گزینه' if n else 'چند گزینه'
            return (
                f'با توجه به {need}، {count_bit} خوب پیدا کردم '
                'که به درخواستتون نزدیکه — جزئیات رو براتون می‌فرستم:'
            )
        count_bit = f'{n} گزینه' if n else 'چند گزینه'
        return f'{count_bit} مناسب پیدا کردم که فکر می‌کنم براتون جالب باشه:'

    if tone == 'مشاورانه':
        if need:
            count_bit = f'{n} گزینه' if n else 'گزینه‌هایی'
            return (
                f'با در نظر گرفتن {need}، این {count_bit} را '
                'بر اساس بالاترین هم‌خوانی با پروفایل شما پیشنهاد می‌کنم:'
            )
        count_bit = f'{n} گزینه' if n else 'گزینه‌هایی'
        return f'این {count_bit} را با اولویت تطابق سیستم برای شما کنار هم گذاشته‌ام:'

    if tone == 'پیگیری':
        if need:
            count_bit = f'{n} پیشنهاد' if n else 'پیشنهادهایی'
            return (
                f'پیرو پیگیری درخواستتان ({need})، '
                f'{count_bit} هنوز برای بررسی شما آماده است:'
            )
        count_bit = f'{n} پیشنهاد' if n else 'پیشنهادهایی'
        return f'{count_bit} زیر هنوز باز است و ارزش یک نگاه کوتاه را دارد:'

    # رسمی
    if need:
        if n:
            return (
                f'با توجه به {need}، {n} پیشنهاد با بالاترین تطابق سیستم '
                'را خدمتتان معرفی می‌کنم:'
            )
        return f'با توجه به {need}، پیشنهادهای زیر را خدمتتان معرفی می‌کنم:'
    if n:
        return f'{n} پیشنهاد با بالاترین تطابق سیستم را خدمتتان معرفی می‌کنم:'
    return 'پیشنهادهای زیر بیشترین هم‌خوانی را با درخواست شما دارند:'


def _cta_line(context: Dict[str, Any]) -> str:
    channel = context.get('channel') or 'واتساپ'
    tone = normalize_crm_tone(context.get('tone'))

    if channel == 'تماس':
        if tone == 'کوتاه':
            return 'برای بازدید تماس بگیرید.'
        if tone == 'صمیمی':
            return 'اگر خواستید بازدید بذاریم، کافیه تماس بگیرید تا هماهنگ کنیم.'
        if tone == 'پیگیری':
            return 'هر وقت آماده بودید، برای هماهنگی بازدید تماس بگیرید.'
        return 'لطفاً برای هماهنگی بازدید یا دریافت جزئیات بیشتر با من تماس بگیرید.'

    if channel == 'پیامک':
        if tone == 'کوتاه':
            return 'برای بازدید تماس بگیرید.'
        return 'برای هماهنگی بازدید لطفاً تماس بگیرید.'

    ctas = {
        'رسمی': (
            'می‌توانید از لینک هر ملک جزئیات کامل را ببینید؛ '
            'برای هماهنگی بازدید یا پرسش، در ارتباط باشید.'
        ),
        'صمیمی': (
            'لینک هر کدوم رو باز کنید و جزئیات رو ببینید؛ '
            'هر کدوم بیشتر به دلتون نشست، بگید تا بازدید رو هماهنگ کنیم.'
        ),
        'کوتاه': 'جزئیات در لینک‌هاست؛ برای بازدید خبر بدید.',
        'مشاورانه': (
            'پیشنهاد می‌کنم لینک هر گزینه را ببینید تا با هم '
            'نقاط قوت و ضعف را مقایسه کنیم و بهترین انتخاب را داشته باشیم.'
        ),
        'پیگیری': (
            'هر وقت فرصت کوتاهی داشتید لینک‌ها را ببینید؛ '
            'برای هماهنگی بازدید بدون عجله در خدمتم.'
        ),
    }
    return ctas.get(tone, ctas['رسمی'])


def _client_reasons(match: Dict[str, Any], limit: int = 2) -> List[str]:
    raw = match.get('reasons') or []
    out: List[str] = []
    for reason in raw:
        text = (reason or '').strip()
        if not text:
            continue
        if any(marker in text for marker in _SKIP_REASON_MARKERS):
            continue
        if text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _spec_bits(match: Dict[str, Any]) -> List[str]:
    bits: List[str] = []
    hood = '، '.join(
        p for p in (match.get('neighborhood'), match.get('city')) if p
    )
    if hood:
        bits.append(hood)
    price = (match.get('price_label') or '').strip()
    if price:
        bits.append(price)
    area = match.get('area')
    if area not in (None, '', 0):
        try:
            bits.append(f'{int(round(float(area)))} متر')
        except (TypeError, ValueError):
            bits.append(f'{area} متر')
    rooms = (match.get('rooms') or '').strip()
    if rooms:
        if 'خواب' in rooms or 'اتاق' in rooms:
            bits.append(rooms)
        else:
            bits.append(f'{rooms} خواب')
    return bits


def _reason_label(tone: str) -> str:
    if tone == 'صمیمی':
        return 'چرا مناسبه'
    if tone == 'مشاورانه':
        return 'نکته تطابق'
    if tone == 'پیگیری':
        return 'نقطه قوت'
    return 'دلیل پیشنهاد'


def _score_line(tone: str, score: Optional[float]) -> str:
    if score is None:
        return ''
    try:
        value = int(round(float(score)))
    except (TypeError, ValueError):
        return ''
    if tone == 'کوتاه':
        return ''
    if tone == 'صمیمی':
        return f'هم‌خوانی با درخواست شما: {value}٪'
    if tone == 'پیگیری':
        return f'امتیاز سیستم: {value}٪'
    return f'امتیاز سیستم: {value}٪'


def _format_match_body(index: int, match: Dict[str, Any], tone: str) -> str:
    title = (match.get('title') or 'ملک').strip()
    deal = (match.get('deal_mode') or '').strip()
    public_url = (match.get('public_url') or '').strip()
    score = match.get('score')

    head = f'{index}. {title}'
    if deal:
        head += f' ({deal})'

    lines = [head]

    specs = _spec_bits(match)
    if specs:
        lines.append('   ' + ' · '.join(specs))

    if tone != 'کوتاه':
        reasons = _client_reasons(match, limit=2 if tone == 'مشاورانه' else 2)
        if reasons:
            lines.append(f'   {_reason_label(tone)}: {" · ".join(reasons)}')

    score_text = _score_line(tone, score)
    if score_text:
        # برای سازگاری با تست‌های قبلی و وضوح مشتری
        if tone in {'رسمی', 'مشاورانه'}:
            try:
                value = int(round(float(score)))
            except (TypeError, ValueError):
                value = None
            if value is not None:
                lines.append(f'   امتیاز تطابق سیستم: {value}٪')
            else:
                lines.append(f'   {score_text}')
        else:
            lines.append(f'   {score_text}')

    if public_url:
        if tone == 'صمیمی':
            lines.append(f'   جزئیات کامل: {public_url}')
        elif tone == 'کوتاه':
            lines.append(f'   {public_url}')
        else:
            lines.append(f'   مشاهده جزئیات: {public_url}')

    return '\n'.join(lines)


def _matches_message(
    context: Dict[str, Any],
    matches: List[Dict[str, Any]],
    top_matches_text: str = '',
) -> str:
    tone = normalize_crm_tone(context.get('tone'))
    match_count = _effective_match_count(matches, top_matches_text)

    lines = [_greeting(context), '', _intro_line(context, match_count), '']

    if matches:
        for i, match in enumerate(matches[:2], start=1):
            lines.append(_format_match_body(i, match, tone))
            lines.append('')
    elif top_matches_text:
        lines.append(top_matches_text.strip())
        lines.append('')

    lines.append(_cta_line(context))
    if tone != 'کوتاه':
        lines.append('')
        lines.append(_closing(context))
    else:
        lines.append(_closing(context))
    return '\n'.join(lines).strip()


def _followup_status_line(context: Dict[str, Any]) -> str:
    areas = (context.get('areas') or '').strip()
    customer_type = (context.get('customer_type') or '').strip()
    status = (context.get('status') or '').strip()
    prop_type = (context.get('property_type') or '').strip()
    budget = (context.get('budget_range') or '').strip()
    tone = normalize_crm_tone(context.get('tone'))
    status_label = status or 'پیگیری'

    type_bit = f' ({prop_type})' if prop_type else ''
    budget_bit = f' با بودجه {budget}' if budget else ''

    if customer_type and areas:
        bodies = {
            'رسمی': (
                f'درخواست {customer_type}{type_bit} شما در محدوده {areas}{budget_bit} '
                f'در وضعیت «{status_label}» همچنان در اولویت پیگیری من است '
                'و به‌محض یافتن گزینه مناسب اطلاع می‌دهم.'
            ),
            'صمیمی': (
                f'درخواست {customer_type}{type_bit}تون برای {areas}{budget_bit} رو '
                f'با دقت پیگیری می‌کنم (وضعیت: {status_label})؛ '
                'به‌محض پیدا شدن گزینه خوب خبرتون می‌کنم.'
            ),
            'کوتاه': (
                f'درخواست {customer_type} در {areas} — وضعیت: {status_label}.'
            ),
            'مشاورانه': (
                f'با توجه به درخواست {customer_type}{type_bit} شما در {areas}{budget_bit}، '
                f'وضعیت فعلی «{status_label}» است و گزینه‌های مناسب را بررسی می‌کنم '
                'تا پیشنهاد دقیق‌تری داشته باشیم.'
            ),
            'پیگیری': (
                f'درخواست {customer_type}{type_bit} شما برای {areas}{budget_bit} '
                f'همچنان باز است (وضعیت: {status_label})؛ '
                'هر وقت آماده بودید در خدمتم.'
            ),
        }
        return bodies[tone]

    if areas:
        bodies = {
            'رسمی': (
                f'درخواست شما برای منطقه {areas}{budget_bit} را با دقت پیگیری می‌کنم '
                'و به‌محض یافتن گزینه مناسب اطلاع می‌دهم.'
            ),
            'صمیمی': (
                f'درخواستتون برای {areas}{budget_bit} رو پیگیری می‌کنم؛ '
                'به‌محض گزینه خوب، خبر می‌دم.'
            ),
            'کوتاه': f'پیگیری {areas} — در جریان.',
            'مشاورانه': (
                f'نیازمندی شما در محدوده {areas}{budget_bit} را بررسی می‌کنم '
                'و مناسب‌ترین گزینه را با جزئیات پیشنهاد می‌دهم.'
            ),
            'پیگیری': (
                f'درخواست شما برای {areas}{budget_bit} هنوز باز است؛ '
                'هر زمان خواستید هماهنگ می‌کنیم.'
            ),
        }
        return bodies[tone]

    bodies = {
        'رسمی': (
            'درخواست شما را پیگیری می‌کنم و به‌محض یافتن گزینه مناسب '
            'با جزئیات اطلاع می‌دهم.'
        ),
        'صمیمی': (
            'درخواستتون رو پیگیری می‌کنم و به‌محض پیدا کردن گزینه خوب خبر می‌دم.'
        ),
        'کوتاه': 'در حال پیگیری — به‌محض یافتن گزینه اطلاع می‌دهم.',
        'مشاورانه': (
            'درخواست شما را بررسی می‌کنم و به‌محض یافتن گزینه مناسب '
            'با جزئیات پیشنهاد می‌دهم.'
        ),
        'پیگیری': (
            'هر وقت آماده بودید، درخواست شما همچنان در صف پیگیری من است '
            'و بدون فشار در خدمتم.'
        ),
    }
    return bodies[tone]


def _followup_invitation(context: Dict[str, Any]) -> str:
    tone = normalize_crm_tone(context.get('tone'))
    channel = context.get('channel') or 'واتساپ'

    if channel == 'تماس':
        if tone == 'کوتاه':
            return 'برای به‌روزرسانی تماس بگیرید.'
        return 'در صورت تغییر نیازمندی‌ها یا آمادگی برای بازدید، لطفاً تماس بگیرید.'

    invitations = {
        'رسمی': (
            'در صورت تمایل برای هماهنگی بازدید یا به‌روزرسانی نیازمندی‌ها، '
            'در خدمتم.'
        ),
        'صمیمی': (
            'اگر چیزی از نیازمندی‌ها عوض شده یا خواستید بازدید بذاریم، '
            'راحت خبر بدید.'
        ),
        'کوتاه': 'برای بازدید یا به‌روزرسانی در خدمتم.',
        'مشاورانه': (
            'اگر نیازمندی‌ها تغییر کرده، بگویید تا پیشنهادها را دقیق‌تر تنظیم کنم.'
        ),
        'پیگیری': (
            'هر زمان مناسب بود برای هماهنگی بازدید یا به‌روزرسانی در ارتباط باشیم.'
        ),
    }
    return invitations[tone]


def _followup_message(context: Dict[str, Any]) -> str:
    tone = normalize_crm_tone(context.get('tone'))
    lines = [_greeting(context), '', _followup_status_line(context)]

    activities = (context.get('recent_activities') or '').strip()
    if activities and activities != '—':
        lines.append('')
        if tone == 'صمیمی':
            lines.append('آخرین پیگیری‌هایی که ثبت شده:')
        elif tone == 'کوتاه':
            lines.append('آخرین پیگیری:')
        else:
            lines.append('آخرین پیگیری‌های ثبت‌شده:')
        lines.append(activities)

    lines.append('')
    lines.append(_followup_invitation(context))
    if tone != 'کوتاه':
        lines.append('')
        lines.append(_closing(context))
    else:
        lines.append(_closing(context))
    return '\n'.join(lines).strip()
