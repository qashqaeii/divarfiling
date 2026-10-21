"""ابزارهای مشترک نرمال‌سازی و استخراج اعداد از گزارش بازار."""
from __future__ import annotations

from typing import Any

_PERSIAN_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
_ASCII_DIGITS = '0123456789'
_DIGIT_TRANS = str.maketrans(_PERSIAN_DIGITS, _ASCII_DIGITS)


def normalize_number_text(text: str) -> str:
    if not text:
        return ''
    t = text.translate(_DIGIT_TRANS)
    t = t.replace('\u200c', '').replace('\u00a0', '')
    t = t.replace('،', ',').replace('٬', ',').replace('٫', '.')
    t = t.replace('٪', '%')
    return t


def extract_report_numbers(report: dict) -> list[str]:
    nums: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                if k.endswith('_fmt') and isinstance(v, str) and v.strip() and v.strip() != '—':
                    nums.append(v.strip())
                else:
                    walk(v)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if value > 0:
                nums.append(str(int(value)))

    walk(report)
    return list(dict.fromkeys(nums))
