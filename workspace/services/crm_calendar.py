"""تقویم CRM — شمسی (جلالی) با رویدادهای پیگیری، یادآور و بازدید."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

import jdatetime
from django.urls import reverse
from django.utils import timezone

from workspace.models import Customer, PropertyVisit
from workspace.services.crm_scope import customers_qs, reminders_qs
from workspace.services.jalali_input import PERSIAN_MONTHS, PERSIAN_WEEKDAYS, to_persian_digits


def _jkey(jd: jdatetime.date) -> str:
    return f'{jd.year}-{jd.month:02d}-{jd.day:02d}'


def _saturday_offset(jd: jdatetime.date) -> int:
    """شاخص روز هفته — شنبه=۰ در jdatetime."""
    return jd.weekday()


def _add_jday(jd: jdatetime.date, days: int) -> jdatetime.date:
    g = jd.togregorian() + timedelta(days=days)
    return jdatetime.date.fromgregorian(date=g)


def _prev_jmonth(jyear: int, jmonth: int) -> Tuple[int, int]:
    if jmonth == 1:
        return jyear - 1, 12
    return jyear, jmonth - 1


def _next_jmonth(jyear: int, jmonth: int) -> Tuple[int, int]:
    if jmonth == 12:
        return jyear + 1, 1
    return jyear, jmonth + 1


_J_MONTH_LENGTHS = (31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29)


def _jdays_in_month(jyear: int, jmonth: int) -> int:
    if jmonth == 12 and jdatetime.date(jyear, 1, 1).isleap():
        return 30
    return _J_MONTH_LENGTHS[jmonth - 1]


def get_calendar_month(user, jyear: int, jmonth: int) -> Dict[str, Any]:
    """تقویم ماه شمسی با گرید شنبه‌محور."""
    today_j = jdatetime.date.today()
    jyear = max(1300, min(jyear, 1500))
    jmonth = max(1, min(jmonth, 12))

    days_in_month = _jdays_in_month(jyear, jmonth)
    first_j = jdatetime.date(jyear, jmonth, 1)
    last_j = jdatetime.date(jyear, jmonth, days_in_month)
    start_g = first_j.togregorian()
    end_g = last_j.togregorian()

    events_by_jkey: Dict[str, List[Dict[str, Any]]] = {}

    def add_gregorian(gday: date, event: Dict[str, Any]) -> None:
        jd = jdatetime.date.fromgregorian(date=gday)
        if jd.year != jyear or jd.month != jmonth:
            return
        events_by_jkey.setdefault(_jkey(jd), []).append(event)

    for c in customers_qs(user).filter(
        next_follow_up__gte=start_g, next_follow_up__lte=end_g,
    ).only('id', 'name', 'next_follow_up', 'status'):
        add_gregorian(c.next_follow_up, {
            'type': 'followup',
            'label': f'پیگیری: {c.name}',
            'href': reverse('workspace:crm_detail', kwargs={'customer_id': c.id}),
        })

    for r in reminders_qs(user).filter(
        is_done=False,
        due_at__date__gte=start_g, due_at__date__lte=end_g,
    ).select_related('customer'):
        add_gregorian(r.due_at.date(), {
            'type': 'reminder',
            'label': r.title,
            'time': r.due_at.strftime('%H:%M'),
            'href': reverse('workspace:crm_reminders'),
        })

    for v in PropertyVisit.objects.filter(
        user=user, visit_date__gte=start_g, visit_date__lte=end_g,
    ).select_related('customer', 'property'):
        title = v.property.title if v.property else (v.listing_title or 'بازدید')
        add_gregorian(v.visit_date, {
            'type': 'visit',
            'label': f'بازدید: {title}',
            'outcome': v.outcome,
            'href': reverse('workspace:crm_detail', kwargs={'customer_id': v.customer_id}) + '?tab=visits',
        })

    offset = _saturday_offset(first_j)
    cursor_j = _add_jday(first_j, -offset)

    weeks: List[List[Dict[str, Any]]] = []
    for _ in range(6):
        week = []
        for _ in range(7):
            jd = cursor_j
            in_month = jd.year == jyear and jd.month == jmonth
            is_today = jd == today_j
            is_friday = jd.weekday() == 4
            events = events_by_jkey.get(_jkey(jd), []) if in_month else []
            week.append({
                'jyear': jd.year,
                'jmonth': jd.month,
                'jday': jd.day,
                'day_label': to_persian_digits(jd.day),
                'in_month': in_month,
                'is_today': is_today,
                'is_friday': is_friday,
                'events': events,
                'event_count': len(events),
                'event_count_label': to_persian_digits(len(events)) if events else '',
                'jkey': _jkey(jd),
            })
            cursor_j = _add_jday(cursor_j, 1)
        weeks.append(week)

    stats = {'followup': 0, 'reminder': 0, 'visit': 0}
    upcoming: List[Dict[str, Any]] = []
    for jkey, evs in events_by_jkey.items():
        jy, jm, jd = [int(x) for x in jkey.split('-')]
        for ev in evs:
            stats[ev['type']] = stats.get(ev['type'], 0) + 1
            upcoming.append({
                'jkey': jkey,
                'sort_key': (jy, jm, jd),
                'date_label': f'{to_persian_digits(jd)} {PERSIAN_MONTHS[jm - 1]}',
                'weekday': PERSIAN_WEEKDAYS[_saturday_offset(jdatetime.date(jy, jm, jd))],
                **ev,
            })
    upcoming.sort(key=lambda x: x['sort_key'])

    prev_y, prev_m = _prev_jmonth(jyear, jmonth)
    next_y, next_m = _next_jmonth(jyear, jmonth)

    month_strip = [
        {
            'num': m,
            'label': PERSIAN_MONTHS[m - 1],
            'active': m == jmonth,
        }
        for m in range(1, 13)
    ]

    return {
        'jyear': jyear,
        'jmonth': jmonth,
        'month_label': PERSIAN_MONTHS[jmonth - 1],
        'year_label': to_persian_digits(jyear),
        'title': f'{PERSIAN_MONTHS[jmonth - 1]} {to_persian_digits(jyear)}',
        'weeks': weeks,
        'month_strip': month_strip,
        'event_total': sum(len(v) for v in events_by_jkey.values()),
        'event_total_label': to_persian_digits(sum(len(v) for v in events_by_jkey.values())),
        'stats': stats,
        'stats_labels': {k: to_persian_digits(v) for k, v in stats.items()},
        'upcoming': upcoming[:10],
        'prev': {'jyear': prev_y, 'jmonth': prev_m},
        'next': {'jyear': next_y, 'jmonth': next_m},
        'today': {'jyear': today_j.year, 'jmonth': today_j.month, 'jday': today_j.day},
        'days_in_month': days_in_month,
        'days_in_month_label': to_persian_digits(days_in_month),
    }


def get_due_notifications(user, *, within_minutes: int = 30) -> List[Dict[str, Any]]:
    """یادآورها و پیگیری‌های نزدیک برای نوتیفیکیشن مرورگر."""
    now = timezone.now()
    horizon = now + timedelta(minutes=within_minutes)
    items = []

    for r in reminders_qs(user).filter(
        is_done=False, due_at__lte=horizon, due_at__gte=now - timedelta(minutes=5),
    ).select_related('customer')[:10]:
        items.append({
            'kind': 'reminder',
            'id': r.id,
            'title': r.title,
            'body': r.customer.name if r.customer else r.note[:80],
            'due_at': r.due_at.isoformat(),
            'url': '/workspace/crm/reminders/',
        })

    today = now.date()
    for c in customers_qs(user).filter(next_follow_up=today).exclude(status='بایگانی')[:5]:
        items.append({
            'kind': 'followup',
            'id': c.id,
            'title': f'پیگیری: {c.name}',
            'body': c.status,
            'due_at': now.replace(hour=9, minute=0).isoformat(),
            'url': f'/workspace/crm/contacts/{c.id}/',
        })

    return items
