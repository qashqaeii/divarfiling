"""نقشه فایل‌های شخصی — reuse همان Map Pro فایلینگ (`map_markers` + initMap)."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List
from urllib.parse import urlencode

from django.urls import reverse

from workspace.carto_basemap import get_carto_basemap_api_key
from workspace.mixins import get_or_create_settings
from workspace.services.advertiser_signal import (
    ADVERTISER_SIGNAL_CONSULTANT,
    ADVERTISER_SIGNAL_DISGUISED,
    property_advertiser_display,
)
from workspace.services.charts import map_markers
from workspace.services.crm import filter_properties
from workspace.services.display import transaction_profile
from workspace.services.filters import get_neighborhoods_qs

MAP_MARKER_LIMIT = 2500

CRM_MAP_FILTER_KEYS = (
    'q', 'deal_mode', 'transaction_status', 'property_type', 'publish_status', 'city',
    'folder_id', 'cabinet_id',
    'parking', 'storage', 'elevator', 'rooms',
    'area_min', 'area_max', 'price_min', 'price_max',
    'year_min', 'year_max', 'age_max',
)

_BOOL_FEATURE_LABELS = (
    ('has_elevator', 'آسانسور'),
    ('has_parking', 'پارکینگ'),
    ('has_storage', 'انباری'),
)


def property_deal_to_transaction_type(deal_mode: str) -> str:
    dm = (deal_mode or '').strip()
    if dm in ('رهن و اجاره', 'اجاره') or ('اجاره' in dm and 'فروش' not in dm):
        return 'اجاره'
    if dm == 'فروش' or 'فروش' in dm:
        return 'فروش'
    return 'فروش'


def merged_properties_transaction_type(properties: Iterable) -> str:
    modes = {property_deal_to_transaction_type(getattr(p, 'deal_mode', '')) for p in properties}
    modes.discard('')
    if {'فروش', 'اجاره'} <= modes:
        return 'ترکیبی'
    if modes == {'اجاره'}:
        return 'اجاره'
    return 'فروش'


def crm_map_filter_querystring(params) -> str:
    """Querystring فیلترهای لیست فایل شخصی برای لینک نقشه / بازگشت."""
    items = getattr(params, 'items', None)
    pairs = items() if callable(items) else list(dict(params).items())
    skip = {'view', 'page', 'drawer', 'partial', 'sort'}
    return urlencode([
        (k, v) for k, v in pairs
        if k not in skip and str(v or '').strip()
    ])


def crm_map_filter_count(params) -> int:
    get = params.get if hasattr(params, 'get') else dict(params).get
    return sum(1 for key in CRM_MAP_FILTER_KEYS if str(get(key) or '').strip())


def _property_image_urls(prop) -> List[str]:
    raw = getattr(prop, 'images', None)
    if not isinstance(raw, list):
        return []
    urls: List[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            urls.append(item.strip())
        elif isinstance(item, dict):
            url = str(item.get('url') or item.get('src') or '').strip()
            if url:
                urls.append(url)
    return urls


def _property_feature_data(prop) -> Dict[str, Any]:
    data = dict(getattr(prop, 'feature_data', None) or {})
    phone = (getattr(prop, 'phone', None) or '').strip()
    if phone:
        data.setdefault('شماره تماس', phone)
        data.setdefault('phone', phone)
    for attr, label in _BOOL_FEATURE_LABELS:
        if getattr(prop, attr, False):
            data.setdefault(label, 'دارد')
    build_year = getattr(prop, 'build_year', None)
    if build_year:
        data.setdefault('سال ساخت', build_year)
    rooms = (getattr(prop, 'rooms', None) or '').strip()
    if rooms:
        data.setdefault('اتاق', rooms)
    if getattr(prop, 'is_vacant', False):
        data.setdefault('وضعیت سکونت', 'تخلیه')
    return data


def crm_property_as_listing(prop) -> SimpleNamespace:
    """آداپتور فایل شخصی به شکل Listing تا `map_markers` بدون تغییر reuse شود."""
    tx_type = property_deal_to_transaction_type(getattr(prop, 'deal_mode', ''))
    price = getattr(prop, 'sale_price', None) or 0
    area = getattr(prop, 'area', None) or 0
    pps = (float(price) / float(area)) if price and area else 0
    return SimpleNamespace(
        pk=prop.pk,
        id=prop.pk,
        latitude=prop.latitude,
        longitude=prop.longitude,
        title=prop.title,
        price=prop.sale_price,
        deposit=prop.deposit,
        rent=prop.monthly_rent,
        area=prop.area,
        rooms=prop.rooms or '',
        neighborhood=prop.neighborhood or '',
        city=prop.city or '',
        business_type=prop.business_type or '',
        published_at=getattr(prop, 'created_at', None),
        token=prop.token or '',
        link=prop.link or '',
        images=_property_image_urls(prop),
        data=_property_feature_data(prop),
        description=prop.notes or '',
        price_per_sqm=pps,
        dataset_id=None,
        dataset=SimpleNamespace(transaction_type=tx_type),
        transaction_type=tx_type,
        advertiser_signal='',
    )


def crm_properties_map_markers(
    properties,
    *,
    transaction_type: str = '',
) -> List[Dict[str, Any]]:
    """همان payload مارکر Map Pro فایلینگ، با URL جزئیات فایل شخصی."""
    props = [p for p in properties if getattr(p, 'latitude', None) and getattr(p, 'longitude', None)]
    listing_likes = [crm_property_as_listing(p) for p in props]
    markers = map_markers(listing_likes, transaction_type=transaction_type)
    by_id = {p.pk: p for p in props}
    for marker in markers:
        prop = by_id.get(marker.get('id'))
        if not prop:
            continue
        marker['platform_url'] = reverse(
            'workspace:crm_property_detail',
            kwargs={'property_id': prop.pk},
        )
        adv = property_advertiser_display(prop.business_type)
        signal = adv.get('signal') or ''
        marker['seller_type'] = adv.get('label') or marker.get('seller_type') or 'شخصی'
        marker['advertiser_signal'] = signal
        marker['is_consultant'] = signal == ADVERTISER_SIGNAL_CONSULTANT
        marker['is_disguised'] = signal == ADVERTISER_SIGNAL_DISGUISED
        marker['business_type'] = prop.business_type or marker.get('business_type') or ''
    return markers


def _server_filters_for_map_config(params) -> Dict[str, Any]:
    get = params.get if hasattr(params, 'get') else dict(params).get
    filters: Dict[str, Any] = {}
    for key in CRM_MAP_FILTER_KEYS:
        val = get(key)
        if val not in ('', None):
            filters[key] = val
    return filters


def build_crm_properties_map_context(request) -> Dict[str, Any]:
    """Context همان صفحه `workspace/map/index.html` با منبع CRMProperty."""
    settings = get_or_create_settings(request.user)
    filtered_qs = filter_properties(request.user, request.GET)
    geo_qs = filtered_qs.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
    geo_count = geo_qs.count()
    sampled = list(geo_qs[:MAP_MARKER_LIMIT])
    transaction_type = merged_properties_transaction_type(sampled) if sampled else 'فروش'
    markers = crm_properties_map_markers(sampled, transaction_type=transaction_type)
    tx = transaction_profile(transaction_type)
    is_rent_only = bool(tx['is_rent'] and not tx['is_sale'] and not tx['is_mixed'])
    filter_value_label = 'رهن کامل' if is_rent_only else 'قیمت'
    show_tx_filter = bool(tx.get('is_mixed'))
    neighborhoods = get_neighborhoods_qs(geo_qs)
    cities = sorted({
        (p.city or '').strip()
        for p in sampled
        if (p.city or '').strip()
    })
    city_label = cities[0] if len(cities) == 1 else ''
    filter_qs = crm_map_filter_querystring(request.GET)
    filter_count = crm_map_filter_count(request.GET)
    back_url = reverse('workspace:crm_properties')
    if filter_qs:
        back_url = f'{back_url}?{filter_qs}'
    map_title = 'فایل‌های شخصی'
    map_config = {
        'cartoBasemapKey': get_carto_basemap_api_key(),
        'map_cluster': settings.map_cluster,
        'map_heatmap': settings.map_heatmap,
        'focusMaxZoom': 17,
        'clusterDisableZoom': 15,
        'mapModes': True,
        'datasetName': map_title,
        'datasetCity': city_label,
        'is_rent': is_rent_only,
        'is_mixed': bool(tx.get('is_mixed')),
        'show_price': bool(tx.get('show_price')),
        'show_deposit': bool(tx.get('show_deposit')),
        'show_rent': bool(tx.get('show_rent')),
        'show_tx_filter': show_tx_filter,
        'neighborhoods': neighborhoods,
        'filters': _server_filters_for_map_config(request.GET),
        'filter_value_label': filter_value_label,
        'filterValueLabel': filter_value_label,
        'is_multi': False,
        'filter_count': filter_count,
        'is_crm_map': True,
    }
    consultant_count = sum(1 for m in markers if m.get('is_consultant'))
    disguised_count = sum(1 for m in markers if m.get('is_disguised'))
    genuine_count = max(0, len(markers) - consultant_count - disguised_count)
    return {
        'dataset': SimpleNamespace(
            id=None,
            name=map_title,
            city=city_label,
            district='',
        ),
        'datasets': [],
        'dataset_count': 0,
        'dataset_ids_param': '',
        'is_crm_map': True,
        'map_kicker': 'نقشه فایل‌های شخصی',
        'map_back_title': 'بازگشت به فایل‌های شخصی',
        'map_empty_desc': 'فایل‌های شخصی فیلد عرض/طول جغرافیایی ندارند.',
        'map_empty_back_label': 'بازگشت به فایل‌های شخصی',
        'map_title': map_title,
        'map_back_url': back_url,
        'map_filter_qs': filter_qs,
        'filters': map_config['filters'],
        'filter_count': filter_count,
        'is_map_filtered': filter_count > 0,
        'is_multi_map': False,
        'markers': markers,
        'markers_json': json.dumps(markers, ensure_ascii=False),
        'map_config': map_config,
        'map_config_json': json.dumps(map_config, ensure_ascii=False),
        'geo_count': geo_count,
        'markers_shown': len(markers),
        'markers_truncated': geo_count > MAP_MARKER_LIMIT,
        'consultant_count': consultant_count,
        'disguised_consultant_count': disguised_count,
        'genuine_personal_count': genuine_count,
        'personal_count': genuine_count + disguised_count,
        'ws_settings': settings,
    }
