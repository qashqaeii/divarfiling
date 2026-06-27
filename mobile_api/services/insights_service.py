"""تحلیل و نقشه فایلینگ برای API موبایل — همان موتور workspace."""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from mobile_api.serializers import dataset_to_dict
from mobile_api.services.filing_service import get_dataset
from workspace.services.analyzer import (
    analyze_market,
    build_analysis_dashboard,
    compute_outliers_report,
    compute_statistics,
    filter_outliers,
    listings_to_dataframe,
)
from workspace.services.analyze_ui import build_l2_ui, build_l3_ui
from workspace.services.charts import build_all_charts, map_markers
from workspace.services.display import transaction_profile
from workspace.services.market_agent import resolve_report_confidence
from workspace.services.property_images import normalize_external_image_url


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, 'item'):
        try:
            return _json_safe(value.item())
        except Exception:
            return str(value)
    return str(value)


def _build_insights_core(dataset) -> Optional[Dict[str, Any]]:
    listings = list(dataset.listings.all())
    df = listings_to_dataframe(listings)
    if df.empty:
        return None

    lite = len(df) > 200
    df_clean = filter_outliers(df, dataset.transaction_type) if len(df) >= 10 else df
    tx = transaction_profile(dataset.transaction_type)

    stats = compute_statistics(df_clean, dataset.transaction_type)
    outliers = compute_outliers_report(df, dataset.transaction_type)
    market = analyze_market(df_clean, dataset.transaction_type)
    market_stats = market.get('stats', {})

    dashboard = build_analysis_dashboard(
        df_clean,
        stats,
        market,
        dataset.transaction_type,
        df_raw=df,
        outliers_report=outliers,
        listings=listings,
        dataset_name=dataset.name,
        subcategory=dataset.subcategory or '',
    )

    prof = dashboard['professional']
    confidence = resolve_report_confidence(
        prof,
        valid_count=len(df_clean),
        raw_count=len(df),
    )
    prof['confidence'] = confidence

    charts = build_all_charts(
        df_clean,
        lite=lite,
        transaction_type=dataset.transaction_type,
        market_stats=market_stats,
        area_segments=dashboard['area_segments'],
        report=prof,
    )
    l2 = build_l2_ui(prof, charts, flat_insights=dashboard.get('insights'))
    l3 = build_l3_ui(prof)

    geo_count = dataset.listings.exclude(
        latitude__isnull=True,
    ).exclude(longitude__isnull=True).count()

    return {
        'dataset': dataset_to_dict(dataset),
        'meta': {
            'row_count': len(df),
            'clean_count': len(df_clean),
            'lite_mode': lite,
            'geo_count': geo_count,
            'transaction_type': dataset.transaction_type or '',
            'is_rent': bool(tx['is_rent'] and not tx['is_sale']),
            'filter_value_label': 'رهن کامل' if (tx['is_rent'] and not tx['is_sale']) else 'قیمت',
        },
        'confidence': confidence,
        'header': prof.get('header') or {},
        'quick_snapshot': prof.get('quick_snapshot') or {},
        'market_depth': prof.get('market_depth') or {},
        'area_segments': prof.get('area_segments') or [],
        'neighborhoods': prof.get('neighborhoods') or [],
        'amenities_coverage': prof.get('amenities_coverage') or {},
        'opportunities': (prof.get('opportunities') or [])[:6],
        'insights': prof.get('insights') or [],
        'negotiation': (prof.get('negotiation') or [])[:6],
        'market_sentiment': prof.get('market_sentiment') or {},
        'data_quality': prof.get('data_quality') or {},
        'l2': l2,
        'l3': l3,
        'charts': charts,
    }


def dataset_insights_payload(user, dataset_id: str) -> Optional[Dict[str, Any]]:
    ds = get_dataset(user, dataset_id)
    if not ds:
        return None
    core = _build_insights_core(ds)
    if not core:
        return {
            'dataset': dataset_to_dict(ds),
            'meta': {
                'row_count': 0,
                'clean_count': 0,
                'lite_mode': False,
                'geo_count': 0,
                'transaction_type': ds.transaction_type or '',
                'is_rent': False,
                'filter_value_label': 'قیمت',
            },
            'confidence': None,
            'header': {},
            'quick_snapshot': {},
            'market_depth': {},
            'area_segments': [],
            'neighborhoods': [],
            'amenities_coverage': {},
            'opportunities': [],
            'insights': [],
            'negotiation': [],
            'market_sentiment': {},
            'data_quality': {},
            'l2': {'tabs': []},
            'l3': {'show': False},
            'charts': [],
        }
    return _json_safe(core)


def dataset_map_payload(user, dataset_id: str, *, marker_limit: int = 2500) -> Optional[Dict[str, Any]]:
    ds = get_dataset(user, dataset_id)
    if not ds:
        return None

    tx = transaction_profile(ds.transaction_type)
    geo_listings = ds.listings.exclude(
        latitude__isnull=True,
    ).exclude(longitude__isnull=True)
    geo_count = geo_listings.count()
    sampled = list(geo_listings[:marker_limit])
    markers = map_markers(
        sampled,
        transaction_type=ds.transaction_type,
        dataset_id=ds.pk,
    )
    for marker in markers:
        thumb = marker.get('thumb')
        if thumb:
            marker['thumb'] = normalize_external_image_url(str(thumb))

    return _json_safe({
        'dataset': dataset_to_dict(ds),
        'markers': markers,
        'config': {
            'map_cluster': True,
            'focus_max_zoom': 17,
            'cluster_disable_zoom': 15,
            'dataset_name': ds.name,
            'dataset_city': ds.city or '',
            'is_rent': bool(tx['is_rent'] and not tx['is_sale']),
            'filter_value_label': 'رهن کامل' if (tx['is_rent'] and not tx['is_sale']) else 'قیمت',
            'modes': ['markers', 'market', 'value', 'full_deposit' if tx['is_rent'] and not tx['is_sale'] else 'value'],
        },
        'geo_count': geo_count,
        'markers_shown': len(markers),
        'markers_truncated': geo_count > marker_limit,
        'consultant_count': sum(1 for m in markers if m.get('is_consultant')),
        'personal_count': sum(1 for m in markers if not m.get('is_consultant')),
    })
