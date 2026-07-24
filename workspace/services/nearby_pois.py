"""امکانات اطراف فایل شخصی CRM — Overpass/OSM با کش و محدودیت روزانه."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from workspace.services.jalali_input import format_jalali_datetime, to_persian_digits
from workspace.services.listing_map import parse_map_coordinates

logger = logging.getLogger(__name__)

PAYLOAD_VERSION = 4

DEFAULT_OVERPASS_URLS = (
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
)

POI_GROUPS: Tuple[Dict[str, str], ...] = (
    {'key': 'transport', 'label': 'دسترسی و حمل‌ونقل'},
    {'key': 'daily', 'label': 'زندگی روزمره'},
    {'key': 'health', 'label': 'درمان و سلامت'},
    {'key': 'education', 'label': 'آموزش'},
    {'key': 'religion', 'label': 'مذهبی'},
    {'key': 'leisure', 'label': 'تفریح و ورزش'},
    {'key': 'safety', 'label': 'امنیت و خدمات'},
)

POI_CATEGORIES: Tuple[Dict[str, Any], ...] = (
    {
        'key': 'metro', 'group': 'transport', 'label': 'مترو', 'icon': 'fa-train-subway',
        'color': '#7c3aed', 'fallback_name': 'ایستگاه مترو',
        'match': (
            {'railway': 'station', 'station': 'subway'},
            {'public_transport': 'station', 'subway': 'yes'},
            {'railway': 'station', 'subway': 'yes'},
        ),
        'overpass': (
            'nwr["railway"="station"]["station"="subway"]',
            'nwr["public_transport"="station"]["subway"="yes"]',
        ),
    },
    {
        'key': 'bus', 'group': 'transport', 'label': 'اتوبوس', 'icon': 'fa-bus',
        'color': '#2563eb', 'fallback_name': 'ایستگاه اتوبوس',
        'match': ({'highway': 'bus_stop'},),
        'overpass': ('nwr["highway"="bus_stop"]',),
    },
    {
        'key': 'motorway', 'group': 'transport', 'label': 'بزرگراه', 'icon': 'fa-road',
        'color': '#1e3a8a', 'fallback_name': 'بزرگراه / آزادراه',
        'match': (
            {'highway': 'motorway'},
            {'highway': 'motorway_link'},
        ),
        'overpass': (
            'nwr["highway"="motorway"]',
            'nwr["highway"="motorway_link"]',
        ),
    },
    {
        'key': 'main_road', 'group': 'transport', 'label': 'معبر اصلی', 'icon': 'fa-road-circle-check',
        'color': '#1d4ed8', 'fallback_name': 'خیابان / جاده اصلی',
        'match': (
            {'highway': 'trunk'},
            {'highway': 'primary'},
            {'highway': 'secondary'},
        ),
        'overpass': (
            'nwr["highway"="trunk"]',
            'nwr["highway"="primary"]',
            'nwr["highway"="secondary"]',
        ),
    },
    {
        'key': 'street_type', 'group': 'transport', 'label': 'نوع معبر', 'icon': 'fa-road-barrier',
        'color': '#475569', 'fallback_name': 'معبر',
        'kind': 'street',
        'overpass': (),
    },
    {
        'key': 'supermarket', 'group': 'daily', 'label': 'سوپرمارکت', 'icon': 'fa-cart-shopping',
        'color': '#0891b2', 'fallback_name': 'فروشگاه',
        'match': ({'shop': 'supermarket'}, {'shop': 'convenience'}, {'shop': 'general'}),
        'overpass': (
            'nwr["shop"="supermarket"]',
            'nwr["shop"="convenience"]',
        ),
    },
    {
        'key': 'bakery', 'group': 'daily', 'label': 'نانوایی', 'icon': 'fa-bread-slice',
        'color': '#ca8a04', 'fallback_name': 'نانوایی',
        'match': ({'shop': 'bakery'},),
        'overpass': ('nwr["shop"="bakery"]',),
    },
    {
        'key': 'bank', 'group': 'daily', 'label': 'بانک', 'icon': 'fa-building-columns',
        'color': '#0369a1', 'fallback_name': 'بانک',
        'match': ({'amenity': 'bank'},),
        'overpass': ('nwr["amenity"="bank"]',),
    },
    {
        'key': 'atm', 'group': 'daily', 'label': 'عابر بانک', 'icon': 'fa-money-bill-wave',
        'color': '#0284c7', 'fallback_name': 'عابر بانک',
        'match': ({'amenity': 'atm'},),
        'overpass': ('nwr["amenity"="atm"]',),
    },
    {
        'key': 'fuel', 'group': 'daily', 'label': 'پمپ بنزین', 'icon': 'fa-gas-pump',
        'color': '#c2410c', 'fallback_name': 'پمپ بنزین',
        'match': ({'amenity': 'fuel'},),
        'overpass': ('nwr["amenity"="fuel"]',),
    },
    {
        'key': 'parking', 'group': 'daily', 'label': 'پارکینگ عمومی', 'icon': 'fa-square-parking',
        'color': '#4f46e5', 'fallback_name': 'پارکینگ',
        'match': ({'amenity': 'parking'},),
        'exclude_match': (
            {'access': 'private'},
            {'parking': 'private'},
            {'access': 'customers'},
        ),
        'overpass': ('nwr["amenity"="parking"]',),
    },
    {
        'key': 'cafe', 'group': 'daily', 'label': 'کافه', 'icon': 'fa-mug-saucer',
        'color': '#a16207', 'fallback_name': 'کافه',
        'match': ({'amenity': 'cafe'}, {'amenity': 'ice_cream'}),
        'overpass': (
            'nwr["amenity"="cafe"]',
            'nwr["amenity"="ice_cream"]',
        ),
    },
    {
        'key': 'restaurant', 'group': 'daily', 'label': 'رستوران', 'icon': 'fa-utensils',
        'color': '#b45309', 'fallback_name': 'رستوران',
        'match': (
            {'amenity': 'restaurant'},
            {'amenity': 'fast_food'},
            {'amenity': 'food_court'},
        ),
        'overpass': (
            'nwr["amenity"="restaurant"]',
            'nwr["amenity"="fast_food"]',
        ),
    },
    {
        'key': 'pharmacy', 'group': 'health', 'label': 'داروخانه', 'icon': 'fa-prescription-bottle-medical',
        'color': '#db2777', 'fallback_name': 'داروخانه',
        'match': ({'amenity': 'pharmacy'},),
        'overpass': ('nwr["amenity"="pharmacy"]',),
    },
    {
        'key': 'hospital', 'group': 'health', 'label': 'بیمارستان', 'icon': 'fa-hospital',
        'color': '#dc2626', 'fallback_name': 'بیمارستان',
        'match': ({'amenity': 'hospital'}, {'healthcare': 'hospital'}),
        'overpass': ('nwr["amenity"="hospital"]',),
    },
    {
        'key': 'clinic', 'group': 'health', 'label': 'کلینیک', 'icon': 'fa-stethoscope',
        'color': '#e11d48', 'fallback_name': 'کلینیک / درمانگاه',
        'match': (
            {'amenity': 'clinic'},
            {'healthcare': 'clinic'},
            {'amenity': 'doctors'},
        ),
        'overpass': (
            'nwr["amenity"="clinic"]',
            'nwr["amenity"="doctors"]',
        ),
    },
    {
        'key': 'school', 'group': 'education', 'label': 'مدرسه', 'icon': 'fa-school',
        'color': '#d97706', 'fallback_name': 'مدرسه',
        'match': ({'amenity': 'school'}, {'amenity': 'kindergarten'}),
        'overpass': (
            'nwr["amenity"="school"]',
            'nwr["amenity"="kindergarten"]',
        ),
    },
    {
        'key': 'university', 'group': 'education', 'label': 'دانشگاه', 'icon': 'fa-graduation-cap',
        'color': '#9333ea', 'fallback_name': 'دانشگاه',
        'match': ({'amenity': 'university'}, {'amenity': 'college'}),
        'overpass': (
            'nwr["amenity"="university"]',
            'nwr["amenity"="college"]',
        ),
    },
    {
        'key': 'mosque', 'group': 'religion', 'label': 'مسجد', 'icon': 'fa-mosque',
        'color': '#0d9488', 'fallback_name': 'مسجد',
        'match': (
            {'amenity': 'place_of_worship', 'religion': 'muslim'},
            {'building': 'mosque'},
            {'amenity': 'mosque'},
        ),
        'overpass': (
            'nwr["amenity"="place_of_worship"]["religion"="muslim"]',
            'nwr["building"="mosque"]',
        ),
    },
    {
        'key': 'park', 'group': 'leisure', 'label': 'پارک', 'icon': 'fa-tree',
        'color': '#059669', 'fallback_name': 'پارک',
        'match': ({'leisure': 'park'}, {'leisure': 'garden'}),
        'overpass': ('nwr["leisure"="park"]', 'nwr["leisure"="garden"]'),
    },
    {
        'key': 'gym', 'group': 'leisure', 'label': 'باشگاه ورزشی', 'icon': 'fa-dumbbell',
        'color': '#ea580c', 'fallback_name': 'باشگاه',
        'match': (
            {'leisure': 'fitness_centre'},
            {'leisure': 'sports_centre'},
            {'sport': 'multi'},
        ),
        'overpass': (
            'nwr["leisure"="fitness_centre"]',
            'nwr["leisure"="sports_centre"]',
        ),
    },
    {
        'key': 'mall', 'group': 'leisure', 'label': 'مرکز خرید', 'icon': 'fa-bag-shopping',
        'color': '#be185d', 'fallback_name': 'مرکز خرید',
        'match': ({'shop': 'mall'}, {'amenity': 'marketplace'}),
        'overpass': (
            'nwr["shop"="mall"]',
            'nwr["amenity"="marketplace"]',
        ),
    },
    {
        'key': 'police', 'group': 'safety', 'label': 'کلانتری', 'icon': 'fa-shield-halved',
        'color': '#1d4ed8', 'fallback_name': 'کلانتری',
        'match': ({'amenity': 'police'},),
        'overpass': ('nwr["amenity"="police"]',),
    },
    {
        'key': 'fire_station', 'group': 'safety', 'label': 'آتش‌نشانی', 'icon': 'fa-fire-extinguisher',
        'color': '#b45309', 'fallback_name': 'آتش‌نشانی',
        'match': ({'amenity': 'fire_station'},),
        'overpass': ('nwr["amenity"="fire_station"]',),
    },
)

_GROUP_LABELS = {g['key']: g['label'] for g in POI_GROUPS}


class NearbyPoiError(Exception):
    """خطای کنترل‌شده امکانات اطراف."""

    def __init__(self, code: str, message: str, *, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


@dataclass(frozen=True)
class NearbyPoiItem:
    key: str
    group: str
    group_label: str
    label: str
    icon: str
    color: str
    found: bool
    name: str = ''
    distance_m: Optional[int] = None
    distance_label: str = ''
    walk_label: str = ''
    empty_label: str = ''

    def as_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'group': self.group,
            'group_label': self.group_label,
            'label': self.label,
            'icon': self.icon,
            'color': self.color,
            'found': self.found,
            'name': self.name,
            'distance_m': self.distance_m,
            'distance_label': self.distance_label,
            'walk_label': self.walk_label,
            'empty_label': self.empty_label,
        }


def _search_radius_m() -> int:
    return int(getattr(settings, 'NEARBY_POI_SEARCH_RADIUS_M', 3000))


def _street_type_radius_m() -> int:
    return int(getattr(settings, 'NEARBY_POI_STREET_RADIUS_M', 120))


HIGHWAY_TYPE_LABELS: Dict[str, str] = {
    'motorway': 'بزرگراه',
    'motorway_link': 'رابط بزرگراه',
    'trunk': 'جاده اصلی',
    'primary': 'خیابان اصلی',
    'primary_link': 'رابط خیابان اصلی',
    'secondary': 'خیابان فرعی مهم',
    'secondary_link': 'رابط خیابان فرعی',
    'tertiary': 'خیابان محلی',
    'tertiary_link': 'رابط محلی',
    'residential': 'کوچه مسکونی',
    'living_street': 'کوچه مسکونی',
    'unclassified': 'معبر محلی',
    'service': 'کوچه/service',
    'road': 'معبر',
    'track': 'مسیر دسترسی',
}

SKIP_STREET_HIGHWAY = frozenset({
    'footway', 'path', 'steps', 'cycleway', 'pedestrian', 'bridleway',
    'corridor', 'elevator', 'proposed', 'construction', 'bus_guideway',
})


def _overpass_timeout() -> int:
    return int(getattr(settings, 'NEARBY_POI_OVERPASS_TIMEOUT', 30))


def _overpass_urls() -> Sequence[str]:
    urls = getattr(settings, 'NEARBY_POI_OVERPASS_URLS', None)
    if urls:
        return tuple(urls)
    return DEFAULT_OVERPASS_URLS


def _coords_key(lat: float, lng: float) -> Tuple[float, float]:
    return round(float(lat), 6), round(float(lng), 6)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def format_distance_label(distance_m: float) -> str:
    dist = max(0, int(round(distance_m)))
    if dist < 1000:
        return f'{to_persian_digits(dist)} متر'
    km = dist / 1000.0
    if km < 10:
        label = f'{km:.1f}'.rstrip('0').rstrip('.')
    else:
        label = str(int(round(km)))
    return f'{to_persian_digits(label)} کیلومتر'


def estimate_walk_label(distance_m: Optional[float]) -> str:
    if distance_m is None or distance_m <= 0:
        return ''
    minutes = max(1, int(round(float(distance_m) / 80.0)))
    if minutes > 45:
        return ''
    return f'حدود {to_persian_digits(minutes)} دقیقه پیاده'


def _radius_empty_label(radius_m: int) -> str:
    if radius_m >= 1000:
        km = radius_m / 1000.0
        if km == int(km):
            return f'در شعاع {to_persian_digits(int(km))} کیلومتر یافت نشد'
        return f'در شعاع {to_persian_digits(km)} کیلومتر یافت نشد'
    return f'در شعاع {to_persian_digits(radius_m)} متر یافت نشد'


def _element_coords(element: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    if element.get('lat') is not None and element.get('lon') is not None:
        return float(element['lat']), float(element['lon'])
    center = element.get('center') or {}
    if center.get('lat') is not None and center.get('lon') is not None:
        return float(center['lat']), float(center['lon'])
    return None


def _tags_match(tags: Dict[str, str], required: Dict[str, str]) -> bool:
    return all(tags.get(k) == v for k, v in required.items())


def _element_matches_category(tags: Dict[str, str], category: Dict[str, Any]) -> bool:
    for rule in category.get('exclude_match') or ():
        if _tags_match(tags, rule):
            return False
    for rule in category.get('match') or ():
        if _tags_match(tags, rule):
            return True
    return False


def _highway_type_label(highway: str) -> str:
    return HIGHWAY_TYPE_LABELS.get(highway or '', 'معبر')


def _parse_width_m(raw: str) -> Optional[int]:
    text = (raw or '').strip().lower().replace(',', '.')
    if not text:
        return None
    for suffix in (' m', 'm', ' meters', ' metre', ' metres'):
        if text.endswith(suffix):
            text = text[:-len(suffix)].strip()
            break
    try:
        val = float(text)
    except ValueError:
        return None
    if val <= 0 or val > 200:
        return None
    return int(round(val))


def _street_width_label(tags: Dict[str, str]) -> str:
    for key in ('width', 'est_width'):
        parsed = _parse_width_m(str(tags.get(key) or ''))
        if parsed:
            return f'عرض {to_persian_digits(parsed)} متر'
    lanes = tags.get('lanes')
    if lanes and str(lanes).isdigit():
        n = int(lanes)
        if 1 <= n <= 8:
            return f'{to_persian_digits(n)} لاین'
    return ''


def _street_type_name(tags: Dict[str, str]) -> str:
    highway = (tags.get('highway') or '').strip()
    base = _highway_type_label(highway)
    width_part = _street_width_label(tags)
    if width_part:
        return f'{base} · {width_part}'
    return base


def _resolve_street_type_item(
    lat: float,
    lng: float,
    elements: Sequence[Dict[str, Any]],
    category: Dict[str, Any],
) -> NearbyPoiItem:
    group_key = category['group']
    street_radius = _street_type_radius_m()
    empty_label = _radius_empty_label(street_radius)
    best_dist = float('inf')
    best_tags: Dict[str, str] = {}

    for element in elements:
        tags = element.get('tags') or {}
        highway = (tags.get('highway') or '').strip()
        if not highway or highway in SKIP_STREET_HIGHWAY:
            continue
        coords = _element_coords(element)
        if not coords:
            continue
        el_lat, el_lng = coords
        dist = haversine_m(lat, lng, el_lat, el_lng)
        if dist > street_radius or dist >= best_dist:
            continue
        best_dist = dist
        best_tags = tags

    if best_dist == float('inf'):
        return NearbyPoiItem(
            key=category['key'],
            group=group_key,
            group_label=_GROUP_LABELS.get(group_key, group_key),
            label=category['label'],
            icon=category['icon'],
            color=category['color'],
            found=False,
            empty_label=empty_label,
        )

    dist_m = int(round(best_dist))
    name = _street_type_name(best_tags)
    dist_label = 'جلوی ملک' if dist_m <= 20 else format_distance_label(best_dist)
    return NearbyPoiItem(
        key=category['key'],
        group=group_key,
        group_label=_GROUP_LABELS.get(group_key, group_key),
        label=category['label'],
        icon=category['icon'],
        color=category['color'],
        found=True,
        name=name,
        distance_m=dist_m,
        distance_label=dist_label,
        walk_label=estimate_walk_label(best_dist) if dist_m > 20 else '',
    )


def _element_name(tags: Dict[str, str], fallback: str) -> str:
    for key in ('name:fa', 'name', 'brand:fa', 'brand', 'operator'):
        val = (tags.get(key) or '').strip()
        if val:
            return val
    return fallback


def build_overpass_query(lat: float, lng: float, *, radius_m: Optional[int] = None) -> str:
    radius = radius_m or _search_radius_m()
    selectors: List[str] = []
    seen = set()
    for category in POI_CATEGORIES:
        for selector in category.get('overpass') or ():
            if selector in seen:
                continue
            seen.add(selector)
            selectors.append(f'  {selector}(around:{radius},{lat},{lng});')
    street_r = _street_type_radius_m()
    street_sel = f'way["highway"](around:{street_r},{lat},{lng});'
    if street_sel not in seen:
        selectors.append(f'  {street_sel}')
    body = '\n'.join(selectors)
    timeout = _overpass_timeout()
    return (
        f'[out:json][timeout:{timeout}];\n'
        f'(\n{body}\n);\n'
        'out center tags;'
    )


def fetch_overpass_elements(lat: float, lng: float, *, radius_m: Optional[int] = None) -> List[Dict[str, Any]]:
    query = build_overpass_query(lat, lng, radius_m=radius_m)
    headers = {'User-Agent': 'DivarFilingCRM/1.0 (nearby-pois; contact@divarfiling.local)'}
    last_error: Optional[Exception] = None

    for base_url in _overpass_urls():
        try:
            resp = requests.post(
                base_url,
                data={'data': query},
                headers=headers,
                timeout=_overpass_timeout() + 5,
            )
            if resp.status_code == 429:
                raise NearbyPoiError(
                    'service_busy',
                    'سرویس نقشه الان شلوغ است. لطفاً چند دقیقه بعد دوباره تلاش کنید.',
                    status=503,
                )
            if resp.status_code in (502, 503, 504):
                raise NearbyPoiError(
                    'service_unavailable',
                    'سرویس نقشه در دسترس نیست. لطفاً بعداً دوباره تلاش کنید.',
                    status=503,
                )
            resp.raise_for_status()
            payload = resp.json()
            elements = payload.get('elements') or []
            if not isinstance(elements, list):
                raise ValueError('پاسخ Overpass نامعتبر است')
            return elements
        except NearbyPoiError:
            raise
        except requests.Timeout as exc:
            last_error = exc
            logger.warning('Overpass timeout on %s', base_url)
            continue
        except requests.RequestException as exc:
            last_error = exc
            logger.warning('Overpass request failed on %s: %s', base_url, exc)
            continue

    if isinstance(last_error, requests.Timeout):
        raise NearbyPoiError(
            'service_busy',
            'پاسخ سرویس نقشه طول کشید. لطفاً چند دقیقه بعد دوباره تلاش کنید.',
            status=504,
        )
    raise NearbyPoiError(
        'service_unavailable',
        'سرویس نقشه در دسترس نیست. لطفاً بعداً دوباره تلاش کنید.',
        status=503,
    )


def resolve_nearby_items(
    lat: float,
    lng: float,
    elements: Sequence[Dict[str, Any]],
    *,
    radius_m: Optional[int] = None,
) -> List[NearbyPoiItem]:
    radius = radius_m or _search_radius_m()
    empty_label = _radius_empty_label(radius)
    items: List[NearbyPoiItem] = []

    for category in POI_CATEGORIES:
        group_key = category['group']
        if category.get('kind') == 'street':
            items.append(_resolve_street_type_item(lat, lng, elements, category))
            continue

        best_dist = float('inf')
        best_name = ''
        for element in elements:
            tags = element.get('tags') or {}
            if not _element_matches_category(tags, category):
                continue
            coords = _element_coords(element)
            if not coords:
                continue
            el_lat, el_lng = coords
            dist = haversine_m(lat, lng, el_lat, el_lng)
            if dist > radius or dist >= best_dist:
                continue
            best_dist = dist
            best_name = _element_name(tags, category['fallback_name'])

        if best_dist == float('inf'):
            items.append(NearbyPoiItem(
                key=category['key'],
                group=group_key,
                group_label=_GROUP_LABELS.get(group_key, group_key),
                label=category['label'],
                icon=category['icon'],
                color=category['color'],
                found=False,
                empty_label=empty_label,
            ))
        else:
            dist_m = int(round(best_dist))
            items.append(NearbyPoiItem(
                key=category['key'],
                group=group_key,
                group_label=_GROUP_LABELS.get(group_key, group_key),
                label=category['label'],
                icon=category['icon'],
                color=category['color'],
                found=True,
                name=best_name,
                distance_m=dist_m,
                distance_label=format_distance_label(best_dist),
                walk_label=estimate_walk_label(best_dist),
            ))
    return items


def group_nearby_items(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """گروه‌بندی آیتم‌ها برای UI — فقط گروه‌های دارای آیتم."""
    by_group: Dict[str, List[Dict[str, Any]]] = {g['key']: [] for g in POI_GROUPS}
    for item in items:
        group_key = item.get('group') or 'daily'
        by_group.setdefault(group_key, []).append(item)

    groups: List[Dict[str, Any]] = []
    for group in POI_GROUPS:
        group_items = by_group.get(group['key']) or []
        if not group_items:
            continue
        found = [i for i in group_items if i.get('found')]
        missing = [i for i in group_items if not i.get('found')]
        found.sort(key=lambda x: x.get('distance_m') or 999999)
        groups.append({
            'key': group['key'],
            'label': group['label'],
            'found_count': len(found),
            'items': found + missing,
        })
    return groups


def nearest_highlights(items: Sequence[Dict[str, Any]], *, limit: int = 3) -> List[Dict[str, Any]]:
    found = [i for i in items if i.get('found')]
    found.sort(key=lambda x: x.get('distance_m') or 999999)
    return found[:limit]


def resolve_nearby_pois(lat: float, lng: float, *, radius_m: Optional[int] = None) -> Dict[str, Any]:
    elements = fetch_overpass_elements(lat, lng, radius_m=radius_m)
    items = resolve_nearby_items(lat, lng, elements, radius_m=radius_m)
    now = timezone.now()
    return _build_payload(lat, lng, items, fetched_at=now, radius_m=radius_m or _search_radius_m())


def _build_payload(
    lat: float,
    lng: float,
    items: Sequence[NearbyPoiItem],
    *,
    fetched_at,
    radius_m: int,
) -> Dict[str, Any]:
    lat_key, lng_key = _coords_key(lat, lng)
    item_dicts = [item.as_dict() for item in items]
    found_count = sum(1 for item in items if item.found)
    return {
        'version': PAYLOAD_VERSION,
        'fetched_at': fetched_at.isoformat(),
        'fetched_at_label': format_jalali_datetime(fetched_at),
        'coords': {'lat': lat_key, 'lng': lng_key},
        'radius_m': radius_m,
        'items': item_dicts,
        'groups': group_nearby_items(item_dicts),
        'highlights': nearest_highlights(item_dicts),
        'found_count': found_count,
        'total_count': len(item_dicts),
        'missing_count': len(item_dicts) - found_count,
    }


def stored_nearby_pois_valid(prop, *, radius_m: Optional[int] = None) -> bool:
    data = getattr(prop, 'nearby_pois', None) or {}
    if not isinstance(data, dict) or not data.get('items'):
        return False
    if int(data.get('version') or 1) < PAYLOAD_VERSION:
        return False
    coords = data.get('coords') or {}
    lat = getattr(prop, 'latitude', None)
    lng = getattr(prop, 'longitude', None)
    if lat is None or lng is None:
        return False
    lat_key, lng_key = _coords_key(lat, lng)
    if coords.get('lat') != lat_key or coords.get('lng') != lng_key:
        return False
    expected_radius = radius_m or _search_radius_m()
    stored_radius = data.get('radius_m')
    if stored_radius and int(stored_radius) != int(expected_radius):
        return False
    return True


def get_stored_nearby_pois_payload(prop) -> Optional[Dict[str, Any]]:
    if not stored_nearby_pois_valid(prop):
        return None
    data = dict(prop.nearby_pois or {})
    if not data.get('groups'):
        data['groups'] = group_nearby_items(data.get('items') or [])
    if not data.get('highlights'):
        data['highlights'] = nearest_highlights(data.get('items') or [])
    data['cached'] = True
    return data


def _cache_day_key(prefix: str, *, day: Optional[date] = None) -> str:
    day = day or timezone.localdate()
    return f'{prefix}:{day.isoformat()}'


def _user_daily_limit() -> int:
    return int(getattr(settings, 'NEARBY_POI_USER_DAILY_LIMIT', 25))


def _global_daily_limit() -> int:
    return int(getattr(settings, 'NEARBY_POI_GLOBAL_DAILY_LIMIT', 400))


def check_rate_limits(user) -> None:
    user_key = _cache_day_key(f'nearby_poi:user:{user.pk}')
    global_key = _cache_day_key('nearby_poi:global')
    user_count = cache.get(user_key, 0) or 0
    global_count = cache.get(global_key, 0) or 0

    if user_count >= _user_daily_limit():
        raise NearbyPoiError(
            'user_limit',
            'امروز سقف درخواست امکانات و دسترسی‌ها برای حساب شما پر شده است. فردا دوباره امتحان کنید.',
            status=429,
        )
    if global_count >= _global_daily_limit():
        raise NearbyPoiError(
            'global_limit',
            'سرویس نقشه الان شلوغ است. لطفاً چند دقیقه بعد دوباره تلاش کنید.',
            status=503,
        )


def increment_rate_limits(user) -> None:
    ttl = 60 * 60 * 30
    user_key = _cache_day_key(f'nearby_poi:user:{user.pk}')
    global_key = _cache_day_key('nearby_poi:global')
    try:
        cache.incr(user_key)
    except ValueError:
        cache.set(user_key, 1, ttl)
    try:
        cache.incr(global_key)
    except ValueError:
        cache.set(global_key, 1, ttl)


def api_response_payload(data: Dict[str, Any], *, cached: bool) -> Dict[str, Any]:
    items = data.get('items') or []
    return {
        'ok': True,
        'cached': cached,
        'fetched_at': data.get('fetched_at'),
        'fetched_at_label': data.get('fetched_at_label'),
        'radius_m': data.get('radius_m'),
        'found_count': data.get('found_count', 0),
        'total_count': data.get('total_count', len(items)),
        'missing_count': data.get('missing_count', 0),
        'items': items,
        'groups': data.get('groups') or group_nearby_items(items),
        'highlights': data.get('highlights') or nearest_highlights(items),
    }


def fetch_and_save_nearby_pois(prop, user, *, force_refresh: bool = False) -> Dict[str, Any]:
    lat, lng, error = parse_map_coordinates(prop.latitude, prop.longitude)
    if error:
        raise NearbyPoiError(
            'no_coords',
            'برای این ملک هنوز موقعیت روی نقشه ثبت نشده است.',
            status=400,
        )

    if not force_refresh:
        cached = get_stored_nearby_pois_payload(prop)
        if cached:
            return api_response_payload(cached, cached=True)

    check_rate_limits(user)
    payload = resolve_nearby_pois(lat, lng)
    increment_rate_limits(user)
    prop.nearby_pois = payload
    prop.save(update_fields=['nearby_pois', 'updated_at'])
    return api_response_payload(payload, cached=False)


def clear_nearby_pois(prop) -> None:
    if prop.nearby_pois:
        prop.nearby_pois = {}
        prop.save(update_fields=['nearby_pois', 'updated_at'])


def nearby_pois_page_context(prop) -> Dict[str, Any]:
    has_coords = prop.latitude is not None and prop.longitude is not None
    stored = get_stored_nearby_pois_payload(prop) if has_coords else None
    return {
        'has_coords': has_coords,
        'has_stored': bool(stored),
        'initial_payload': stored,
        'category_count': len(POI_CATEGORIES),
    }


def property_has_nearby_pois_data(prop) -> bool:
    stored = get_stored_nearby_pois_payload(prop)
    return bool(stored and int(stored.get('found_count') or 0) > 0)


def property_share_nearby_meta(prop) -> Dict[str, Any]:
    has_coords = prop.latitude is not None and prop.longitude is not None
    has_data = property_has_nearby_pois_data(prop)
    return {
        'has_coords': has_coords,
        'has_data': has_data,
        'can_enable': has_coords and has_data,
    }


def validate_share_show_nearby_pois(prop, *, enable: bool) -> Optional[str]:
    """خطای فارسی در صورت عدم امکان فعال‌سازی؛ در غیر این صورت None."""
    if not enable:
        return None
    if prop.latitude is None or prop.longitude is None:
        return 'برای نمایش امکانات و دسترسی‌ها، ابتدا موقعیت ملک را روی نقشه ثبت کنید.'
    if not property_has_nearby_pois_data(prop):
        return 'ابتدا در جزئیات فایل، دکمه «محاسبه» امکانات و دسترسی‌ها را بزنید تا داده ذخیره شود.'
    return None


def build_public_nearby_pois_context(prop, share) -> Optional[Dict[str, Any]]:
    """داده نمایش دسترسی‌های اطراف در صفحه عمومی — فقط موارد یافت‌شده."""
    if not getattr(share, 'show_nearby_pois', False):
        return None
    stored = get_stored_nearby_pois_payload(prop)
    if not stored or not int(stored.get('found_count') or 0):
        return None

    items = [i for i in (stored.get('items') or []) if i.get('found')]
    if not items:
        return None

    groups: List[Dict[str, Any]] = []
    for group in group_nearby_items(stored.get('items') or []):
        found_items = [i for i in (group.get('items') or []) if i.get('found')]
        if not found_items:
            continue
        groups.append({
            'key': group['key'],
            'label': group['label'],
            'items': found_items,
        })

    approx = bool(getattr(share, 'approximate_location', False))
    radius_m = int(stored.get('radius_m') or _search_radius_m())
    radius_label = (
        f'{to_persian_digits(radius_m // 1000)} کیلومتر'
        if radius_m >= 1000
        else f'{to_persian_digits(radius_m)} متر'
    )

    return {
        'groups': groups,
        'highlights': nearest_highlights(items, limit=4),
        'found_count': len(items),
        'fetched_at_label': stored.get('fetched_at_label') or '',
        'radius_label': radius_label,
        'approx_note': (
            'فاصله‌ها بر اساس موقعیت ملک محاسبه شده‌اند. '
            'نمایش روی نقشه ممکن است به‌صورت تقریبی باشد.'
        ) if approx else '',
        'disclaimer': 'فاصله خط مستقیم',
    }
