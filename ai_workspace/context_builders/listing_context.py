"""Context Builder — آگهی دیوار."""
from __future__ import annotations

from typing import Any, Dict, List

from workspace.services.formatting import format_area, format_pct, format_toman
from workspace.services.features import extract_listing_features
from workspace.services.display import (
    build_listing_display_data,
    format_sections,
    format_supplementary_groups,
    transaction_profile,
)
from workspace.services.listing_features import build_listing_feature_profile

from ai_workspace.context_builders.base import redact_pii_text, truncate


def _join_fields(fields: Dict[str, str]) -> str:
    if not fields:
        return ''
    return '\n'.join(f'{k}: {v}' for k, v in fields.items())


def _feature_lines(profile: Dict[str, Any], limit: int = 24) -> str:
    lines: List[str] = []
    for item in profile.get('core') or []:
        if not item.get('known'):
            continue
        label = str(item.get('label') or '').strip()
        value = str(item.get('value') or '').strip()
        if label and value and value != '—':
            lines.append(f'{label}: {value}')
    for group in profile.get('groups') or []:
        for item in group.get('items') or []:
            label = str(item.get('label') or item.get('key') or '').strip()
            value = str(item.get('display') or item.get('value') or '').strip()
            if label and value and value != '—':
                lines.append(f'{label}: {value}')
            if len(lines) >= limit:
                break
        if len(lines) >= limit:
            break
    return '\n'.join(lines[:limit])


def _supplementary_lines(groups: List[Dict[str, Any]], limit: int = 16) -> str:
    lines: List[str] = []
    for group in groups:
        for row in group.get('fields') or []:
            key = str(row.get('key') or '').strip()
            display = str(row.get('display') or row.get('short') or '').strip()
            if key and display and display != '—':
                lines.append(f'{key}: {display}')
            if len(lines) >= limit:
                break
        if len(lines) >= limit:
            break
    return '\n'.join(lines[:limit])


def _benchmark_block(benchmark: Dict[str, Any]) -> Dict[str, str]:
    diff = benchmark.get('diff_pct')
    return {
        'metric_label': str(benchmark.get('label') or '').strip(),
        'listing_value': str(benchmark.get('price_per_sqm_fmt') or '').strip(),
        'market_median': str(benchmark.get('market_median_fmt') or '').strip(),
        'diff_pct': format_pct(diff) if diff is not None else '',
        'verdict': str(benchmark.get('verdict') or '').strip(),
        'note': str(benchmark.get('note') or '').strip(),
    }


def build(listing, dataset, benchmark: Dict[str, Any] | None = None) -> Dict[str, Any]:
    benchmark = benchmark or {}
    feat = extract_listing_features(listing)
    tx = transaction_profile(dataset.transaction_type)

    data = build_listing_display_data(listing, feat, transaction_type=dataset.transaction_type)
    desc = (getattr(listing, 'description', '') or '').strip()
    if desc and not any('توضیح' in k or 'description' in k.lower() for k in data):
        data['توضیحات'] = desc

    sections = format_sections(data, tx)
    sections.pop('سایر', None)
    if listing.latitude and listing.longitude:
        sections.setdefault('مکان', {})

    feature_profile = build_listing_feature_profile(listing, feat)
    supplementary_groups = format_supplementary_groups(data, tx, sections)

    price_label = ''
    if tx.get('show_price') and listing.price:
        price_label = format_toman(listing.price)
    elif listing.deposit or listing.rent:
        parts = []
        if listing.deposit:
            parts.append(f'ودیعه {format_toman(listing.deposit)}')
        if listing.rent:
            parts.append(f'اجاره {format_toman(listing.rent)}')
        price_label = ' · '.join(parts)

    text_tab = sections.get('متن') or {}
    description = ''
    for key in ('توضیحات', 'description', 'متن آگهی'):
        if key in text_tab:
            description = str(text_tab[key]).strip()
            break
    if not description:
        description = desc
    description = redact_pii_text(description)

    bench = _benchmark_block(benchmark)
    tab_financial = _join_fields(sections.get('مالی') or {})
    tab_property = _join_fields(sections.get('ملک') or {})
    tab_location = _join_fields(sections.get('مکان') or {})
    tab_text = redact_pii_text(
        _join_fields({k: v for k, v in text_tab.items() if k not in ('توضیحات', 'description')})
    )
    if description and not tab_text:
        tab_text = description
    tab_features = _feature_lines(feature_profile)
    tab_extra = _supplementary_lines(supplementary_groups)

    return {
        'title': listing.title or '',
        'token': listing.token or '',
        'deal_mode': tx.get('badge') or dataset.transaction_type or '',
        'price_label': price_label,
        'price_per_sqm_label': format_toman(listing.price_per_sqm, per_sqm=True) if listing.price_per_sqm else '',
        'area_label': format_area(listing.area) if listing.area else '',
        'rooms': feat.get('rooms') or listing.rooms or '',
        'floor': feat.get('floor') or '',
        'build_year': feat.get('build_year') or '',
        'neighborhood': listing.neighborhood or '',
        'city': listing.city or dataset.city or '',
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
        'content_version': f'{listing.id}:{listing.created_at.isoformat() if listing.created_at else ""}',
        '_listing': listing,
        '_dataset': dataset,
    }
