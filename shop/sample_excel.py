"""پیش‌نمایش فایل نمونه اکسل برای صفحه محصول ربات."""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import pandas as pd
from django.conf import settings

SAMPLE_FILENAME = 'فروش_آپارتمان.xlsx'
SAMPLE_FOLDER_PATH = 'تهران/تهران/مرزداران/'
PREVIEW_ROW_LIMIT = 50

PRICE_COLUMNS = frozenset({'قیمت', 'قیمت هر متر'})
LTR_COLUMNS = frozenset({'لینک', 'شناسه', 'عرض جغرافیایی', 'طول جغرافیایی'})
WIDE_COLUMNS = frozenset({'عنوان', 'توضیحات', 'ویژگی‌ها و امکانات', 'نام مشاور / آژانس'})
LINK_COLUMNS = frozenset({'لینک'})


def _excel_col_letter(index: int) -> str:
    """تبدیل اندیس ستون (۰-مبنا) به حرف اکسل."""
    result = ''
    n = index + 1
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _format_cell(value, column: str) -> str:
    if _is_empty(value):
        return ''
    if column in PRICE_COLUMNS and isinstance(value, (int, float)):
        return f'{int(value):,}'
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if len(text) > 120:
        return text[:117] + '…'
    return text


def _cell_title(value, column: str) -> str:
    if _is_empty(value):
        return ''
    if column in PRICE_COLUMNS and isinstance(value, (int, float)):
        text = f'{int(value):,}'
    else:
        text = str(value).strip()
    return text.replace('\n', ' ').replace('\r', ' ')


def _cell_css(column: str) -> str:
    classes = ['pb-xls-cell']
    if column in PRICE_COLUMNS:
        classes.append('is-num is-price')
    elif column == 'متراژ':
        classes.append('is-num')
    elif column in LINK_COLUMNS:
        classes.append('is-link')
    if column in LTR_COLUMNS:
        classes.append('is-ltr')
    if column in WIDE_COLUMNS:
        classes.append('is-wide')
    return ' '.join(classes)


def _sample_path() -> Path | None:
    static_dir = Path(settings.BASE_DIR) / 'static'
    direct = static_dir / SAMPLE_FILENAME
    if direct.is_file():
        return direct
    matches = sorted(static_dir.glob('*.xlsx'))
    return matches[0] if matches else None


@lru_cache(maxsize=1)
def get_sale_apartment_excel_preview() -> dict | None:
    """خواندن فایل نمونه و آماده‌سازی داده برای رندر جدول."""
    path = _sample_path()
    if not path:
        return None

    df = pd.read_excel(path, engine='openpyxl')
    columns = [str(c) for c in df.columns]
    preview = df.head(PREVIEW_ROW_LIMIT)

    col_meta = [
        {
            'name': name,
            'letter': _excel_col_letter(i),
            'class': _cell_css(name),
        }
        for i, name in enumerate(columns)
    ]

    rows = []
    for row_index, (_, series) in enumerate(preview.iterrows(), start=2):
        cells = []
        for name in columns:
            raw = series[name]
            cells.append({
                'value': _format_cell(raw, name),
                'title': _cell_title(raw, name),
                'class': _cell_css(name),
                'href': str(raw).strip() if name in LINK_COLUMNS and not _is_empty(raw) else '',
            })
        rows.append({'num': row_index, 'cells': cells})

    return {
        'filename': SAMPLE_FILENAME,
        'folder_path': SAMPLE_FOLDER_PATH,
        'total_rows': len(df),
        'total_cols': len(columns),
        'preview_rows': len(rows),
        'columns': col_meta,
        'rows': rows,
    }
