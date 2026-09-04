"""اتصال موعدهای قرارداد به یادآور CRM."""
from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from contracts.models import Contract
from workspace.models import Reminder


def _parse_due_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, int):
        return None
    if isinstance(value, str):
        from workspace.services.jalali_input import parse_jalali_date_string
        parsed = parse_jalali_date_string(value)
        if isinstance(parsed, datetime):
            return parsed.date()
        return parsed
    return None


def sync_contract_reminders(contract: Contract) -> None:
    """ایجاد یادآورها از داده مالی قرارداد."""
    version = contract.current_version
    if not version:
        return
    deal = contract.deal
    fin = version.financial_data or {}
    user = contract.user
    customer = deal.customer

    Reminder.objects.filter(
        user=user,
        title__startswith=f'[قرارداد {contract.internal_number}]',
    ).delete()

    def _add(title: str, due_value, note: str = '', *, recurrence: str = '') -> None:
        due_date = _parse_due_date(due_value)
        if not due_date:
            return
        due_at = timezone.make_aware(datetime.combine(due_date, time(9, 0)))
        Reminder.objects.create(
            user=user,
            customer=customer,
            title=f'[قرارداد {contract.internal_number}] {title}',
            note=note,
            due_at=due_at,
            recurrence=recurrence,
        )

    def _add_before_end(lease_end, days_before: int, label: str) -> None:
        end = _parse_due_date(lease_end)
        if not end:
            return
        due = end - timedelta(days=days_before)
        _add(label, due)

    def _add_monthly_rent_day(day_of_month) -> None:
        try:
            dom = int(day_of_month)
        except (TypeError, ValueError):
            return
        if not 1 <= dom <= 31:
            return
        today = timezone.localdate()
        year, month = today.year, today.month
        if today.day >= dom:
            month += 1
            if month > 12:
                month = 1
                year += 1
        last_day = calendar.monthrange(year, month)[1]
        due_date = date(year, month, min(dom, last_day))
        due_at = timezone.make_aware(datetime.combine(due_date, time(9, 0)))
        Reminder.objects.create(
            user=user,
            customer=customer,
            title=f'[قرارداد {contract.internal_number}] سررسید اجاره',
            note=f'روز پرداخت اجاره: {dom}',
            due_at=due_at,
            recurrence='monthly',
        )

    ctype = contract.contract_type
    if ctype == 'lease':
        _add('یادآوری تحویل ملک', fin.get('delivery_date'))
        _add('تاریخ تخلیه', fin.get('vacate_date'))
        _add_monthly_rent_day(fin.get('rent_payment_day'))
        lease_end = fin.get('lease_end')
        _add_before_end(lease_end, 30, '۳۰ روز مانده به پایان اجاره')
        _add_before_end(lease_end, 7, '۷ روز مانده به پایان اجاره')
        _add('روز پایان اجاره', lease_end)
    elif ctype == 'sale':
        for idx, p in enumerate(fin.get('payments') or [], 1):
            _add(f'قسط {idx}', p.get('due_date'), p.get('label', ''))
        _add('اقدام انتقال رسمی', fin.get('transfer_date') or fin.get('official_transfer_date'))
        _add('تحویل ملک', fin.get('delivery_date'))
    elif ctype == 'jv':
        for milestone in (version.jv_data or {}).get('milestones') or []:
            _add(milestone.get('title', 'مرحله ساخت'), milestone.get('due_date'))
