"""Import مخاطبین CRM از Excel/CSV."""
from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from workspace.constants import (
    CRM_PRIORITIES,
    CRM_SOURCES,
    CRM_STATUSES,
    CRM_TYPES,
    IMPORT_CONTACT_COLUMNS,
)
from workspace.models import Customer
from workspace.services.crm import log_activity, normalize_phone
from workspace.services.crm_import_phone import parse_import_phone_fields
from workspace.services.crm_merge import find_duplicate_contact, normalize_contact_name
from workspace.services.crm_scope import customers_qs, get_agency
from workspace.services.contact_gender import normalize_contact_gender_import
from workspace.services.import_header_map import (
    build_contact_header_map,
    contact_name_field_mapped,
    map_row_by_headers,
)
from workspace.services.spreadsheet_io import SpreadsheetReadError, read_uploaded_spreadsheet


@dataclass
class ImportRowError:
    row_number: int
    column: str
    reason: str
    hint: str = ''


@dataclass
class ContactImportResult:
    total_rows: int = 0
    processed_rows: int = 0
    created: int = 0
    updated: int = 0
    duplicates: int = 0
    invalid_rows: int = 0
    skipped_empty_name: int = 0
    row_errors: List[ImportRowError] = field(default_factory=list)
    created_ids: List[int] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str = ''

    @property
    def skipped(self) -> int:
        return self.duplicates + self.invalid_rows + self.skipped_empty_name

    @property
    def error_count(self) -> int:
        return len(self.row_errors)

    def error_messages(self, limit: int = 50) -> List[str]:
        msgs = []
        for err in self.row_errors[:limit]:
            line = f'ردیف {err.row_number}'
            if err.column:
                line += f' ({err.column})'
            line += f': {err.reason}'
            if err.hint:
                line += f' — {err.hint}'
            msgs.append(line)
        if self.aborted and self.abort_reason:
            msgs.insert(0, self.abort_reason)
        return msgs

    def visible_created_count(self, user) -> int:
        if not self.created_ids:
            return 0
        return customers_qs(user).filter(pk__in=self.created_ids).count()


def _clean_str(val) -> str:
    if val is None:
        return ''
    if isinstance(val, float) and math.isnan(val):
        return ''
    s = str(val).strip()
    return '' if s.lower() in ('nan', 'none', 'null') else s


def import_contacts_from_file_result(user, uploaded_file) -> ContactImportResult:
    result = ContactImportResult()
    try:
        df, _ext = read_uploaded_spreadsheet(uploaded_file)
    except SpreadsheetReadError as exc:
        result.aborted = True
        result.abort_reason = str(exc)
        return result

    header_to_field = build_contact_header_map(list(df.columns))
    if not contact_name_field_mapped(header_to_field):
        result.aborted = True
        result.abort_reason = (
            'ستون «نام» شناسایی نشد. عنوان ستون را مطابق نمونه تنظیم کنید '
            '(مثلاً نام، نام مخاطب، نام مشتری).'
        )
        return result

    result.total_rows = len(df)

    existing_keys = set()
    for c in customers_qs(user).only('name', 'phone', 'phone_alt'):
        phone_key = normalize_phone(c.phone)
        name_key = normalize_contact_name(c.name).casefold()
        if phone_key and name_key:
            existing_keys.add((name_key, phone_key))

    in_file_keys = set()
    agency = get_agency(user)

    for idx, row in df.iterrows():
        row_num = int(idx) + 2
        row_dict = {str(k): row[k] for k in df.columns}
        data = map_row_by_headers(row_dict, header_to_field)
        name_val = _clean_str(data.get('name'))
        if not name_val:
            result.skipped_empty_name += 1
            continue

        result.processed_rows += 1

        phone, phone_alt, phone_err = parse_import_phone_fields(
            data.get('phone'),
            data.get('phone_alt'),
        )
        if phone_err:
            result.invalid_rows += 1
            result.row_errors.append(ImportRowError(
                row_number=row_num,
                column='تلفن',
                reason=phone_err,
                hint='مثال: 09121234567 یا 02188776655',
            ))
            continue
        phone_key = normalize_phone(phone)

        name_key = normalize_contact_name(name_val).casefold()
        dup_key = (name_key, phone_key) if phone and name_key else None

        if dup_key:
            if dup_key in existing_keys or dup_key in in_file_keys:
                result.duplicates += 1
                continue
            existing = find_duplicate_contact(user, name_val, phone)
            if existing:
                result.duplicates += 1
                existing_keys.add(dup_key)
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
            agency=agency,
            name=name_val,
            phone=phone,
            phone_alt=phone_alt,
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
        if dup_key:
            existing_keys.add(dup_key)
            in_file_keys.add(dup_key)
        result.created_ids.append(customer.pk)
        result.created += 1

    return result


def import_contacts_from_file(user, uploaded_file) -> Tuple[int, int, List[str]]:
    """
    Import contacts from xlsx/csv.
    Returns (created_count, skipped_count, errors) — سازگار با نسخه قبلی.
    """
    result = import_contacts_from_file_result(user, uploaded_file)
    return result.created, result.skipped, result.error_messages()


def build_import_errors_csv(result: ContactImportResult) -> bytes:
    """فایل CSV خطاهای import برای دانلود."""
    import csv

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['ردیف', 'ستون', 'علت', 'راهکار'])
    for err in result.row_errors:
        writer.writerow([err.row_number, err.column, err.reason, err.hint])
    return ('\ufeff' + buf.getvalue()).encode('utf-8')


def import_template_headers() -> List[str]:
    return list(IMPORT_CONTACT_COLUMNS.keys())


def import_column_specs() -> List[Dict[str, Any]]:
    """متادیتای ستون‌ها برای UI import."""
    return [
        {'header': 'نام', 'required': True, 'hint': 'نام کامل مخاطب (یا نام مخاطب / نام مشتری)', 'example': 'علی رضایی'},
        {'header': 'تلفن', 'required': False, 'hint': 'با نام یکسان — تکراری رد می‌شود', 'example': '09121234567'},
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
