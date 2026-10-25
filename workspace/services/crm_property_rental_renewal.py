"""پیگیری تمدید اجاره — تاریخ پایان قرارداد و یادآور یک ماه قبل (جلالی)."""
from __future__ import annotations

import datetime as dt
import re
from typing import Any, Dict, Optional

import jdatetime
from django.utils import timezone

from workspace.models import CRMProperty, Reminder
from workspace.services.crm_scope import can_edit_property
from workspace.services.jalali_input import format_jalali_date, parse_jalali_date_string

RENEWAL_REMINDER_KIND = 'rental_renewal'
RENEWAL_REMINDER_TITLE = 'پیگیری تمدید اجاره — {title}'
_LEGACY_NOTE_PROPERTY_ID = re.compile(r'\s*·\s*property_id=\d+\s*', re.IGNORECASE)


def format_renewal_reminder_note(contract_end: dt.date, follow: dt.date) -> str:
    return (
        f'پایان قرارداد: {format_jalali_date(contract_end)} · '
        f'پیگیری تمدید: {format_jalali_date(follow)}'
    )


def sanitize_reminder_note_for_display(note: str) -> str:
    """حذف شناسه‌های داخلی از متن یادآور برای نمایش در UI."""
    text = (note or '').strip()
    if not text:
        return ''
    return _LEGACY_NOTE_PROPERTY_ID.sub('', text).strip()


def property_is_rental(prop: CRMProperty) -> bool:
    return (prop.deal_mode or '') in ('رهن و اجاره', 'اجاره')


def max_jalali_day(year: int, month: int) -> int:
    if month <= 6:
        return 31
    if month <= 11:
        return 30
    return 30 if jdatetime.date(year, 1, 1).isleap() else 29


def subtract_one_jalali_month(gregorian_date: dt.date) -> dt.date:
    j = jdatetime.date.fromgregorian(date=gregorian_date)
    y, m, d = j.year, j.month, j.day
    if m == 1:
        m = 12
        y -= 1
    else:
        m -= 1
    d = min(d, max_jalali_day(y, m))
    return jdatetime.date(y, m, d).togregorian()


def renewal_followup_date(contract_end: dt.date) -> dt.date:
    return subtract_one_jalali_month(contract_end)


def suggest_contract_end_one_year_after(reference: Optional[dt.date] = None) -> dt.date:
    """پیشنهاد قابل ویرایش: یک سال تقویم جلالی بعد از تاریخ مرجع."""
    ref = reference or timezone.now().date()
    j = jdatetime.date.fromgregorian(date=ref)
    y = j.year + 1
    m = j.month
    d = min(j.day, max_jalali_day(y, m))
    return jdatetime.date(y, m, d).togregorian()


def get_renewal_reminder(user, prop: CRMProperty) -> Optional[Reminder]:
    return (
        Reminder.objects.filter(
            user=user,
            property=prop,
            reminder_kind=RENEWAL_REMINDER_KIND,
        )
        .order_by('-created_at')
        .first()
    )


def _due_datetime_for_date(d: dt.date) -> dt.datetime:
    naive = dt.datetime.combine(d, dt.time(9, 0))
    if timezone.is_naive(naive):
        return timezone.make_aware(naive, timezone.get_current_timezone())
    return naive


def upsert_renewal_schedule(
    user,
    prop: CRMProperty,
    contract_end: dt.date,
    *,
    create_reminder: bool,
) -> Optional[Reminder]:
    if not can_edit_property(user, prop):
        raise PermissionError('امکان ویرایش این ملک را ندارید')
    if not property_is_rental(prop):
        raise ValueError('فقط برای فایل‌های اجاره‌ای')
    if contract_end < timezone.now().date().replace(year=timezone.now().year - 30):
        raise ValueError('تاریخ پایان قرارداد نامعتبر است')

    prop.rental_contract_end_date = contract_end
    prop.save(update_fields=['rental_contract_end_date', 'updated_at'])

    if not create_reminder:
        Reminder.objects.filter(
            user=user,
            property=prop,
            reminder_kind=RENEWAL_REMINDER_KIND,
            is_done=False,
        ).update(is_done=True)
        return None

    follow = renewal_followup_date(contract_end)
    due_at = _due_datetime_for_date(follow)
    title = RENEWAL_REMINDER_TITLE.format(title=prop.title)[:200]
    note = format_renewal_reminder_note(contract_end, follow)
    existing = (
        Reminder.objects.filter(
            user=user,
            property=prop,
            reminder_kind=RENEWAL_REMINDER_KIND,
            is_done=False,
        )
        .order_by('-created_at')
        .first()
    )
    if existing:
        existing.due_at = due_at
        existing.title = title
        existing.note = note
        existing.save(update_fields=['due_at', 'title', 'note'])
        return existing
    return Reminder.objects.create(
        user=user,
        property=prop,
        reminder_kind=RENEWAL_REMINDER_KIND,
        title=title,
        note=note,
        due_at=due_at,
    )


def parse_contract_end_jalali(raw: str) -> dt.date:
    text = (raw or '').strip()
    if not text:
        raise ValueError('تاریخ پایان قرارداد الزامی است')
    parsed = parse_jalali_date_string(text)
    if not parsed:
        raise ValueError('تاریخ پایان قرارداد نامعتبر است')
    return parsed


def build_renewal_panel(user, prop: CRMProperty) -> Dict[str, Any]:
    contract_end = prop.rental_contract_end_date
    follow = renewal_followup_date(contract_end) if contract_end else None
    reminder = get_renewal_reminder(user, prop)
    today = timezone.now().date()
    days_until_follow = None
    if follow:
        days_until_follow = (follow - today).days

    if reminder and reminder.is_done:
        reminder_state = 'done'
    elif reminder and not reminder.is_done:
        reminder_state = 'scheduled'
    else:
        reminder_state = 'none'

    return {
        'has_contract_end': bool(contract_end),
        'contract_end': contract_end,
        'contract_end_jalali': format_jalali_date(contract_end) if contract_end else '',
        'followup_date': follow,
        'followup_jalali': format_jalali_date(follow) if follow else '',
        'reminder': reminder,
        'reminder_id': reminder.pk if reminder else None,
        'reminder_state': reminder_state,
        'days_until_followup': days_until_follow,
        'tracking_missing': property_is_rental(prop) and is_property_archived(prop) and not contract_end,
    }


def is_property_archived(prop: CRMProperty) -> bool:
    from workspace.services.crm_property_archive import is_property_archived as _is

    return _is(prop)
