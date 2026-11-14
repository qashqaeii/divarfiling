"""Data-quality hints for snapshot metrics (stock vs flow, cohort basis)."""
from __future__ import annotations

from typing import Any, Dict, List


def _warn(*lines: str) -> List[str]:
    return [ln for ln in lines if ln]


def enrich_data_quality(section: str, metrics: Dict[str, Any], period: Dict[str, Any]) -> Dict[str, Any]:
    days = period.get('days', 'all')
    warnings: List[str] = []
    semantics: Dict[str, Dict[str, str]] = {}

    period_label = f'بازه {days} روز' if str(days) not in ('all', '0') else 'بازه انتخاب‌شده'

    if section == 'crm':
        if 'overdue_reminders' in metrics:
            semantics['metrics.overdue_reminders'] = {
                'kind': 'stock_backlog',
                'time_basis': 'all_time_open_overdue',
                'note': 'یادآورهای معوق فعلی در کل سیستم؛ محدود به بازه KPI نیست.',
            }
        if 'reminders_created_period' in metrics:
            semantics['metrics.reminders_created_period'] = {
                'kind': 'flow_period',
                'time_basis': period_label,
                'note': 'یادآورهای ایجاد‌شده فقط در بازه انتخاب‌شده.',
            }
        if 'reminders_due' in metrics:
            semantics['metrics.reminders_due'] = {
                'kind': 'stock_snapshot',
                'time_basis': 'current',
                'note': 'یادآورهای سررسیدشده فعلی (snapshot).',
            }
        if 'overdue_reminders' in metrics and 'reminders_created_period' in metrics:
            warnings.append(
                'مقایسه مستقیم overdue_reminders (backlog کل) با reminders_created_period (flow بازه) '
                'بدون توضیح time_basis مجاز نیست.'
            )

    if section == 'users':
        for key, kind, note in (
            ('users_total', 'stock_snapshot', 'موجودی کل کاربران در لحظه.'),
            ('users_without_license', 'stock_snapshot', 'کاربران بدون لایسنس فعال — snapshot.'),
            ('users_new_period', 'flow_period', f'ثبت‌نام جدید در {period_label}.'),
            ('retention_d30', 'cohort_metric', 'نگهداشت یک‌ماهه؛ سهم ثبت‌نام‌های بازه که بعد از ۳۰ روز برگشته‌اند.'),
            ('retention_d7', 'cohort_metric', 'نگهداشت یک‌هفته‌ای؛ سهم ثبت‌نام‌های بازه که بعد از ۷ روز برگشته‌اند.'),
        ):
            if key in metrics:
                semantics[f'metrics.{key}'] = {'kind': kind, 'time_basis': period_label, 'note': note}
        if metrics.get('retention_d30', {}).get('current') == 0:
            warnings.append(
                'retention_d30 صفر است — قبل از تفسیر قطعی، کامل بودن tracking را ذکر کن.'
            )

    if section == 'licenses':
        for key, kind, note in (
            ('licenses_active', 'stock_snapshot', 'لایسنس‌های فعال فعلی.'),
            ('licenses_new_period', 'flow_period', f'لایسنس جدید در {period_label}.'),
            ('renewals_period', 'flow_period', f'تمدیدهای ثبت‌شده در {period_label} (طبق تعریف backend).'),
            ('licenses_expired', 'stock_or_period', 'منقضی‌شده — معنی را از label KPI بگیر.'),
        ):
            if key in metrics:
                semantics[f'metrics.{key}'] = {'kind': kind, 'time_basis': period_label, 'note': note}
        rb = metrics.get('renewal_breakdown', {}).get('current') or {}
        if rb:
            semantics['metrics.renewal_breakdown'] = {
                'kind': 'structured_breakdown',
                'note': 'تفکیک تمدید رسمی vs خرید کلید جدید؛ هر کدام را جدا نام ببر.',
            }

    return {
        'completeness': None,
        'warnings': _warn(*warnings),
        'metric_semantics': semantics,
    }
