"""تبدیل ورودی تاریخ شمسی به میلادی برای فرم‌ها."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional, Union

import jdatetime

_FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')


def jalali_is_leap_year(year: int) -> bool:
    """بررسی سال کبیسه شمسی — jdatetime.date.isleap متد نمونه است نه classmethod."""
    return jdatetime.date(int(year), 1, 1).isleap()


def jalali_esfand_days(year: int) -> int:
    return 30 if jalali_is_leap_year(year) else 29


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


def jalali_month_bounds(reference: Union[date, datetime, None] = None) -> tuple[date, date]:
    """اول و آخر ماه شمسی (برگشت تاریخ میلادی)."""
    if reference:
        ref = reference.date() if isinstance(reference, datetime) else reference
        jtoday = jdatetime.date.fromgregorian(date=ref)
    else:
        jtoday = jdatetime.date.today()
    jstart = jdatetime.date(jtoday.year, jtoday.month, 1)
    month_days = jdatetime.j_days_in_month[jtoday.month - 1]
    if jtoday.month == 12 and jalali_is_leap_year(jtoday.year):
        month_days = 30
    jend = jdatetime.date(jtoday.year, jtoday.month, month_days)
    g_start = jstart.togregorian()
    g_end = jend.togregorian()
    return date(g_start.year, g_start.month, g_start.day), date(g_end.year, g_end.month, g_end.day)


def jalali_month_bounds_display(reference: Union[date, datetime, None] = None) -> tuple[str, str]:
    """برچسب شمسی اول و آخر ماه جاری برای فرم‌ها."""
    start, end = jalali_month_bounds(reference)
    return format_jalali_date(start), format_jalali_date(end)


def jalali_quarter_ahead_display(reference: Union[date, datetime, None] = None) -> tuple[str, str]:
    """از امروز تا پایان ماه سوم شمسی جلوتر."""
    if reference:
        ref = reference.date() if isinstance(reference, datetime) else reference
        jtoday = jdatetime.date.fromgregorian(date=ref)
    else:
        jtoday = jdatetime.date.today()
    jend_month = jtoday.month + 2
    jend_year = jtoday.year
    while jend_month > 12:
        jend_month -= 12
        jend_year += 1
    month_days = jdatetime.j_days_in_month[jend_month - 1]
    if jend_month == 12 and jalali_is_leap_year(jend_year):
        month_days = 30
    jend = jdatetime.date(jend_year, jend_month, month_days)
    g_start = jtoday.togregorian()
    g_end = jend.togregorian()
    return format_jalali_date(g_start), format_jalali_date(g_end)


def parse_goal_period_strings(start_raw: str, end_raw: str) -> tuple[date, date]:
    """تبدیل بازه هدف تیم از ورودی شمسی به میلادی."""
    start = parse_jalali_date_string((start_raw or '').strip())
    end = parse_jalali_date_string((end_raw or '').strip())
    if not start or not end:
        raise ValueError('تاریخ شمسی نامعتبر است. مثال: ۱۴۰۴/۰۶/۱۵')
    if end < start:
        raise ValueError('پایان دوره باید بعد از شروع دوره باشد')
    return start, end
