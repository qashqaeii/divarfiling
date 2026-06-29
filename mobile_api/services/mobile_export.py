"""خروجی فایل برای API موبایل."""
from __future__ import annotations

from django.http import HttpResponse

from workspace.services.crm import (
    customers_to_export_rows,
    export_customers_csv_response,
    export_customers_excel_response,
    export_customers_queryset,
    export_properties_csv_response,
    export_properties_excel_response,
    properties_to_export_rows,
    export_properties_queryset,
)
from workspace.services.export import rows_json_response


def export_contacts_response(user, params, fmt: str) -> HttpResponse:
    fmt = (fmt or 'xlsx').lower()
    if fmt == 'json':
        rows = customers_to_export_rows(export_customers_queryset(user, params))
        if not rows:
            rows = [{'نام': ''}]
        return rows_json_response(rows, 'crm_contacts.json')
    if fmt == 'csv':
        return export_customers_csv_response(user, params)
    return export_customers_excel_response(user, params)


def export_properties_response(user, params, fmt: str) -> HttpResponse:
    fmt = (fmt or 'xlsx').lower()
    if fmt == 'json':
        rows = properties_to_export_rows(export_properties_queryset(user, params))
        if not rows:
            rows = [{'عنوان': ''}]
        return rows_json_response(rows, 'crm_properties.json')
    if fmt == 'csv':
        return export_properties_csv_response(user, params)
    return export_properties_excel_response(user, params)
