"""تقویم CRM — شمسی (جلالی) با رویدادهای پیگیری، یادآور، بازدید و قرارداد."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import jdatetime
from django.urls import reverse
from django.utils import timezone

from workspace.models import Customer, PropertyVisit
from workspace.services.crm_scope import customers_qs, deals_qs, reminders_qs
from workspace.services.jalali_input import (
    PERSIAN_MONTHS,
    PERSIAN_WEEKDAYS,
    format_jalali_date,
    to_persian_digits,
)


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


def _location_for_property(prop) -> str:
    if not prop:
        return ''
    parts = [p for p in (prop.neighborhood, prop.district) if p]
    return ' · '.join(parts)


def _location_for_customer(customer: Customer) -> str:
    return customer.district or ''


def _short_label(event: Dict[str, Any]) -> str:
    label = event.get('label', '')
    if ': ' in label:
        return label.split(': ', 1)[1]
    return label


def _event_time(event: Dict[str, Any]) -> str:
    return event.get('time') or ''


def _percent_change(current: int, previous: int) -> Optional[int]:
    if previous <= 0:
        return None if current <= 0 else 100
    return round(((current - previous) / previous) * 100)


def _week_range_gregorian(today_g: date) -> Tuple[date, date]:
    """شنبه تا جمعه هفته جاری."""
    weekday = (today_g.weekday() + 2) % 7  # Mon=0 → Sat=0
    start = today_g - timedelta(days=weekday)
    return start, start + timedelta(days=6)


def get_calendar_month(user, jyear: int, jmonth: int) -> Dict[str, Any]:
    """تقویم ماه شمسی با گرید شنبه‌محور."""
    today_j = jdatetime.date.today()
    today_g = today_j.togregorian()
    today_key = _jkey(today_j)
    jyear = max(1300, min(jyear, 1500))
    jmonth = max(1, min(jmonth, 12))

    days_in_month = _jdays_in_month(jyear, jmonth)
    first_j = jdatetime.date(jyear, jmonth, 1)
    last_j = jdatetime.date(jyear, jmonth, days_in_month)
    start_g = first_j.togregorian()
    end_g = last_j.togregorian()
    week_start_g, week_end_g = _week_range_gregorian(today_g)

    events_by_jkey: Dict[str, List[Dict[str, Any]]] = {}

    def add_gregorian(gday: date, event: Dict[str, Any]) -> None:
        jd = jdatetime.date.fromgregorian(date=gday)
        if jd.year != jyear or jd.month != jmonth:
            return
        event.setdefault('short_label', _short_label(event))
        events_by_jkey.setdefault(_jkey(jd), []).append(event)

    for c in customers_qs(user).filter(
        next_follow_up__gte=start_g, next_follow_up__lte=end_g,
    ).only('id', 'name', 'next_follow_up', 'status', 'district'):
        add_gregorian(c.next_follow_up, {
            'type': 'followup',
            'label': f'پیگیری: {c.name}',
            'customer_name': c.name,
            'location': _location_for_customer(c),
            'time': '',
            'href': reverse('workspace:crm_detail', kwargs={'customer_id': c.id}),
        })

    for r in reminders_qs(user).filter(
        is_done=False,
        due_at__date__gte=start_g, due_at__date__lte=end_g,
    ).select_related('customer'):
        local_due = timezone.localtime(r.due_at)
        add_gregorian(r.due_at.date(), {
            'type': 'reminder',
            'label': r.title,
            'customer_name': r.customer.name if r.customer else '',
            'location': _location_for_customer(r.customer) if r.customer else '',
            'time': local_due.strftime('%H:%M'),
            'href': reverse('workspace:crm_reminders'),
            'reminder_id': r.id,
        })

    for v in PropertyVisit.objects.filter(
        user=user, visit_date__gte=start_g, visit_date__lte=end_g,
    ).select_related('customer', 'property'):
        title = v.property.title if v.property else (v.listing_title or 'بازدید')
        add_gregorian(v.visit_date, {
            'type': 'visit',
            'label': f'بازدید: {title}',
            'customer_name': v.customer.name if v.customer else '',
            'location': _location_for_property(v.property) or _location_for_customer(v.customer),
            'time': '',
            'href': reverse('workspace:crm_detail', kwargs={'customer_id': v.customer_id}) + '?tab=visits',
        })

    for d in deals_qs(user).filter(
        contract_date__gte=start_g, contract_date__lte=end_g,
    ).select_related('customer', 'property'):
        add_gregorian(d.contract_date, {
            'type': 'contract',
            'label': f'قرارداد: {d.title}',
            'customer_name': d.customer.name if d.customer else '',
            'location': _location_for_property(d.property) or (
                _location_for_customer(d.customer) if d.customer else ''
            ),
            'time': '',
            'href': reverse('workspace:crm_deal_detail', kwargs={'deal_id': d.id}),
        })

    for c in customers_qs(user).filter(
        lease_deadline__gte=start_g, lease_deadline__lte=end_g,
    ).only('id', 'name', 'lease_deadline', 'district'):
        add_gregorian(c.lease_deadline, {
            'type': 'contract',
            'label': f'مهلت اجاره: {c.name}',
            'customer_name': c.name,
            'location': _location_for_customer(c),
            'time': '',
            'href': reverse('workspace:crm_detail', kwargs={'customer_id': c.id}),
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
            is_friday = jd.weekday() == 6  # jdatetime: شنبه=۰ … جمعه=۶
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

    stats = {'followup': 0, 'reminder': 0, 'visit': 0, 'contract': 0}
    upcoming: List[Dict[str, Any]] = []
    today_agenda: List[Dict[str, Any]] = []
    near_reminders: List[Dict[str, Any]] = []
    events_flat: List[Dict[str, Any]] = []

    followups_this_week = 0
    visits_today = 0
    reminders_today = 0
    overdue_n = 0
    upcoming_followups = 0
    upcoming_visits = 0

    for jkey, evs in events_by_jkey.items():
        jy, jm, jd = [int(x) for x in jkey.split('-')]
        jd_obj = jdatetime.date(jy, jm, jd)
        gday = jd_obj.togregorian()
        for ev in evs:
            stats[ev['type']] = stats.get(ev['type'], 0) + 1
            item = {
                'jkey': jkey,
                'sort_key': (jy, jm, jd, _event_time(ev)),
                'date_label': f'{to_persian_digits(jd)} {PERSIAN_MONTHS[jm - 1]}',
                'weekday': PERSIAN_WEEKDAYS[_saturday_offset(jd_obj)],
                **ev,
            }
            upcoming.append(item)
            events_flat.append({
                'jkey': jkey,
                'jyear': jy,
                'jmonth': jm,
                'jday': jd,
                'day_label': to_persian_digits(jd),
                'weekday': item['weekday'],
                'type': ev['type'],
                'label': ev['label'],
                'short_label': ev.get('short_label', ''),
                'customer_name': ev.get('customer_name', ''),
                'location': ev.get('location', ''),
                'time': ev.get('time', ''),
                'href': ev.get('href', ''),
            })

            if jkey == today_key:
                today_agenda.append(item)
                if ev['type'] == 'visit':
                    visits_today += 1
                elif ev['type'] == 'reminder':
                    reminders_today += 1

            if gday < today_g and ev['type'] in ('followup', 'reminder'):
                overdue_n += 1

            if ev['type'] == 'followup' and gday >= today_g:
                upcoming_followups += 1
                if week_start_g <= gday <= week_end_g:
                    followups_this_week += 1

            if ev['type'] == 'visit' and gday >= today_g:
                upcoming_visits += 1

            if ev['type'] == 'reminder' and gday > today_g:
                near_reminders.append(item)

    upcoming.sort(key=lambda x: x['sort_key'])
    today_agenda.sort(key=lambda x: (x.get('time') or '99:99', x.get('label', '')))
    near_reminders.sort(key=lambda x: x['sort_key'])

    event_total = sum(len(v) for v in events_by_jkey.values())
    today_n = len(today_agenda)
    prev_y, prev_m = _prev_jmonth(jyear, jmonth)
    next_y, next_m = _next_jmonth(jyear, jmonth)
    prev_total = _count_month_events(user, prev_y, prev_m)
    pct_change = _percent_change(event_total, prev_total)

    def _share(part: int, base: int) -> int:
        if not base:
            return 0
        return int(round((part / base) * 100))

    mix_segments: List[Dict[str, Any]] = []
    for key, label in (
        ('followup', 'پیگیری'),
        ('visit', 'بازدید'),
        ('reminder', 'یادآور'),
        ('contract', 'قرارداد'),
    ):
        count = int(stats.get(key) or 0)
        if count <= 0:
            continue
        mix_segments.append({
            'key': key,
            'label': label,
            'count': count,
            'pct': _share(count, event_total),
        })

    hero_bits = []
    for seg in mix_segments[:3]:
        hero_bits.append(f'{seg["count"]} {seg["label"]}')
    if pct_change is not None and pct_change > 0:
        hero_bits.append(f'+{abs(pct_change)}٪ ماه قبل')
    elif pct_change is not None and pct_change < 0:
        hero_bits.append(f'{abs(pct_change)}٪ کمتر از ماه قبل')
    hero_meta = ' · '.join(hero_bits) if hero_bits else (
        'رویدادی در این ماه نیست' if event_total == 0 else 'برنامه ماه آماده است'
    )

    if today_n:
        today_meta = f'{_share(today_n, event_total)}٪ از کارهای ماه'
        if visits_today or reminders_today:
            bits = []
            if visits_today:
                bits.append(f'{visits_today} بازدید')
            if reminders_today:
                bits.append(f'{reminders_today} یادآور')
            today_meta = ' · '.join(bits)
    elif event_total:
        today_meta = 'امروز برنامه آزادی دارید'
    else:
        today_meta = 'هنوز رویدادی نیست'

    if overdue_n:
        overdue_meta = f'{_share(overdue_n, event_total)}٪ از کارهای ماه عقب افتاده'
    elif event_total:
        overdue_meta = 'کار معوقی در این ماه نیست'
    else:
        overdue_meta = 'هنوز رویدادی نیست'

    if upcoming_followups:
        followup_meta = f'{followups_this_week} مورد این هفته'
    elif stats.get('followup'):
        followup_meta = 'پیگیری‌های باقی‌مانده گذشته‌اند'
    else:
        followup_meta = 'پیگیری پیش‌رویی نیست'

    # سازگاری با قالب‌های قدیمی + ساختار fl-kpi-pro
    kpis = {
        'total': {
            'value': event_total,
            'value_label': to_persian_digits(event_total),
            'context': hero_meta,
        },
        'followups': {
            'value': upcoming_followups,
            'value_label': to_persian_digits(upcoming_followups),
            'context': followup_meta,
        },
        'visits': {
            'value': upcoming_visits,
            'value_label': to_persian_digits(upcoming_visits),
            'context': f'{to_persian_digits(visits_today)} مورد امروز',
        },
        'reminders': {
            'value': stats.get('reminder', 0),
            'value_label': to_persian_digits(stats.get('reminder', 0)),
            'context': f'{to_persian_digits(reminders_today)} مورد امروز',
        },
        'month_total': event_total,
        'today': today_n,
        'overdue': overdue_n,
        'upcoming_followups': upcoming_followups,
        'upcoming_visits': upcoming_visits,
        'mix_segments': mix_segments,
        'hero_meta': hero_meta,
        'today_share': _share(today_n, event_total),
        'today_meta': today_meta,
        'overdue_share': _share(overdue_n, event_total),
        'overdue_meta': overdue_meta,
        'followup_share': _share(upcoming_followups, event_total),
        'followup_meta': followup_meta,
    }

    month_strip = [
        {
            'num': m,
            'label': PERSIAN_MONTHS[m - 1],
            'active': m == jmonth,
        }
        for m in range(1, 13)
    ]

    today_full_label = format_jalali_date(today_g)
    today_weekday = PERSIAN_WEEKDAYS[_saturday_offset(today_j)]

    return {
        'jyear': jyear,
        'jmonth': jmonth,
        'month_label': PERSIAN_MONTHS[jmonth - 1],
        'year_label': to_persian_digits(jyear),
        'title': f'{PERSIAN_MONTHS[jmonth - 1]} {to_persian_digits(jyear)}',
        'weeks': weeks,
        'month_strip': month_strip,
        'event_total': event_total,
        'event_total_label': to_persian_digits(event_total),
        'stats': stats,
        'stats_labels': {k: to_persian_digits(v) for k, v in stats.items()},
        'kpis': kpis,
        'upcoming': upcoming[:10],
        'today_agenda': today_agenda,
        'today_agenda_count': len(today_agenda),
        'today_agenda_count_label': to_persian_digits(len(today_agenda)),
        'today_full_label': today_full_label,
        'today_weekday': today_weekday,
        'near_reminders': near_reminders[:5],
        'events_flat': events_flat,
        'today_jkey': today_key,
        'prev': {'jyear': prev_y, 'jmonth': prev_m},
        'next': {'jyear': next_y, 'jmonth': next_m},
        'today': {'jyear': today_j.year, 'jmonth': today_j.month, 'jday': today_j.day},
        'days_in_month': days_in_month,
        'days_in_month_label': to_persian_digits(days_in_month),
    }


def _count_month_events(user, jyear: int, jmonth: int) -> int:
    """تعداد رویدادهای ماه — بدون ساخت گرید کامل."""
    jyear = max(1300, min(jyear, 1500))
    jmonth = max(1, min(jmonth, 12))
    days_in_month = _jdays_in_month(jyear, jmonth)
    first_j = jdatetime.date(jyear, jmonth, 1)
    last_j = jdatetime.date(jyear, jmonth, days_in_month)
    start_g = first_j.togregorian()
    end_g = last_j.togregorian()
    total = 0
    total += customers_qs(user).filter(
        next_follow_up__gte=start_g, next_follow_up__lte=end_g,
    ).count()
    total += reminders_qs(user).filter(
        is_done=False,
        due_at__date__gte=start_g, due_at__date__lte=end_g,
    ).count()
    total += PropertyVisit.objects.filter(
        user=user, visit_date__gte=start_g, visit_date__lte=end_g,
    ).count()
    total += deals_qs(user).filter(
        contract_date__gte=start_g, contract_date__lte=end_g,
    ).count()
    total += customers_qs(user).filter(
        lease_deadline__gte=start_g, lease_deadline__lte=end_g,
    ).count()
    return total


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
