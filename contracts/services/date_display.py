"""Stable, Persian-digit Jalali display formatting for contract and handover PDFs.

Database fields, API machine values and immutable signed snapshots stay Gregorian.
Date-only fields are never shifted through a timezone. Absolute timestamps use
Iran's civil time, independently of the web server's configured timezone.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.utils import timezone

from workspace.services.jalali_input import format_jalali_date, to_persian_digits

TEHRAN = ZoneInfo("Asia/Tehran")


def jalali_pdf_date(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        local = timezone.localtime(value, TEHRAN) if timezone.is_aware(value) else value
        value = local.date()
    return to_persian_digits(format_jalali_date(value))


def jalali_pdf_datetime(value: datetime | date | None) -> str:
    if value is None:
        return "—"
    if not isinstance(value, datetime):
        return jalali_pdf_date(value)
    local = timezone.localtime(value, TEHRAN) if timezone.is_aware(value) else value
    # Always show 00:00 as an actual time; a midnight signing is not date-only.
    label = f"{format_jalali_date(local.date())} {local:%H:%M}"
    return to_persian_digits(label)
