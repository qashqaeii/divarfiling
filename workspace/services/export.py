"""صادرات داده."""
from __future__ import annotations

import csv
import json
import io
from typing import Iterable, List

from django.http import HttpResponse

from workspace.services.spreadsheet_io import spreadsheet_safe_cell, stable_union_fieldnames


def listings_to_rows(listings) -> List[dict]:
    rows = []
    for lst in listings:
        row = dict(lst.data) if lst.data else {}
        row.update({
            'شناسه': lst.token,
            'عنوان': lst.title,
            'قیمت': lst.price,
            'ودیعه': lst.deposit,
            'اجاره': lst.rent,
            'متراژ': lst.area,
            'محله': lst.neighborhood,
            'شهر': lst.city,
            'لینک': lst.link,
        })
        rows.append(row)
    return rows


def export_csv_response(listings, filename: str = 'export.csv') -> HttpResponse:
    rows = listings_to_rows(listings)
    if not rows:
        response = HttpResponse('', content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    fieldnames = stable_union_fieldnames(rows)
    safe_rows = [
        {k: spreadsheet_safe_cell(row.get(k)) for k in fieldnames}
        for row in rows
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(safe_rows)

    response = HttpResponse('\ufeff' + output.getvalue(), content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def export_json_response(listings, filename: str = 'export.json') -> HttpResponse:
    rows = listings_to_rows(listings)
    content = json.dumps(rows, ensure_ascii=False, indent=2, default=str)
    response = HttpResponse(content, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def export_excel_response(listings, filename: str = 'export.xlsx') -> HttpResponse:
    import io

    import pandas as pd

    rows = listings_to_rows(listings)
    if not rows:
        rows = [{'عنوان': ''}]
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine='openpyxl')
    buf.seek(0)
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def rows_json_response(rows: List[dict], filename: str = 'export.json') -> HttpResponse:
    content = json.dumps(rows, ensure_ascii=False, indent=2, default=str)
    response = HttpResponse(content, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
