"""بررسی کیفیت فایل برای استودیو."""
from __future__ import annotations

from typing import Any, Dict, List

from workspace.models import CRMProperty
from workspace.services.property_content_studio.brand import default_brand_from_user


def _item(status: str, label: str, detail: str = '') -> Dict[str, str]:
    return {'status': status, 'label': label, 'detail': detail}


def build_quality_report(prop: CRMProperty, user) -> Dict[str, Any]:
    items: List[Dict[str, str]] = []
    images = list(prop.images or [])
    if images:
        items.append(_item('ok', 'تصاویر موجود است'))
    else:
        items.append(_item('warn', 'تصویر ثبت نشده', 'پوستر بدون عکس محدود می‌شود'))

    if prop.area:
        items.append(_item('ok', 'متراژ ثبت شده'))
    else:
        items.append(_item('warn', 'متراژ ثبت نشده'))

    if prop.property_type:
        items.append(_item('ok', 'نوع ملک مشخص است'))
    else:
        items.append(_item('warn', 'نوع ملک نامشخص'))

    if prop.sale_price or prop.deposit or prop.monthly_rent:
        items.append(_item('ok', 'قیمت ثبت شده'))
    else:
        items.append(_item('warn', 'قیمت ثبت نشده'))

    if prop.neighborhood or prop.city:
        items.append(_item('ok', 'موقعیت مشخص است'))
    else:
        items.append(_item('warn', 'موقعیت ثبت نشده'))

    brand = default_brand_from_user(user)
    if brand.get('contact_phone'):
        items.append(_item('ok', 'شماره تماس تبلیغاتی مشخص است'))
    else:
        items.append(_item('warn', 'شماره تماس تبلیغاتی خالی است', 'در تنظیمات برند وارد کنید'))

    desc_len = len((prop.notes or '').strip())
    if desc_len >= 80:
        items.append(_item('ok', 'توضیحات برای AI کافی است'))
    elif desc_len > 0:
        items.append(_item('warn', 'توضیحات فایل کوتاه است'))
    else:
        items.append(_item('warn', 'توضیحات فایل خالی است'))

    ok_count = sum(1 for i in items if i['status'] == 'ok')
    score = round(100 * ok_count / max(len(items), 1))
    suggested_template = 'minimal'
    if len(images) >= 3:
        suggested_template = 'gallery'
    elif prop.sale_price and prop.sale_price >= 10_000_000_000:
        suggested_template = 'luxury'
    elif not images:
        suggested_template = 'minimal'

    return {
        'items': items,
        'score': score,
        'suggested_template': suggested_template,
        'can_generate_posters': True,
    }
