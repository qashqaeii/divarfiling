"""صادرات داده."""
from __future__ import annotations

import csv
import json
import io
from typing import Iterable, List

from django.http import HttpResponse


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

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()), extrasaction='ignore')
    writer.writeheader()
    writer.writerows(rows)

    response = HttpResponse('\ufeff' + output.getvalue(), content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def export_json_response(listings, filename: str = 'export.json') -> HttpResponse:
    rows = listings_to_rows(listings)
    content = json.dumps(rows, ensure_ascii=False, indent=2, default=str)
    response = HttpResponse(content, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
