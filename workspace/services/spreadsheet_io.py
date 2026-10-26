"""خواندن فایل‌های جدولی (CSV / Excel) برای Import."""
from __future__ import annotations

import io
import os
from typing import List, Optional, Tuple

import pandas as pd

SUPPORTED_IMPORT_EXTENSIONS = frozenset({'.csv', '.xlsx'})
LEGACY_XLS_EXTENSION = '.xls'

DEFAULT_MAX_ROWS = 50_000


class SpreadsheetReadError(Exception):
    pass


def extension_from_filename(name: str) -> str:
    return os.path.splitext((name or '').lower())[1]


def read_uploaded_spreadsheet(
    uploaded_file,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
    sheet_name: Optional[str] = None,
) -> Tuple[pd.DataFrame, str]:
    """
    خواندن فایل آپلود‌شده به DataFrame.
    برمی‌گرداند: (df, extension)
    """
    name = uploaded_file.name or ''
    ext = extension_from_filename(name)
    raw = uploaded_file.read()
    if not raw:
        raise SpreadsheetReadError('فایل خالی است.')

    if ext == '.csv':
        df = _read_csv_bytes(raw)
    elif ext == '.xlsx':
        df = pd.read_excel(io.BytesIO(raw), engine='openpyxl', sheet_name=sheet_name or 0)
    elif ext == LEGACY_XLS_EXTENSION:
        try:
            df = pd.read_excel(io.BytesIO(raw), sheet_name=sheet_name or 0)
        except Exception as exc:
            raise SpreadsheetReadError(
                'فرمت xls پشتیبانی نمی‌شود. فایل را با Excel به xlsx ذخیره کنید.'
            ) from exc
    else:
        raise SpreadsheetReadError(
            'فرمت فایل پشتیبانی نمی‌شود. از xlsx یا csv استفاده کنید.'
        )

    if isinstance(df, dict):
        first_key = next(iter(df.keys()))
        df = df[first_key]

    df = df.dropna(how='all')
    if df.empty:
        raise SpreadsheetReadError('فایل خالی است یا فقط ردیف‌های خالی دارد.')

    if len(df) > max_rows:
        raise SpreadsheetReadError(
            f'تعداد ردیف‌ها ({len(df)}) بیش از حد مجاز ({max_rows}) است.'
        )

    df.columns = [_normalize_header(str(c)) for c in df.columns]
    return df, ext


def _read_csv_bytes(raw: bytes) -> pd.DataFrame:
    for enc in ('utf-8-sig', 'utf-8', 'cp1256', 'utf-16'):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc)
        except UnicodeDecodeError:
            continue
        except pd.errors.ParserError:
            continue
    try:
        return pd.read_csv(io.BytesIO(raw), encoding='utf-8', sep=None, engine='python')
    except Exception as exc:
        raise SpreadsheetReadError(f'خواندن CSV ناموفق: {exc}') from exc


def normalize_spreadsheet_header(h: str) -> str:
    return str(h or '').strip().replace('\ufeff', '').replace('\u200c', '')


def _normalize_header(h: str) -> str:
    return normalize_spreadsheet_header(h)


def stable_union_fieldnames(rows: List[dict]) -> List[str]:
    """ترتیب پایدار ستون‌ها با union کلیدهای همه ردیف‌ها."""
    seen: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.append(key)
    return seen


def spreadsheet_safe_cell(value):
    """جلوگیری از Formula Injection در خروجی CSV/Excel."""
    if value is None:
        return value
    if isinstance(value, (int, float, bool)):
        return value
    s = str(value)
    if not s:
        return s
    if s[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + s
    return value
