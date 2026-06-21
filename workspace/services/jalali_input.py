"""تبدیل ورودی تاریخ شمسی به میلادی برای فرم‌ها."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional, Union

import jdatetime

_FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')


def _normalize_digits(value: str) -> str:
    return (value or '').strip().translate(_FA_DIGITS)


def format_jalali_date(value: Union[date, datetime, None]) -> str:
    if not value:
        return ''
    d = value.date() if isinstance(value, datetime) else value
    j = jdatetime.date.fromgregorian(date=d)
    return j.strftime('%Y/%m/%d')


_EN_DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def to_persian_digits(value) -> str:
    """تبدیل اعداد لاتین به فارسی."""
    return str(value).translate(_EN_DIGITS)


PERSIAN_MONTHS = [
    'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
]

PERSIAN_WEEKDAYS = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه']


def format_jalali_today_label() -> str:
    """برچسب تاریخ امروز — مثال: سه‌شنبه، ۲۸ خرداد ۱۴۰۴"""
    today = jdatetime.date.today()
    # jdatetime.weekday(): شنبه=۰ … جمعه=۶ (همان ترتیب PERSIAN_WEEKDAYS)
    weekday = PERSIAN_WEEKDAYS[today.weekday()]
    month = PERSIAN_MONTHS[today.month - 1]
    return f'{weekday}، {to_persian_digits(today.day)} {month} {to_persian_digits(today.year)}'


def format_jalali_datetime(value: Union[date, datetime, None]) -> str:
    if not value:
        return ''
    if isinstance(value, datetime):
        j = jdatetime.datetime.fromgregorian(datetime=value)
        if j.hour or j.minute:
            return j.strftime('%Y/%m/%d %H:%M')
    d = value.date() if isinstance(value, datetime) else value
    j = jdatetime.date.fromgregorian(date=d)
    return j.strftime('%Y/%m/%d')


def parse_jalali_date_string(value: str) -> Optional[date]:
    s = _normalize_digits(value)
    if not s or s in ('-', '—'):
        return None
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
        try:
            return datetime.strptime(s, '%Y-%m-%d').date()
        except ValueError:
            pass
    s = s.replace('-', '/').split(' ')[0]
    for fmt in ('%Y/%m/%d',):
        try:
            j = jdatetime.datetime.strptime(s, fmt)
            g = j.togregorian()
            return date(g.year, g.month, g.day)
        except ValueError:
            continue
    return None


def parse_jalali_datetime_string(value: str) -> Optional[datetime]:
    s = _normalize_digits(value)
    if not s or s in ('-', '—'):
        return None
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', s):
        try:
            return datetime.strptime(s, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass
    if re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', s):
        try:
            return datetime.strptime(s, '%Y-%m-%d %H:%M')
        except ValueError:
            pass
    parts = s.replace('-', '/').split(' ', 1)
    date_part = parts[0]
    time_part = (parts[1] if len(parts) > 1 else '00:00')[:8]
    for fmt in ('%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M'):
        try:
            j = jdatetime.datetime.strptime(f'{date_part} {time_part}', fmt)
            g = j.togregorian()
            return datetime(g.year, g.month, g.day, g.hour, g.minute, g.second)
        except ValueError:
            continue
    d = parse_jalali_date_string(date_part)
    return datetime.combine(d, datetime.min.time()) if d else None
