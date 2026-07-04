"""Fallback تحلیل آپلود — آمار عددی."""
from __future__ import annotations

import json
from typing import Any, Dict, List


def build(context: Dict[str, Any]) -> Dict[str, Any]:
    total_files = context.get('total_files') or 0
    total_added = context.get('total_added') or 0
    new_files = context.get('new_files') or 0
    updated_files = context.get('updated_files') or 0
    errors_count = context.get('errors_count') or 0
    outlier_count = context.get('outlier_count')
    duplicate_count = context.get('duplicate_count')
    median_price = context.get('median_price_label') or ''

    summary = (
        f'{total_files} فایل پردازش شد — {total_added:,} آگهی جدید'
        f' ({new_files} فایل جدید، {updated_files} ادغام).'
    )
    if errors_count:
        summary += f' {errors_count} فایل با خطا.'

    opportunities: List[str] = []
    if total_added and outlier_count:
        opportunities.append(f'{outlier_count} آگهی قیمت پرت — فرصت مذاکره یا بررسی سریع.')
    if median_price:
        opportunities.append(f'میانه قیمت بازار: {median_price}')

    outliers_note = ''
    if outlier_count is not None:
        outliers_note = f'{outlier_count} آگهی خارج از محدوده معمول بازار شناسایی شد.'

    duplicates_note = ''
    if duplicate_count is not None:
        duplicates_note = f'{duplicate_count} آگهی تکراری در مجموعه وجود دارد.'

    action_items = [
        'آگهی‌های زیر میانه بازار را برای پیشنهاد به مشتریان اولویت‌بندی کنید.',
        'فایل‌های پرت قیمت را قبل از تماس بررسی کنید.',
    ]
    if errors_count:
        action_items.append('فایل‌های خطادار را دوباره آپلود یا بررسی کنید.')

    payload = {
        'executive_summary': summary,
        'opportunities': opportunities,
        'outliers_note': outliers_note,
        'duplicates_note': duplicates_note,
        'action_items': action_items[:3],
    }
    return {
        'data': payload,
        'raw_text': json.dumps(payload, ensure_ascii=False),
        'is_fallback': True,
    }
