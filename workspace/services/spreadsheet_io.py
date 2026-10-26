"""خواندن فایل‌های جدولی (CSV / Excel) برای Import."""
from __future__ import annotations

import io
import os
from typing import List, Optional, Tuple

import pandas as pd

SUPPORTED_IMPORT_EXTENSIONS = frozenset({'.csv', '.xlsx'})
LEGACY_XLS_EXTENSION = '.xls'

DEFAULT_MAX_ROWS = 50_000
DEFAULT_MAX_COLUMNS = 200
DEFAULT_MAX_BYTES = 25 * 1024 * 1024  # 25MB


class SpreadsheetReadError(Exception):
    pass


def extension_from_filename(name: str) -> str:
    return os.path.splitext((name or '').lower())[1]


def _check_upload_size(uploaded_file, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
    size = getattr(uploaded_file, 'size', None)
    if size is not None and size > max_bytes:
        raise SpreadsheetReadError(
            f'حجم فایل ({size // (1024 * 1024)} مگابایت) بیش از حد مجاز است.'
        )


def read_uploaded_spreadsheet(
    uploaded_file,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
    max_columns: int = DEFAULT_MAX_COLUMNS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    sheet_name: Optional[str] = None,
) -> Tuple[pd.DataFrame, str]:
    """
    خواندن فایل آپلود‌شده به DataFrame.
    برمی‌گرداند: (df, extension)
    """
    name = uploaded_file.name or ''
    ext = extension_from_filename(name)
    _check_upload_size(uploaded_file, max_bytes=max_bytes)

    raw = uploaded_file.read()
    if not raw:
        raise SpreadsheetReadError('فایل خالی است.')
    if len(raw) > max_bytes:
        raise SpreadsheetReadError('حجم فایل بیش از حد مجاز است.')

    try:
        if ext == '.csv':
            df = _read_csv_bytes(raw)
        elif ext == '.xlsx':
            df = _read_excel_bytes(raw, sheet_name=sheet_name)
        elif ext == LEGACY_XLS_EXTENSION:
            raise SpreadsheetReadError(
                'فرمت xls پشتیبانی نمی‌شود. فایل را با Excel به xlsx ذخیره کنید.'
            )
        else:
            raise SpreadsheetReadError(
                'فرمت فایل پشتیبانی نمی‌شود. از xlsx یا csv استفاده کنید.'
            )
    except SpreadsheetReadError:
        raise
    except pd.errors.EmptyDataError:
        raise SpreadsheetReadError('فایل خالی است.') from None
    except pd.errors.ParserError as exc:
        raise SpreadsheetReadError(f'ساختار فایل نامعتبر است: {exc}') from exc
    except Exception as exc:
        raise SpreadsheetReadError(
            'خواندن فایل ناموفق بود. از قالب xlsx یا csv معتبر استفاده کنید.'
        ) from exc

    if isinstance(df, dict):
        first_key = next(iter(df.keys()))
        df = df[first_key]

    if df.shape[1] > max_columns:
        raise SpreadsheetReadError(
            f'تعداد ستون‌ها ({df.shape[1]}) بیش از حد مجاز ({max_columns}) است.'
        )

    df = df.dropna(how='all')
    if df.empty:
        raise SpreadsheetReadError('فایل خالی است یا فقط ردیف‌های خالی دارد.')

    if len(df) > max_rows:
        raise SpreadsheetReadError(
            f'تعداد ردیف‌ها ({len(df)}) بیش از حد مجاز ({max_rows}) است.'
        )

    df.columns = [_normalize_header(str(c)) for c in df.columns]
    return df, ext


def _read_excel_bytes(raw: bytes, *, sheet_name: Optional[str] = None) -> pd.DataFrame:
    try:
        return pd.read_excel(io.BytesIO(raw), engine='openpyxl', sheet_name=sheet_name or 0)
    except ImportError as exc:
        raise SpreadsheetReadError('خواندن Excel در سرور پیکربندی نشده است.') from exc
    except ValueError as exc:
        msg = str(exc).lower()
        if 'zip' in msg or 'excel' in msg or 'workbook' in msg:
            raise SpreadsheetReadError('فایل Excel خراب یا نامعتبر است.') from exc
        raise SpreadsheetReadError(f'خواندن Excel ناموفق: {exc}') from exc


def _read_csv_bytes(raw: bytes) -> pd.DataFrame:
    last_error: Optional[Exception] = None
    for enc in ('utf-8-sig', 'utf-8', 'cp1256', 'utf-16'):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except pd.errors.ParserError as exc:
            last_error = exc
            continue
    try:
        return pd.read_csv(io.BytesIO(raw), encoding='utf-8', sep=None, engine='python')
    except Exception as exc:
        last_error = exc
    raise SpreadsheetReadError(
        f'خواندن CSV ناموفق: {last_error}' if last_error else 'خواندن CSV ناموفق.'
    ) from last_error


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
