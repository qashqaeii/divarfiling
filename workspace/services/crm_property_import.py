"""Import فایل‌های شخصی CRM از Excel/CSV."""
from __future__ import annotations

import io
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError

from workspace.constants import (
    CRM_PROPERTIES,
    IMPORT_PROPERTY_COLUMNS,
    IMPORT_PROPERTY_HEADER_ALIASES,
    PROPERTY_ADVERTISER_TYPES,
    PROPERTY_DEAL_MODES,
    PROPERTY_PUBLISH_STATUSES,
    PROPERTY_TX_STATUSES,
)
from workspace.forms import parse_money_input
from workspace.models import CRMProperty
from workspace.services.crm import normalize_phone
from workspace.services.crm_scope import properties_qs
from workspace.services.features import parse_bool_feature, parse_rooms_value

_FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
_HEADER_TITLE_MARKERS = frozenset(
    {
        'عنوان',
        'title',
        'نام',
        'name',
        *IMPORT_PROPERTY_COLUMNS.keys(),
    }
)


def _normalize_header(h: str) -> str:
    return str(h or '').strip().replace('\ufeff', '')


def _compact_header(h: str) -> str:
    return re.sub(r'\s+', '', _normalize_header(h))


_COMPACT_HEADER_MARKERS = frozenset(_compact_header(h) for h in IMPORT_PROPERTY_COLUMNS)


def _map_row(row: dict) -> Dict[str, Any]:
    header_map = {**IMPORT_PROPERTY_COLUMNS, **IMPORT_PROPERTY_HEADER_ALIASES}
    mapped: Dict[str, Any] = {}
    for key, val in row.items():
        field = header_map.get(_normalize_header(key))
        if field and field not in mapped:
            mapped[field] = val
    return mapped


def _clean_str(val) -> str:
    if val is None:
        return ''
    if isinstance(val, float) and math.isnan(val):
        return ''
    s = str(val).strip()
    return '' if s.lower() in ('nan', 'none', 'null') else s


def _is_header_like_row(data: Dict[str, Any], title_val: str) -> bool:
    """ردیف تکراری هدر (مثلاً عنوان در ستون عنوان) را به‌عنوان داده قبول نکن."""
    if title_val in _HEADER_TITLE_MARKERS:
        return True
    if _compact_header(title_val) in _COMPACT_HEADER_MARKERS:
        return True
    sale = _clean_str(data.get('sale_price'))
    if sale and _compact_header(sale) in _COMPACT_HEADER_MARKERS:
        return True
    return False


def _parse_float(val) -> Optional[float]:
    if val is None or val == '':
        return None
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    if isinstance(val, int):
        return float(val)
    s = str(val).strip().translate(_FA_DIGITS).replace(',', '').replace('،', '')
    if not s or s.lower() in ('nan', 'none', '-', '—'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_int(val) -> Optional[int]:
    f = _parse_float(val)
    if f is None:
        return None
    return int(f)


def _parse_money(val) -> Optional[int]:
    if val is None or val == '':
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    try:
        return parse_money_input(val)
    except ValidationError:
        # در import به‌جای ۵۰۰، مبلغ نامعتبر را خالی می‌گذاریم
        return None

def _parse_bool(val) -> bool:
    parsed = parse_bool_feature(val)
    return bool(parsed) if parsed is not None else False


def _dedup_key(title: str, city: str, district: str) -> str:
    return '|'.join(
        part.strip().lower()
        for part in (title, city, district)
    )


def _normalize_business_type(val) -> str:
    raw = _clean_str(val)
    if not raw:
        return ''
    lowered = raw.lower().replace('\u200c', '')
    if lowered in ('personal', 'شخصی', 'مالک'):
        return 'شخصی'
    if 'مشاور' in lowered or lowered in ('consultant', 'premium-panel', 'premium'):
        return 'مشاور'
    if lowered in ('business', 'بنگاه'):
        return 'business'
    if raw in PROPERTY_ADVERTISER_TYPES:
        return raw
    return raw


def import_properties_from_file(user, uploaded_file) -> Tuple[int, int, List[str]]:
    """
    Import personal property files from xlsx/csv.
    Returns (created_count, skipped_count, errors).
    """
    import pandas as pd

    name = (uploaded_file.name or '').lower()
    raw = uploaded_file.read()
    errors: List[str] = []
    created = 0
    skipped = 0

    try:
        if name.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(raw))
        else:
            df = pd.read_excel(io.BytesIO(raw))
    except Exception as exc:
        return 0, 0, [f'خواندن فایل ناموفق: {exc}']

    if df.empty:
        return 0, 0, ['فایل خالی است.']

    active_props = properties_qs(user)
    existing_tokens = {
        t.strip()
        for t in active_props.exclude(token='').values_list('token', flat=True)
        if t and str(t).strip()
    }
    existing_keys = {
        _dedup_key(p.title or '', p.city or '', p.district or '')
        for p in active_props.only('title', 'city', 'district')
    }

    for idx, row in df.iterrows():
        row_num = int(idx) + 2  # هدر = ردیف ۱ در اکسل
        row_dict = {str(k): row[k] for k in df.columns}
        data = _map_row(row_dict)
        title_val = _clean_str(data.get('title'))
        if not title_val:
            skipped += 1
            continue
        if _is_header_like_row(data, title_val):
            skipped += 1
            continue

        token = _clean_str(data.get('token'))
        city = _clean_str(data.get('city'))
        district = _clean_str(data.get('district'))
        dedup = _dedup_key(title_val, city, district)

        if token and token in existing_tokens:
            skipped += 1
            continue
        if not token and dedup in existing_keys:
            skipped += 1
            continue

        property_type = _clean_str(data.get('property_type')) or 'آپارتمان'
        if property_type not in CRM_PROPERTIES:
            property_type = 'سایر'

        deal_mode = _clean_str(data.get('deal_mode')) or 'فروش'
        if deal_mode not in PROPERTY_DEAL_MODES:
            deal_mode = 'فروش'

        transaction_status = _clean_str(data.get('transaction_status')) or 'فعال'
        if transaction_status not in PROPERTY_TX_STATUSES:
            transaction_status = 'فعال'

        publish_status = _clean_str(data.get('publish_status')) or 'پیش‌نویس'
        if publish_status not in PROPERTY_PUBLISH_STATUSES:
            publish_status = 'پیش‌نویس'

        business_type = _normalize_business_type(data.get('business_type'))
        phone = normalize_phone(_clean_str(data.get('phone')))

        try:
            CRMProperty.objects.create(
                user=user,
                title=title_val,
                property_type=property_type,
                deal_mode=deal_mode,
                transaction_status=transaction_status,
                publish_status=publish_status,
                business_type=business_type,
                phone=phone,
                city=city,
                district=district,
                neighborhood=_clean_str(data.get('neighborhood')),
                address=_clean_str(data.get('address')),
                area=_parse_float(data.get('area')),
                rooms=parse_rooms_value(data.get('rooms')),
                floor=_parse_int(data.get('floor')),
                total_floors=_parse_int(data.get('total_floors')),
                build_year=_parse_int(data.get('build_year')),
                has_parking=_parse_bool(data.get('has_parking')),
                has_storage=_parse_bool(data.get('has_storage')),
                has_elevator=_parse_bool(data.get('has_elevator')),
                is_vacant=_parse_bool(data.get('is_vacant') or data.get('تخلیه')),
                sale_price=_parse_money(data.get('sale_price')),
                deposit=_parse_money(data.get('deposit')),
                monthly_rent=_parse_money(data.get('monthly_rent')),
                amenities=_clean_str(data.get('amenities')),
                token=token,
                link=_clean_str(data.get('link')),
                latitude=_parse_float(data.get('latitude')),
                longitude=_parse_float(data.get('longitude')),
                notes=_clean_str(data.get('notes')),
            )
        except ValidationError as exc:
            msg = '; '.join(getattr(exc, 'messages', [str(exc)]))
            errors.append(f'ردیف {row_num}: {msg}')
            skipped += 1
            continue
        except Exception as exc:
            errors.append(f'ردیف {row_num}: {exc}')
            skipped += 1
            continue

        if token:
            existing_tokens.add(token)
        existing_keys.add(dedup)
        created += 1

    return created, skipped, errors


def property_import_template_headers() -> List[str]:
    return list(IMPORT_PROPERTY_COLUMNS.keys())


def property_import_column_specs() -> List[Dict[str, Any]]:
    """متادیتای ستون‌ها برای UI import فایل‌های شخصی."""
    return [
        {'header': 'عنوان', 'required': True, 'hint': 'عنوان ملک — ردیف بدون عنوان رد می‌شود', 'example': 'آپارتمان ۱۲۰ متری شهرک غرب'},
        {'header': 'نوع ملک', 'required': False, 'hint': 'آپارتمان، ویلا، …', 'example': 'آپارتمان', 'values_key': 'property_types'},
        {'header': 'نوع معامله', 'required': False, 'hint': 'فروش یا رهن و اجاره', 'example': 'فروش', 'values_key': 'deal_modes'},
        {'header': 'وضعیت معامله', 'required': False, 'hint': 'مرحله پیگیری ملک', 'example': 'فعال', 'values_key': 'tx_statuses'},
        {'header': 'وضعیت انتشار', 'required': False, 'hint': 'وضعیت نمایش', 'example': 'پیش‌نویس', 'values_key': 'publish_statuses'},
        {'header': 'نوع آگهی دهنده', 'required': False, 'hint': 'شخصی، مشاور، business', 'example': 'شخصی', 'values_key': 'advertiser_types'},
        {'header': 'شماره تماس', 'required': False, 'hint': 'شماره مالک یا آگهی‌دهنده', 'example': '09121234567'},
        {'header': 'شهر', 'required': False, 'hint': 'شهر محل ملک', 'example': 'تهران'},
        {'header': 'منطقه', 'required': False, 'hint': 'منطقه یا ناحیه', 'example': 'منطقه ۲'},
        {'header': 'محله', 'required': False, 'hint': 'محله دقیق', 'example': 'شهرک غرب'},
        {'header': 'آدرس', 'required': False, 'hint': 'آدرس کامل', 'example': 'خیابان …'},
        {'header': 'متراژ (متر)', 'required': False, 'hint': 'عدد — اعشار مجاز', 'example': '120'},
        {'header': 'اتاق', 'required': False, 'hint': 'تعداد اتاق', 'example': '2'},
        {'header': 'طبقه', 'required': False, 'hint': 'طبقه واحد', 'example': '5'},
        {'header': 'تعداد طبقات', 'required': False, 'hint': 'کل طبقات ساختمان', 'example': '8'},
        {'header': 'سال ساخت', 'required': False, 'hint': 'مثلاً ۱۴۰۰', 'example': '1400'},
        {'header': 'پارکینگ', 'required': False, 'hint': 'بله / خیر / دارد / ندارد', 'example': 'بله'},
        {'header': 'انباری', 'required': False, 'hint': 'بله / خیر', 'example': 'بله'},
        {'header': 'آسانسور', 'required': False, 'hint': 'بله / خیر', 'example': 'بله'},
        {'header': 'قیمت فروش (تومان)', 'required': False, 'hint': 'فقط برای فروش', 'example': '8500000000'},
        {'header': 'رهن (تومان)', 'required': False, 'hint': 'مبلغ رهن', 'example': '500000000'},
        {'header': 'اجاره ماهانه (تومان)', 'required': False, 'hint': 'اجاره ماهانه', 'example': '25000000'},
        {'header': 'امکانات', 'required': False, 'hint': 'توضیح امکانات', 'example': 'بالکن، لابی'},
        {'header': 'شناسه آگهی', 'required': False, 'hint': 'شناسه یکتا — تکراری‌ها رد می‌شوند', 'example': 'abc123'},
        {'header': 'لینک', 'required': False, 'hint': 'لینک آگهی', 'example': 'https://divar.ir/v/…'},
        {'header': 'عرض جغرافیایی', 'required': False, 'hint': 'مختصات GPS', 'example': '35.7219'},
        {'header': 'طول جغرافیایی', 'required': False, 'hint': 'مختصات GPS', 'example': '51.3347'},
        {'header': 'یادداشت', 'required': False, 'hint': 'توضیح آزاد', 'example': 'مالک مستقیم'},
    ]


def property_import_template_excel_response():
    """فایل نمونه Excel برای import فایل‌های شخصی."""
    import pandas as pd
    from django.http import HttpResponse

    headers = list(IMPORT_PROPERTY_COLUMNS.keys())
    sample = {
        'عنوان': 'آپارتمان ۱۲۰ متری شهرک غرب',
        'نوع ملک': 'آپارتمان',
        'نوع معامله': 'فروش',
        'وضعیت معامله': 'فعال',
        'وضعیت انتشار': 'پیش‌نویس',
        'نوع آگهی دهنده': 'شخصی',
        'شماره تماس': '09121234567',
        'شهر': 'تهران',
        'منطقه': 'منطقه ۲',
        'محله': 'شهرک غرب',
        'آدرس': '',
        'متراژ (متر)': 120,
        'اتاق': '2',
        'طبقه': 5,
        'تعداد طبقات': 8,
        'سال ساخت': 1400,
        'پارکینگ': 'بله',
        'انباری': 'بله',
        'آسانسور': 'بله',
        'قیمت فروش (تومان)': 8500000000,
        'رهن (تومان)': '',
        'اجاره ماهانه (تومان)': '',
        'امکانات': 'بالکن، لابی',
        'شناسه آگهی': '',
        'لینک': '',
        'عرض جغرافیایی': '',
        'طول جغرافیایی': '',
        'یادداشت': 'مالک مستقیم',
    }
    df = pd.DataFrame([sample], columns=headers)
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="mizkar-properties-template.xlsx"'
    return response
