"""Import مخاطبین CRM از Excel/CSV."""
from __future__ import annotations

import io
from typing import Any, Dict, List, Tuple

from workspace.constants import CRM_PRIORITIES, CRM_SOURCES, CRM_STATUSES, CRM_TYPES, IMPORT_CONTACT_COLUMNS
from workspace.models import Customer
from workspace.services.crm import log_activity, normalize_phone
from workspace.services.contact_gender import normalize_contact_gender_import


def _normalize_header(h: str) -> str:
    return str(h or '').strip().replace('\ufeff', '')


def _map_row(row: dict) -> Dict[str, Any]:
    mapped: Dict[str, Any] = {}
    for src, field in IMPORT_CONTACT_COLUMNS.items():
        for key, val in row.items():
            if _normalize_header(key) == src:
                mapped[field] = val
                break
    return mapped


def _clean_str(val) -> str:
    if val is None:
        return ''
    s = str(val).strip()
    return '' if s.lower() in ('nan', 'none', 'null') else s


def import_contacts_from_file(user, uploaded_file) -> Tuple[int, int, List[str]]:
    """
    Import contacts from xlsx/csv.
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

    from workspace.services.crm_merge import normalize_contact_name

    existing_keys = set()
    for c in Customer.objects.filter(user=user):
        phone_key = normalize_phone(c.phone)
        name_key = normalize_contact_name(c.name).casefold()
        if len(phone_key) >= 10 and name_key:
            existing_keys.add((name_key, phone_key))

    for idx, row in df.iterrows():
        row_dict = {str(k): row[k] for k in df.columns}
        data = _map_row(row_dict)
        name_val = _clean_str(data.get('name'))
        if not name_val:
            skipped += 1
            continue

        phone = _clean_str(data.get('phone'))
        phone_key = normalize_phone(phone)
        name_key = normalize_contact_name(name_val).casefold()
        if len(phone_key) >= 10 and name_key and (name_key, phone_key) in existing_keys:
            skipped += 1
            continue

        customer_type = _clean_str(data.get('customer_type')) or 'سرنخ'
        if customer_type not in CRM_TYPES:
            customer_type = 'سرنخ'

        status = _clean_str(data.get('status')) or 'جدید'
        if status not in CRM_STATUSES:
            status = 'جدید'

        priority = _clean_str(data.get('priority')) or 'متوسط'
        if priority not in CRM_PRIORITIES:
            priority = 'متوسط'

        source = _clean_str(data.get('source'))
        if source and source not in CRM_SOURCES:
            source = 'سایر'

        gender = normalize_contact_gender_import(data.get('gender'))

        customer = Customer.objects.create(
            user=user,
            name=name_val,
            phone=phone,
            phone_alt=_clean_str(data.get('phone_alt')),
            email=_clean_str(data.get('email')),
            gender=gender,
            customer_type=customer_type,
            status=status,
            priority=priority,
            source=source or '',
            city=_clean_str(data.get('city')),
            district=_clean_str(data.get('district')),
            tags=_clean_str(data.get('tags')),
            notes=_clean_str(data.get('notes')),
        )
        log_activity(customer, 'یادداشت', content='واردشده از فایل', title='Import')
        if len(phone_key) >= 10 and name_key:
            existing_keys.add((name_key, phone_key))
        created += 1

    return created, skipped, errors


def import_template_headers() -> List[str]:
    return list(IMPORT_CONTACT_COLUMNS.keys())


def import_column_specs() -> List[Dict[str, Any]]:
    """متادیتای ستون‌ها برای UI import."""
    return [
        {'header': 'نام', 'required': True, 'hint': 'نام کامل مخاطب', 'example': 'علی رضایی'},
        {'header': 'تلفن', 'required': False, 'hint': 'شناسه یکتا — تکراری‌ها رد می‌شوند', 'example': '09121234567'},
        {'header': 'تلفن دوم', 'required': False, 'hint': 'شماره جایگزین', 'example': '02188776655'},
        {'header': 'ایمیل', 'required': False, 'hint': 'اختیاری', 'example': 'ali@example.com'},
        {'header': 'جنسیت', 'required': False, 'hint': 'اختیاری — آقا، خانم، male، female', 'example': 'خانم'},
        {'header': 'نوع', 'required': False, 'hint': 'سرنخ، خریدار، فروشنده، …', 'example': 'سرنخ', 'values_key': 'types'},
        {'header': 'وضعیت', 'required': False, 'hint': 'مرحله پیگیری', 'example': 'جدید', 'values_key': 'statuses'},
        {'header': 'اولویت', 'required': False, 'hint': 'سطح اهمیت', 'example': 'متوسط', 'values_key': 'priorities'},
        {'header': 'منبع', 'required': False, 'hint': 'منبع جذب', 'example': 'دیوار', 'values_key': 'sources'},
        {'header': 'شهر', 'required': False, 'hint': 'شهر محل', 'example': 'تهران'},
        {'header': 'منطقه', 'required': False, 'hint': 'محله یا منطقه', 'example': 'شهرک غرب'},
        {'header': 'یادداشت', 'required': False, 'hint': 'توضیح آزاد', 'example': 'تماس بعدازظهر'},
        {'header': 'برچسب‌ها', 'required': False, 'hint': 'برچسب با کاما', 'example': 'VIP,اجاره'},
    ]


def import_template_excel_response():
    """فایل نمونه Excel برای import مخاطبین."""
    import pandas as pd
    from django.http import HttpResponse

    headers = list(IMPORT_CONTACT_COLUMNS.keys())
    sample = {
        'نام': 'علی رضایی',
        'تلفن': '09121234567',
        'تلفن دوم': '',
        'ایمیل': 'ali@example.com',
        'جنسیت': 'خانم',
        'نوع': 'سرنخ',
        'وضعیت': 'جدید',
        'اولویت': 'متوسط',
        'منبع': 'دیوار',
        'شهر': 'تهران',
        'منطقه': 'شهرک غرب',
        'یادداشت': 'تماس بعدازظهر',
        'برچسب‌ها': 'VIP',
    }
    df = pd.DataFrame([sample], columns=headers)
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="mizkar-contacts-template.xlsx"'
    return response
