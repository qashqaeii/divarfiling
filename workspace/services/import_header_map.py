"""نگاشت یکپارچه عنوان ستون‌های Import."""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from workspace.constants import IMPORT_CONTACT_COLUMNS, IMPORT_CONTACT_HEADER_ALIASES
from workspace.services.spreadsheet_io import normalize_spreadsheet_header

_COMPACT_RE = re.compile(r'[\s\u200c\u200d\ufeff\u00ad]+')


def compact_header_key(h: str) -> str:
    """کلید مقایسه — بدون فاصله، نیم‌فاصله و کاراکترهای نامرئی."""
    s = normalize_spreadsheet_header(h)
    s = s.replace('‌', '').replace('ي', 'ی').replace('ك', 'ک')
    return _COMPACT_RE.sub('', s)


def build_contact_header_map(columns: List[str]) -> Dict[str, str]:
    """
    نگاشت عنوان ستون فایل (همان‌طور که در DataFrame است) → نام فیلد مدل.
    هر فیلد مقصد فقط یک‌بار نگاشت می‌شود.
    """
    canonical: Dict[str, str] = {}
    for header, field in {**IMPORT_CONTACT_COLUMNS, **IMPORT_CONTACT_HEADER_ALIASES}.items():
        canonical[compact_header_key(header)] = field

    file_to_field: Dict[str, str] = {}
    used_fields: set = set()

    for col in columns:
        col_str = str(col or '').strip()
        if not col_str:
            continue
        field_name = canonical.get(compact_header_key(col_str))
        if not field_name or field_name in used_fields:
            continue
        file_to_field[col_str] = field_name
        used_fields.add(field_name)

    return file_to_field


def map_row_by_headers(row: dict, header_to_field: Dict[str, str]) -> Dict[str, object]:
    mapped: Dict[str, object] = {}
    for key, val in row.items():
        key_str = str(key).strip()
        field_name = header_to_field.get(key_str)
        if field_name and field_name not in mapped:
            mapped[field_name] = val
    return mapped


def contact_name_field_mapped(header_to_field: Dict[str, str]) -> bool:
    return 'name' in header_to_field.values()
