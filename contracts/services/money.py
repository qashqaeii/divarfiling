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


def _toman_words(amount: int) -> str:
    """تبدیل ساده به حروف — برای نمایش قرارداد."""
    if amount <= 0:
        return ''
    units = ['', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه']
    tens = ['', 'ده', 'بیست', 'سی', 'چهل', 'پنجاه', 'شصت', 'هفتاد', 'هشتاد', 'نود']
    if amount < 10:
        return f'{units[amount]} تومان'
    if amount < 100:
        u, t = amount % 10, amount // 10
        part = tens[t]
        if u:
            part = f'{part} و {units[u]}'
        return f'{part} تومان'
    if amount < 1_000:
        h, rest = amount // 100, amount % 100
        head = f'{units[h]}صد'
        if rest:
            head = f'{head} و {_toman_words(rest).replace(" تومان", "")}'
        return f'{head} تومان'
    if amount < 1_000_000:
        th, rest = amount // 1000, amount % 1000
        head = f'{_toman_words(th).replace(" تومان", "")} هزار'
        if rest:
            head = f'{head} و {_toman_words(rest).replace(" تومان", "")}'
        return f'{head} تومان'
    mil, rest = amount // 1_000_000, amount % 1_000_000
    head = f'{_toman_words(mil).replace(" تومان", "")} میلیون'
    if rest:
        head = f'{head} و {_toman_words(rest).replace(" تومان", "")}'
    return f'{head} تومان'
