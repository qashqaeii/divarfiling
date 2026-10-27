"""Context Builder — فایل شخصی CRM."""
from __future__ import annotations

from typing import Any, Dict, List

from workspace.models import CRMProperty
from workspace.services.formatting import format_area, format_pct, format_toman

from ai_workspace.context_builders.base import redact_pii_text, truncate
from ai_workspace.context_builders.listing_context import _benchmark_block, _feature_lines


def _join_fields(fields: Dict[str, str]) -> str:
    if not fields:
        return ''
    return '\n'.join(f'{k}: {v}' for k, v in fields.items())


def _bool_label(value: bool | None) -> str:
    if value is True:
        return 'دارد'
    if value is False:
        return 'ندارد'
    return ''


def _financial_fields(prop: CRMProperty) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    if prop.deal_mode == 'فروش' and prop.sale_price:
        fields['قیمت فروش'] = format_toman(prop.sale_price)
    if prop.deposit:
        fields['ودیعه'] = format_toman(prop.deposit)
    if prop.monthly_rent:
        fields['اجاره ماهانه'] = format_toman(prop.monthly_rent)
    if prop.sale_price and prop.area and prop.area > 0:
        fields['قیمت هر متر'] = format_toman(int(prop.sale_price / prop.area), per_sqm=True)
    return fields


def _property_fields(prop: CRMProperty) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    if prop.property_type:
        fields['نوع ملک'] = prop.property_type
    if prop.area:
        fields['متراژ'] = format_area(prop.area)
    if prop.rooms:
        fields['اتاق'] = prop.rooms
    if prop.floor is not None:
        fields['طبقه'] = str(prop.floor)
    if prop.total_floors:
        fields['تعداد طبقات'] = str(prop.total_floors)
    if prop.build_year:
        fields['سال ساخت'] = str(prop.build_year)
    parking = _bool_label(prop.has_parking)
    if parking:
        fields['پارکینگ'] = parking
    storage = _bool_label(prop.has_storage)
    if storage:
        fields['انباری'] = storage
    elevator = _bool_label(prop.has_elevator)
    if elevator:
        fields['آسانسور'] = elevator
    return fields


def _location_fields(
    prop: CRMProperty,
    *,
    include_address: bool = False,
    mask_sensitive: bool = False,
) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    if prop.city:
        fields['شهر'] = prop.city
    if prop.district:
        fields['منطقه'] = prop.district
    if prop.neighborhood and not mask_sensitive:
        fields['محله'] = prop.neighborhood
    if include_address and prop.address and not mask_sensitive:
        fields['آدرس'] = prop.address
    return fields


def _extra_lines(prop: CRMProperty, limit: int = 16, *, include_crm_notes: bool = True) -> str:
    lines: List[str] = []
    amenities = (prop.amenities or '').strip()
    if amenities:
        for line in amenities.splitlines():
            text = line.strip()
            if text:
                lines.append(text)
            if len(lines) >= limit:
                break
    if include_crm_notes and prop.notes and len(lines) < limit:
        for line in prop.notes.splitlines():
            text = line.strip()
            if text:
                lines.append(text)
            if len(lines) >= limit:
                break
    return '\n'.join(lines[:limit])


def _price_label(prop: CRMProperty) -> str:
    if prop.deal_mode == 'فروش' and prop.sale_price:
        return format_toman(prop.sale_price)
    parts = []
    if prop.deposit:
        parts.append(f'ودیعه {format_toman(prop.deposit)}')
    if prop.monthly_rent:
        parts.append(f'اجاره {format_toman(prop.monthly_rent)}')
    return ' · '.join(parts)


def _price_per_sqm_label(prop: CRMProperty) -> str:
    if prop.sale_price and prop.area and prop.area > 0:
        return format_toman(int(prop.sale_price / prop.area), per_sqm=True)
    return ''


def build(
    prop: CRMProperty,
    benchmark: Dict[str, Any] | None = None,
    *,
    feature_profile: Dict[str, Any] | None = None,
    include_address: bool = False,
    include_crm_notes: bool = True,
    mask_sensitive: bool = False,
) -> Dict[str, Any]:
    benchmark = benchmark or {}
    feature_profile = feature_profile or {}

    tab_financial = _join_fields(_financial_fields(prop))
    tab_property = _join_fields(_property_fields(prop))
    tab_location = _join_fields(
        _location_fields(prop, include_address=include_address, mask_sensitive=mask_sensitive),
    )
    tab_features = _feature_lines(feature_profile) if feature_profile.get('has_details') else ''
    if not tab_features:
        tab_features = tab_property
    tab_text = ''
    if include_crm_notes:
        tab_text = truncate(redact_pii_text((prop.notes or '').strip()), 1200)
    tab_extra = redact_pii_text(_extra_lines(prop, include_crm_notes=include_crm_notes))

    bench = _benchmark_block(benchmark)
    description = tab_text or tab_extra

    return {
        'title': prop.title or '',
        'token': prop.token or '',
        'deal_mode': prop.deal_mode or '',
        'price_label': _price_label(prop),
        'price_per_sqm_label': _price_per_sqm_label(prop),
        'area_label': format_area(prop.area) if prop.area else '',
        'rooms': prop.rooms or '',
        'floor': str(prop.floor) if prop.floor is not None else '',
        'build_year': str(prop.build_year) if prop.build_year else '',
        'neighborhood': (prop.neighborhood or '') if not mask_sensitive else '',
        'city': prop.city or '',
        'tab_financial': tab_financial,
        'tab_property': tab_property,
        'tab_location': tab_location,
        'tab_text': tab_text or truncate(description, 1200),
        'tab_features': tab_features,
        'tab_extra': tab_extra,
        'benchmark': bench,
        'benchmark_verdict': bench.get('verdict') or '',
        'benchmark_note': bench.get('note') or '',
        'benchmark_diff': bench.get('diff_pct') or '',
        'market_median': bench.get('market_median') or '',
        'benchmark_listing_value': bench.get('listing_value') or '',
        'benchmark_metric': bench.get('metric_label') or '',
        'description_excerpt': truncate(description, 1200),
        'content_version': f'crm-{prop.id}:{prop.updated_at.isoformat() if prop.updated_at else ""}',
        '_property': prop,
    }
