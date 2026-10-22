"""ترجیحات چندگانه نوع ملک در جست‌وجوی مخاطب CRM."""
from __future__ import annotations

from typing import Iterable, List, Optional, TYPE_CHECKING

from workspace.constants import CRM_PROPERTIES

if TYPE_CHECKING:
    from workspace.models import Customer

_CRM_PROPERTY_SET = frozenset(CRM_PROPERTIES)

# ورودی‌های رایج (مثلاً از دیوار) → مقدار استاندارد CRM
_CUSTOMER_PROPERTY_TYPE_ALIASES = {
    'خانه و ویلا': 'ویلا',
    'خانه': 'ویلا',
    'ویلایی': 'ویلا',
}

# برچسب نمایشی در UI (مقدار ذخیره‌شده تغییر نمی‌کند)
_CUSTOMER_PROPERTY_TYPE_DISPLAY = {
    'ویلا': 'خانه و ویلا',
}


def customer_property_type_display_label(value: str) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    return _CUSTOMER_PROPERTY_TYPE_DISPLAY.get(text, text)


def customer_search_property_type_choices() -> List[tuple]:
    return [(p, customer_property_type_display_label(p)) for p in CRM_PROPERTIES]


def normalize_customer_search_property_types(raw: Optional[Iterable]) -> List[str]:
    """حذف تکرار و مقادیر نامعتبر؛ ترتیب ورودی حفظ می‌شود."""
    if not raw:
        return []
    out: List[str] = []
    seen = set()
    for item in raw:
        text = _CUSTOMER_PROPERTY_TYPE_ALIASES.get(
            str(item or '').strip(),
            str(item or '').strip(),
        )
        if not text or text not in _CRM_PROPERTY_SET:
            continue
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def customer_search_property_types_list(customer: Customer) -> List[str]:
    """لیست انواع انتخاب‌شده برای نمایش و API."""
    raw = getattr(customer, 'property_types', None)
    if isinstance(raw, list) and raw:
        return normalize_customer_search_property_types(raw)
    legacy = (getattr(customer, 'property_type', None) or '').strip()
    if legacy and legacy != 'سایر':
        return [legacy]
    return []


def customer_search_property_types_restricted(customer: Customer) -> bool:
    return bool(customer_search_property_types_list(customer))


def apply_customer_search_property_types(customer: Customer, types: List[str]) -> None:
    """ذخیره ترجیحات و همگام‌سازی فیلد تک‌انتخابی legacy."""
    normalized = normalize_customer_search_property_types(types)
    customer.property_types = normalized
    if len(normalized) == 1:
        customer.property_type = normalized[0]
    else:
        customer.property_type = ''
