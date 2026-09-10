"""خروجی داده مشاوران — با اعتبارسنجی مستقل و Audit."""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any, Iterable, Optional

from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from workspace.models import CRMAgencyMember
from workspace.services.agency_data_scope import (
    assert_can_export,
    get_member_contacts_qs,
    get_member_contracts_qs,
    get_member_deals_qs,
    get_member_filing_qs,
    get_member_listings_qs,
    get_member_properties_qs,
    list_visible_advisor_members,
    log_agency_activity,
    resolve_visible_agency_member,
)
from workspace.services.agency_entitlement import resolve_managed_agency
from workspace.services.crm import customers_to_export_rows

EXPORT_DATA_TYPES = ('contacts', 'properties', 'filing', 'deals', 'contracts')
EXPORT_FORMATS = ('csv', 'xlsx')


def _parse_filter_dates(filters: dict) -> tuple:
    date_from = filters.get('date_from') or filters.get('from')
    date_to = filters.get('date_to') or filters.get('to')
    if isinstance(date_from, str) and date_from:
        parsed = parse_datetime(date_from) or parse_date(date_from)
        if parsed and timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed)
        date_from = parsed
    if isinstance(date_to, str) and date_to:
        parsed = parse_datetime(date_to) or parse_date(date_to)
        if parsed:
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed)
            if hasattr(parsed, 'hour') and parsed.hour == 0:
                from datetime import timedelta
                date_to = parsed + timedelta(days=1) - timedelta(microseconds=1)
            else:
                date_to = parsed
    return date_from, date_to


def _audit_export(
    actor,
    member: CRMAgencyMember,
    data_type: str,
    fmt: str,
    record_count: int,
    filters: dict,
) -> None:
    log_agency_activity(
        member.agency,
        actor,
        'advisor_data_export',
        object_type='member',
        object_id=member.pk,
        metadata={
            'member_id': member.pk,
            'target_user_id': member.user_id,
            'dataset': data_type,
            'format': fmt,
            'record_count': record_count,
            'filters': {k: v for k, v in filters.items() if v},
        },
    )


def _rows_to_response(rows: list[dict], fmt: str, filename: str) -> HttpResponse:
    if not rows:
        rows = [{'—': ''}]
    if fmt == 'xlsx':
        import pandas as pd
        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine='openpyxl')
        buf.seek(0)
        return HttpResponse(
            buf.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'},
        )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return HttpResponse(
        buf.getvalue().encode('utf-8-sig'),
        content_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


def _properties_to_rows(properties) -> list[dict]:
    rows = []
    for p in properties:
        rows.append({
            'عنوان': p.title,
            'نوع': p.property_type,
            'معامله': p.deal_mode,
            'وضعیت': p.transaction_status,
            'شهر': p.city,
            'منطقه': p.district,
            'محله': p.neighborhood,
            'متراژ': p.area,
            'قیمت فروش': p.sale_price,
            'رهن': p.deposit,
            'اجاره': p.monthly_rent,
            'تلفن': p.phone,
            'تاریخ ثبت': p.created_at,
            'آخرین بروزرسانی': p.updated_at,
        })
    return rows


def _deals_to_rows(deals) -> list[dict]:
    rows = []
    for d in deals:
        rows.append({
            'عنوان': d.title,
            'مخاطب': d.customer.name if d.customer_id else '',
            'ملک': d.property.title if d.property_id else '',
            'مرحله': d.stage,
            'ارزش': d.value,
            'کمیسیون': d.commission_amount,
            'اقدام بعدی': d.next_action_type,
            'زمان اقدام': d.next_action_at,
            'ایجاد': d.created_at,
            'بروزرسانی': d.updated_at,
        })
    return rows


def _filing_to_rows(datasets, listings=None) -> list[dict]:
    if listings is not None:
        rows = []
        for l in listings:
            rows.append({
                'Dataset': l.dataset.name if l.dataset_id else '',
                'شناسه': l.token,
                'عنوان': l.title,
                'قیمت': l.price,
                'متراژ': l.area,
                'محله': l.neighborhood,
                'شهر': l.city,
                'تاریخ': l.created_at,
            })
        return rows
    rows = []
    for ds in datasets:
        rows.append({
            'نام Dataset': ds.name,
            'فرمت': ds.file_format,
            'تعداد آگهی': getattr(ds, 'listing_count', ds.row_count),
            'شهر': ds.city,
            'منطقه': ds.district,
            'نوع معامله': ds.transaction_type,
            'ایجاد': ds.created_at,
            'بروزرسانی': ds.updated_at,
        })
    return rows


def _contracts_to_rows(contracts) -> list[dict]:
    rows = []
    for c in contracts:
        rows.append({
            'شناسه': c.internal_number,
            'عنوان': c.title,
            'نوع': c.get_contract_type_display(),
            'وضعیت': c.get_status_display(),
            'معامله': c.deal.title if c.deal_id else '',
            'ایجاد': c.created_at,
            'بروزرسانی': c.updated_at,
        })
    return rows


def export_member_data(
    actor,
    member_id: int,
    data_type: str,
    fmt: str = 'xlsx',
    *,
    filters: Optional[dict] = None,
) -> HttpResponse:
    filters = filters or {}
    date_from, date_to = _parse_filter_dates(filters)
    member = resolve_visible_agency_member(actor, member_id)
    assert_can_export(actor, member)
    if data_type not in EXPORT_DATA_TYPES:
        raise ValueError('نوع داده نامعتبر است')
    if fmt not in EXPORT_FORMATS:
        raise ValueError('فرمت نامعتبر است')

    ts = datetime.now().strftime('%Y%m%d')
    advisor_label = (member.user.phone or member.user.username or str(member.user_id))[:20]

    if data_type == 'contacts':
        qs = get_member_contacts_qs(
            actor, member, search=filters.get('search', ''),
            date_from=date_from, date_to=date_to,
        )
        rows = customers_to_export_rows(qs)
    elif data_type == 'properties':
        qs = get_member_properties_qs(
            actor, member, search=filters.get('search', ''),
            date_from=date_from, date_to=date_to,
        )
        rows = _properties_to_rows(qs)
    elif data_type == 'filing':
        if filters.get('dataset_id'):
            qs = get_member_listings_qs(actor, member, dataset_id=filters['dataset_id'])
            rows = _filing_to_rows(None, qs)
        else:
            qs = get_member_filing_qs(actor, member, date_from=date_from, date_to=date_to)
            rows = _filing_to_rows(qs)
    elif data_type == 'deals':
        qs = get_member_deals_qs(
            actor, member, search=filters.get('search', ''),
            date_from=date_from, date_to=date_to,
        )
        rows = _deals_to_rows(qs)
    else:
        qs = get_member_contracts_qs(actor, member)
        rows = _contracts_to_rows(qs)

    record_count = len(rows) if isinstance(rows, list) else qs.count()
    _audit_export(actor, member, data_type, fmt, record_count, filters)
    filename = f'agency_{data_type}_{advisor_label}_{ts}.{fmt}'
    return _rows_to_response(rows, fmt, filename)


def export_team_data(
    actor,
    data_type: str,
    fmt: str = 'xlsx',
    *,
    member_ids: Optional[list[int]] = None,
    filters: Optional[dict] = None,
) -> HttpResponse:
    filters = filters or {}
    date_from, date_to = _parse_filter_dates(filters)
    agency, sub = resolve_managed_agency(actor)
    if not agency or not sub:
        raise PermissionError('اشتراک آژانس فعال نیست')

    members = list_visible_advisor_members(actor)
    if member_ids:
        members = members.filter(pk__in=member_ids)
    members = list(members)
    if not members:
        raise ValueError('مشاوری برای خروجی انتخاب نشده است')

    all_rows: list[dict] = []
    for member in members:
        assert_can_export(actor, member)
        label = member.user.get_full_name() or member.user.phone or member.user.username
        if data_type == 'contacts':
            qs = get_member_contacts_qs(
                actor, member, search=filters.get('search', ''),
                date_from=date_from, date_to=date_to,
            )
            for row in customers_to_export_rows(qs):
                row['مشاور'] = label
                all_rows.append(row)
        elif data_type == 'properties':
            for row in _properties_to_rows(get_member_properties_qs(
                actor, member, date_from=date_from, date_to=date_to,
            )):
                row['مشاور'] = label
                all_rows.append(row)
        elif data_type == 'deals':
            for row in _deals_to_rows(get_member_deals_qs(
                actor, member, date_from=date_from, date_to=date_to,
            )):
                row['مشاور'] = label
                all_rows.append(row)
        elif data_type == 'filing':
            for row in _filing_to_rows(get_member_filing_qs(
                actor, member, date_from=date_from, date_to=date_to,
            )):
                row['مشاور'] = label
                all_rows.append(row)
        else:
            raise ValueError('نوع داده تیمی نامعتبر است')

    _audit_export(
        actor,
        members[0],
        f'team_{data_type}',
        fmt,
        len(all_rows),
        {**filters, 'member_ids': [m.pk for m in members]},
    )
    ts = datetime.now().strftime('%Y%m%d')
    filename = f'agency_team_{data_type}_{ts}.{fmt}'
    return _rows_to_response(all_rows, fmt, filename)
