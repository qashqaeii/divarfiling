"""CRM property map — Mobile API (viewport + filters)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from workspace.services.crm import filter_properties
from workspace.services.crm_map import (
    CRM_MAP_FILTER_KEYS,
    crm_properties_map_markers,
    merged_properties_transaction_type,
)
from workspace.services.display import transaction_profile


MAP_MARKER_LIMIT = 500
MAP_MARKER_MAX = 2500


def _float_param(name: str, raw: Optional[str]) -> Optional[float]:
    if raw in (None, ''):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_bounds(params) -> Optional[Tuple[float, float, float, float]]:
    get = params.get if hasattr(params, 'get') else dict(params).get
    north = _float_param('north', get('north'))
    south = _float_param('south', get('south'))
    east = _float_param('east', get('east'))
    west = _float_param('west', get('west'))
    if None in (north, south, east, west):
        return None
    if south > north or west > east:
        return None
    return north, south, east, west


def _filter_params_from_request(params) -> Dict[str, str]:
    get = params.get if hasattr(params, 'get') else dict(params).get
    out: Dict[str, str] = {}
    for key in CRM_MAP_FILTER_KEYS:
        val = get(key)
        if val not in (None, ''):
            out[key] = str(val)
    q = str(get('q') or '').strip()
    if q:
        out['q'] = q
    return out


def crm_property_map_payload(user, params) -> Dict[str, Any]:
    get = params.get if hasattr(params, 'get') else dict(params).get
    try:
        limit = int(get('limit') or MAP_MARKER_LIMIT)
    except (TypeError, ValueError):
        limit = MAP_MARKER_LIMIT
    limit = max(1, min(limit, MAP_MARKER_MAX))

    filter_params = _filter_params_from_request(params)
    qs = filter_properties(user, filter_params)
    qs = qs.exclude(latitude__isnull=True).exclude(longitude__isnull=True)

    bounds = _parse_bounds(params)
    if bounds:
        north, south, east, west = bounds
        qs = qs.filter(
            latitude__gte=south,
            latitude__lte=north,
            longitude__gte=west,
            longitude__lte=east,
        )

    geo_count = qs.count()
    sampled = list(qs[:limit])
    transaction_type = merged_properties_transaction_type(sampled) if sampled else 'فروش'
    markers = crm_properties_map_markers(sampled, transaction_type=transaction_type)
    for marker, prop in zip(markers, sampled):
        marker['property_id'] = prop.pk
        marker['transaction_status'] = prop.transaction_status or ''
        marker['publish_status'] = prop.publish_status or ''
        if not marker.get('token'):
            marker['token'] = f'crm-property-{prop.pk}'

    tx = transaction_profile(transaction_type)
    return {
        'markers': markers,
        'geo_count': geo_count,
        'markers_shown': len(markers),
        'markers_truncated': geo_count > limit,
        'config': {
            'dataset_name': 'فایل‌های شخصی',
            'is_rent': bool(tx['is_rent'] and not tx['is_sale']),
            'filter_value_label': 'رهن کامل' if (tx['is_rent'] and not tx['is_sale']) else 'قیمت',
            'map_cluster': True,
        },
    }
