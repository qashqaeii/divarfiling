"""تبدیل عبارت خام فارسی date_text/time_text به datetime — منبع حقیقت Django."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

import jdatetime

from workspace.services.jalali_input import PERSIAN_WEEKDAYS, _normalize_digits, to_persian_digits

TIME_OF_DAY_DEFAULTS = {
    'صبح': time(9, 0),
    'بامداد': time(6, 0),
    'ظهر': time(12, 0),
    'عصر': time(16, 0),
    'غروب': time(18, 0),
    'شب': time(20, 0),
    'شب‌ها': time(20, 0),
}

_AFTERNOON_EVENING_KEYWORDS = frozenset({'عصر', 'غروب', 'شب', 'شب‌ها'})

_WEEKDAY_MAP = {name: idx for idx, name in enumerate(PERSIAN_WEEKDAYS)}

_WORD_HOUR = {
    'یک': 1,
    'دو': 2,
    'سه': 3,
    'چهار': 4,
    'پنج': 5,
    'شش': 6,
    'هفت': 7,
    'هشت': 8,
    'نه': 9,
    'ده': 10,
    'یازده': 11,
    'دوازده': 12,
}


def _local_now(tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name or 'Asia/Tehran')
    return datetime.now(tz)


def _parse_clock(text: str) -> Optional[time]:
    s = _normalize_digits((text or '').strip()).lower()
    s = s.replace('‌', ' ')
    if not s:
        return None
    for keyword, default_time in TIME_OF_DAY_DEFAULTS.items():
        if keyword in s:
            hour_match = re.search(r'ساعت\s*(\d{1,2})', s)
            if hour_match:
                hour = int(hour_match.group(1))
                if hour <= 11 and keyword in _AFTERNOON_EVENING_KEYWORDS:
                    hour += 12
                elif hour <= 12 and 'شب' in s and hour < 12:
                    hour += 12
                return time(hour, 0)
            minute_match = re.search(r'(\d{1,2})\s*:\s*(\d{2})', s)
            if minute_match:
                return time(int(minute_match.group(1)), int(minute_match.group(2)))
            return default_time
    m = re.search(r'ساعت\s+([^\s:]+)(?:\s*:\s*(\d{2}))?', s)
    if m:
        raw_h = (m.group(1) or '').strip()
        minute = int(m.group(2) or 0)
        if raw_h in _WORD_HOUR:
            hour = _WORD_HOUR[raw_h]
        elif re.fullmatch(r'\d{1,2}', raw_h):
            hour = int(raw_h)
        else:
            return None
        if hour <= 12 and re.search(r'\bشب\b', s) and hour < 12:
            hour += 12
        return time(hour, minute)
    m = re.fullmatch(r'(\d{1,2})(?:\s*:\s*(\d{2}))?', s)
    if m:
        return time(int(m.group(1)), int(m.group(2) or 0))
    return None


def _resolve_relative_date(date_text: str, now_local: datetime) -> Optional[date]:
    s = _normalize_digits((date_text or '').strip()).replace('‌', ' ')
    if not s:
        return None
    base = now_local.date()
    if 'امروز' in s:
        return base
    if 'پس فردا' in s or 'پس‌فردا' in s or 'پسفردا' in s:
        return base + timedelta(days=2)
    if 'فردا' in s:
        return base + timedelta(days=1)
    if 'دیروز' in s:
        return base - timedelta(days=1)

    next_week = 'بعد' in s or 'آینده' in s or 'اینده' in s
    for name, weekday_idx in _WEEKDAY_MAP.items():
        if name in s:
            jtoday = jdatetime.date.fromgregorian(date=base)
            current_idx = jtoday.weekday()
            delta = (weekday_idx - current_idx) % 7
            if next_week and delta == 0:
                delta = 7
            return base + timedelta(days=delta)
    return None


def parse_due_datetime(
    *,
    date_text: Optional[str],
    time_text: Optional[str],
    tz_name: str = 'Asia/Tehran',
    now: Optional[datetime] = None,
) -> Tuple[Optional[datetime], str]:
    """برگشت (due_at aware, error_code)."""
    now_local = now or _local_now(tz_name)
    tz = now_local.tzinfo or ZoneInfo(tz_name)
    target_date = _resolve_relative_date(date_text or '', now_local)
    if not target_date and (date_text or '').strip():
        return None, 'invalid_date'
    if not target_date:
        target_date = now_local.date()

    clock = _parse_clock(time_text or '')
    if not clock and not (time_text or '').strip():
        clock = _parse_clock(date_text or '')
    if not clock and (time_text or '').strip():
        return None, 'invalid_time'
    if not clock:
        clock = time(9, 0)

    naive = datetime.combine(target_date, clock)
    due_at = naive.replace(tzinfo=tz)
    if due_at <= now_local:
        return None, 'past_datetime'
    return due_at, ''


def format_due_display(due_at: datetime, tz_name: str = 'Asia/Tehran') -> str:
    tz = ZoneInfo(tz_name or 'Asia/Tehran')
    local = due_at.astimezone(tz)
    now_local = datetime.now(tz)
    day_label = ''
    if local.date() == now_local.date():
        day_label = 'امروز'
    elif local.date() == (now_local + timedelta(days=1)).date():
        day_label = 'فردا'
    elif local.date() == (now_local + timedelta(days=2)).date():
        day_label = 'پس‌فردا'
    else:
        j = jdatetime.date.fromgregorian(date=local.date())
        month_names = [
            'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
            'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
        ]
        day_label = f'{to_persian_digits(j.day)} {month_names[j.month - 1]}'
    time_part = to_persian_digits(local.strftime('%H:%M'))
    return f'{day_label}، {time_part}'
