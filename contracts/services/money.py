"""نمایش مبلغ — تومان/ریال و حروف."""
from __future__ import annotations

from typing import Any, Optional


def parse_toman_amount(value: Any) -> Optional[int]:
    if value is None or value == '':
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = str(value).replace(',', '').strip()
    if not s:
        return None
    if not s.isdigit():
        return None
    return int(s)


def toman_to_rial(toman: Optional[int]) -> Optional[int]:
    if toman is None:
        return None
    return toman * 10


def format_toman(value: Any) -> str:
    amount = parse_toman_amount(value)
    if amount is None:
        return '—'
    return f'{amount:,} تومان'


def format_rial(value: Any) -> str:
    amount = parse_toman_amount(value)
    if amount is None:
        return '—'
    return f'{toman_to_rial(amount):,} ریال'


def amount_display_block(value: Any) -> dict:
    """برای PDF/Renderer — تومان + ریال + حروف."""
    toman = parse_toman_amount(value)
    if toman is None:
        return {'toman': '', 'rial': '', 'words': ''}
    return {
        'toman': format_toman(toman),
        'rial': format_rial(toman),
        'words': _toman_words(toman),
    }


def _toman_words_chunk(amount: int) -> str:
    """تبدیل ۰ تا ۹۹۹ به حروف فارسی."""
    if amount <= 0:
        return ''
    if amount >= 1000:
        raise ValueError(f'_toman_words_chunk expects 0-999, got {amount}')
    teens = (
        'ده', 'یازده', 'دوازده', 'سیزده', 'چهارده', 'پانزده',
        'شانزده', 'هفده', 'هجده', 'نوزده',
    )
    units = ('', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه')
    tens = ('', 'ده', 'بیست', 'سی', 'چهل', 'پنجاه', 'شصت', 'هفتاد', 'هشتاد', 'نود')
    hundreds = (
        '', 'یکصد', 'دویست', 'سیصد', 'چهارصد', 'پانصد',
        'ششصد', 'هفتصد', 'هشتصد', 'نهصد',
    )
    if amount < 10:
        return units[amount]
    if amount < 20:
        return teens[amount - 10]
    if amount < 100:
        unit, ten = amount % 10, amount // 10
        part = tens[ten]
        if unit:
            part = f'{part} و {units[unit]}'
        return part
    hundred, rest = amount // 100, amount % 100
    head = hundreds[hundred]
    if rest:
        head = f'{head} و {_toman_words_chunk(rest)}'
    return head


def _toman_words(amount: int) -> str:
    """تبدیل مبلغ تومان به حروف — برای نمایش قرارداد."""
    if amount <= 0:
        return ''
    if amount < 1_000:
        return f'{_toman_words_chunk(amount)} تومان'

    for scale, label in (
        (1_000_000_000, 'میلیارد'),
        (1_000_000, 'میلیون'),
        (1_000, 'هزار'),
    ):
        if amount >= scale:
            quotient, remainder = divmod(amount, scale)
            if quotient >= 1_000:
                head = _toman_words(quotient).replace(' تومان', '')
            else:
                head = _toman_words_chunk(quotient)
            phrase = f'{head} {label}'
            if remainder:
                tail = _toman_words(remainder).replace(' تومان', '')
                return f'{phrase} و {tail} تومان'
            return f'{phrase} تومان'

    return f'{_toman_words_chunk(amount)} تومان'
