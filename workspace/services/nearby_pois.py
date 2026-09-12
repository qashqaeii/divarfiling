"""امکانات اطراف فایل شخصی CRM — Overpass/OSM با کش و محدودیت روزانه."""
from __future__ import annotations

import logging
import math
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from workspace.services.jalali_input import format_jalali_datetime, to_persian_digits
from workspace.services.listing_map import parse_map_coordinates

logger = logging.getLogger(__name__)

PAYLOAD_VERSION = 4

ACCESSIBILITY_STATUS_PENDING = 'pending'
ACCESSIBILITY_STATUS_READY = 'ready'
ACCESSIBILITY_STATUS_FAILED = 'failed'
ACCESSIBILITY_STATUS_UNAVAILABLE = 'unavailable'

PROPERTY_ACCESSIBILITY_RADIUS_KM = 3

DEFAULT_OVERPASS_URLS = (
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
    'https://overpass.openstreetmap.ru/api/interpreter',
    'https://overpass.private.coffee/api/interpreter',
    'https://overpass.osm.ch/api/interpreter',
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
)

_OVERPASS_IPV4_LOCK = threading.Lock()
MAX_INGEST_ELEMENTS = 8000

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

    def __init__(self, code: str, message: str, *, status: int = 400, extra: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra or {}
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


def property_accessibility_radius_m() -> int:
    """شعاع جستجوی POI — منبع واحد (پیش‌فرض ۳ کیلومتر)."""
    return _search_radius_m()


def property_accessibility_radius_km() -> int:
    return max(1, property_accessibility_radius_m() // 1000)


def accessibility_radius_label_fa(*, radius_m: Optional[int] = None) -> str:
    radius = radius_m or property_accessibility_radius_m()
    if radius >= 1000:
        km = radius // 1000
        return f'شعاع {to_persian_digits(km)} کیلومتر'
    return f'شعاع {to_persian_digits(radius)} متر'


def _accessibility_status(data: Optional[Dict[str, Any]]) -> str:
    if not isinstance(data, dict):
        return ''
    status = str(data.get('status') or '').strip()
    if status:
        return status
    if data.get('items'):
        return ACCESSIBILITY_STATUS_READY
    return ''


def resolve_property_location(prop) -> Dict[str, Any]:
    """Resolve usable map coordinates and precision metadata for a CRM property."""
    lat, lng, error = parse_map_coordinates(prop.latitude, prop.longitude)
    if error:
        return {
            'lat': None,
            'lng': None,
            'precision': 'none',
            'source': 'none',
            'usable': False,
        }

    precision, source = _resolve_location_precision_and_source(prop)
    return {
        'lat': lat,
        'lng': lng,
        'precision': precision,
        'source': source,
        'usable': True,
    }


def _resolve_location_precision_and_source(prop) -> Tuple[str, str]:
    feature_data = getattr(prop, 'feature_data', None) or {}
    stored_precision = str(
        feature_data.get('_location_precision') or feature_data.get('location_precision') or '',
    ).strip()
    stored_source = str(
        feature_data.get('_location_source') or feature_data.get('location_source') or '',
    ).strip()

    if stored_precision in ('exact', 'approximate'):
        return stored_precision, stored_source or 'listing_coordinates'

    from workspace.services.display import location_accuracy_for_map

    loc_acc = location_accuracy_for_map(feature_data)
    if loc_acc.get('kind') == 'exact':
        return 'exact', 'listing_coordinates'
    if loc_acc.get('kind') == 'approx':
        return 'approximate', 'listing_coordinates'

    source_external_id = str(getattr(prop, 'source_external_id', '') or '').strip()
    if source_external_id:
        return 'approximate', 'listing_coordinates'

    return 'exact', 'manual_pin'


def listing_location_metadata(listing) -> Dict[str, str]:
    """Metadata persisted on CRMProperty when created from a filing listing."""
    from workspace.services.display import location_accuracy_for_map

    loc_acc = location_accuracy_for_map(getattr(listing, 'data', None) or {})
    if loc_acc.get('kind') == 'exact':
        precision = 'exact'
    elif loc_acc.get('kind') == 'approx':
        precision = 'approximate'
    elif getattr(listing, 'latitude', None) is not None and getattr(listing, 'longitude', None) is not None:
        precision = 'approximate'
    else:
        precision = 'none'
    return {
        '_location_precision': precision,
        '_location_source': 'listing_coordinates',
    }


def get_property_accessibility_status(prop) -> str:
    location = resolve_property_location(prop)
    if not location['usable']:
        return ACCESSIBILITY_STATUS_UNAVAILABLE
    data = getattr(prop, 'nearby_pois', None) or {}
    status = _accessibility_status(data)
    if status:
        return status
    if stored_nearby_pois_valid(prop):
        return ACCESSIBILITY_STATUS_READY
    return ''


def _new_generation_id() -> str:
    return str(uuid.uuid4())


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except (TypeError, ValueError):
            return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def mark_property_manual_location(prop) -> None:
    """User moved pin on map — treat coordinates as exact manual placement."""
    feature_data = dict(getattr(prop, 'feature_data', None) or {})
    feature_data['_location_precision'] = 'exact'
    feature_data['_location_source'] = 'manual_pin'
    prop.feature_data = feature_data
    prop.save(update_fields=['feature_data', 'updated_at'])


def mark_property_accessibilities_pending(
    prop,
    *,
    location: Optional[Dict[str, Any]] = None,
    generation_id: Optional[str] = None,
) -> str:
    location = location or resolve_property_location(prop)
    generation_id = generation_id or _new_generation_id()
    now = timezone.now()
    prop.nearby_pois = {
        'version': PAYLOAD_VERSION,
        'status': ACCESSIBILITY_STATUS_PENDING,
        'generation_id': generation_id,
        'location_precision': location.get('precision') or 'none',
        'location_source': location.get('source') or 'none',
        'radius_m': property_accessibility_radius_m(),
        'scheduled_at': now.isoformat(),
        'scheduled_at_label': format_jalali_datetime(now),
    }
    prop.save(update_fields=['nearby_pois', 'updated_at'])
    return generation_id


def mark_property_accessibilities_unavailable(prop) -> None:
    prop.nearby_pois = {
        'version': PAYLOAD_VERSION,
        'status': ACCESSIBILITY_STATUS_UNAVAILABLE,
        'radius_m': property_accessibility_radius_m(),
    }
    prop.save(update_fields=['nearby_pois', 'updated_at'])


def mark_property_accessibilities_failed(
    prop,
    *,
    error_code: str,
    error_message: str,
    location: Optional[Dict[str, Any]] = None,
    generation_id: Optional[str] = None,
) -> None:
    if generation_id and not _generation_matches(prop, generation_id):
        return
    location = location or resolve_property_location(prop)
    now = timezone.now()
    prop.nearby_pois = {
        'version': PAYLOAD_VERSION,
        'status': ACCESSIBILITY_STATUS_FAILED,
        'generation_id': generation_id or (prop.nearby_pois or {}).get('generation_id'),
        'error_code': error_code,
        'error_message': error_message,
        'location_precision': location.get('precision') or 'none',
        'location_source': location.get('source') or 'none',
        'radius_m': property_accessibility_radius_m(),
        'failed_at': now.isoformat(),
        'failed_at_label': format_jalali_datetime(now),
    }
    prop.save(update_fields=['nearby_pois', 'updated_at'])


def _generation_matches(prop, generation_id: Optional[str]) -> bool:
    if not generation_id:
        return True
    current = getattr(prop, 'nearby_pois', None) or {}
    return str(current.get('generation_id') or '') == str(generation_id)


def _save_accessibility_payload(prop, payload: Dict[str, Any], *, generation_id: Optional[str] = None) -> bool:
    prop.refresh_from_db()
    if generation_id and not _generation_matches(prop, generation_id):
        return False
    prop.nearby_pois = payload
    prop.save(update_fields=['nearby_pois', 'updated_at'])
    return True


def schedule_property_accessibilities(
    property_id: int,
    user_id: Optional[int] = None,
    *,
    force: bool = False,
) -> Optional[str]:
    """Mark pending synchronously; enqueue durable DB job after transaction commit."""
    from workspace.models import CRMProperty
    from workspace.services.property_accessibility_jobs import (
        enqueue_property_accessibility_job,
        is_property_accessibility_pending_stale,
    )

    prop = CRMProperty.objects.filter(pk=property_id).first()
    if not prop:
        return None
    location = resolve_property_location(prop)
    if not location['usable']:
        mark_property_accessibilities_unavailable(prop)
        return None
    if not force and stored_nearby_pois_valid(prop):
        return None
    current_status = _accessibility_status(prop.nearby_pois)
    if not force and current_status == ACCESSIBILITY_STATUS_PENDING:
        if not is_property_accessibility_pending_stale(prop):
            return (prop.nearby_pois or {}).get('generation_id')
    generation_id = mark_property_accessibilities_pending(prop, location=location)

    def _after_commit() -> None:
        enqueue_property_accessibility_job(property_id, user_id, generation_id)

    transaction.on_commit(_after_commit)
    return generation_id


def refresh_property_accessibilities(
    prop,
    user,
    *,
    force_refresh: bool = False,
    elements: Optional[Sequence[Dict[str, Any]]] = None,
    generation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Single source of truth for generating and persisting property accessibilities."""
    location = resolve_property_location(prop)
    if not location['usable']:
        mark_property_accessibilities_unavailable(prop)
        raise NearbyPoiError(
            'no_coords',
            'برای این ملک هنوز موقعیت روی نقشه ثبت نشده است.',
            status=400,
        )

    if generation_id and not _generation_matches(prop, generation_id):
        cached = get_stored_nearby_pois_payload(prop)
        if cached:
            return api_response_payload(cached, cached=True)
        raise NearbyPoiError(
            'superseded',
            'محاسبه جدیدتری در حال انجام است.',
            status=409,
        )

    if not force_refresh and elements is None:
        cached = get_stored_nearby_pois_payload(prop)
        if cached:
            return api_response_payload(cached, cached=True)

    if force_refresh and elements is None and not generation_id:
        generation_id = mark_property_accessibilities_pending(prop, location=location)

    lat = location['lat']
    lng = location['lng']
    radius_m = property_accessibility_radius_m()

    try:
        check_rate_limits(user)
        if elements is not None:
            cleaned = sanitize_overpass_elements(elements)
            items = resolve_nearby_items(lat, lng, cleaned, radius_m=radius_m)
            payload = _build_payload(
                lat,
                lng,
                items,
                fetched_at=timezone.now(),
                radius_m=radius_m,
                status=ACCESSIBILITY_STATUS_READY,
                location_precision=location['precision'],
                location_source=location['source'],
                generation_id=generation_id,
            )
        else:
            overpass_elements = fetch_overpass_elements_with_retry(lat, lng, radius_m=radius_m)
            items = resolve_nearby_items(lat, lng, overpass_elements, radius_m=radius_m)
            payload = _build_payload(
                lat,
                lng,
                items,
                fetched_at=timezone.now(),
                radius_m=radius_m,
                status=ACCESSIBILITY_STATUS_READY,
                location_precision=location['precision'],
                location_source=location['source'],
                generation_id=generation_id,
            )
        increment_rate_limits(user)
    except NearbyPoiError as exc:
        mark_property_accessibilities_failed(
            prop,
            error_code=exc.code,
            error_message=exc.message,
            location=location,
            generation_id=generation_id,
        )
        raise

    if not _save_accessibility_payload(prop, payload, generation_id=generation_id):
        cached = get_stored_nearby_pois_payload(prop)
        if cached:
            return api_response_payload(cached, cached=True)
        raise NearbyPoiError(
            'superseded',
            'محاسبه جدیدتری در حال انجام است.',
            status=409,
        )
    return api_response_payload(payload, cached=False)


def property_accessibility_status_payload(prop) -> Dict[str, Any]:
    """Lightweight status for polling — never calls external providers."""
    status = get_property_accessibility_status(prop)
    data = getattr(prop, 'nearby_pois', None) or {}
    stored = get_stored_nearby_pois_payload(prop)
    if stored:
        return api_response_payload(stored, cached=True)
    location = resolve_property_location(prop)
    body: Dict[str, Any] = {
        'ok': True,
        'status': status or ACCESSIBILITY_STATUS_UNAVAILABLE,
        'location_precision': location.get('precision') or 'none',
        'radius_m': property_accessibility_radius_m(),
    }
    if status == ACCESSIBILITY_STATUS_FAILED:
        body['error_code'] = data.get('error_code') or 'failed'
        body['error_message'] = data.get('error_message') or 'محاسبه دسترسی‌ها انجام نشد.'
        if body['error_code'] in ('service_unavailable', 'service_busy') and location.get('usable'):
            body['fallback'] = overpass_client_fallback(location['lat'], location['lng'])
    if status == ACCESSIBILITY_STATUS_PENDING:
        body['message'] = 'در حال محاسبه امکانات و دسترسی‌ها…'
    return body


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


def _overpass_connect_timeout() -> float:
    return float(getattr(settings, 'NEARBY_POI_OVERPASS_CONNECT_TIMEOUT', 6))


def _force_ipv4() -> bool:
    return bool(getattr(settings, 'NEARBY_POI_FORCE_IPV4', True))


def _overpass_urls() -> Sequence[str]:
    urls = getattr(settings, 'NEARBY_POI_OVERPASS_URLS', None)
    if urls:
        cleaned = tuple(str(u).strip() for u in urls if str(u).strip())
        if cleaned:
            return cleaned
    return DEFAULT_OVERPASS_URLS


def _post_overpass(url: str, query: str, headers: Dict[str, str], timeout: Tuple[float, int]):
    """درخواست Overpass؛ روی سرورهای با IPv6 خراب فقط IPv4 امتحان می‌شود."""
    if not _force_ipv4():
        return requests.post(url, data={'data': query}, headers=headers, timeout=timeout)

    import urllib3.util.connection as urllib3_cn

    with _OVERPASS_IPV4_LOCK:
        original_family = urllib3_cn.allowed_gai_family
        urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
        try:
            return requests.post(url, data={'data': query}, headers=headers, timeout=timeout)
        finally:
            urllib3_cn.allowed_gai_family = original_family


def overpass_client_fallback(lat: float, lng: float, *, radius_m: Optional[int] = None) -> Dict[str, Any]:
    return {
        'query': build_overpass_query(lat, lng, radius_m=radius_m),
        'urls': list(_overpass_urls()),
    }


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
    timeout = (_overpass_connect_timeout(), _overpass_timeout())
    had_timeout = False
    had_busy = False

    for base_url in _overpass_urls():
        try:
            resp = _post_overpass(base_url, query, headers, timeout)
            if resp.status_code in (429, 502, 503, 504):
                had_busy = True
                logger.warning('Overpass HTTP %s on %s', resp.status_code, base_url)
                continue
            resp.raise_for_status()
            payload = resp.json()
            elements = payload.get('elements') or []
            if not isinstance(elements, list):
                raise ValueError('پاسخ Overpass نامعتبر است')
            logger.info('Overpass succeeded via %s (%s elements)', base_url, len(elements))
            return elements
        except NearbyPoiError:
            raise
        except requests.Timeout as exc:
            last_error = exc
            had_timeout = True
            logger.warning('Overpass timeout on %s', base_url)
            continue
        except requests.RequestException as exc:
            last_error = exc
            logger.warning('Overpass request failed on %s: %s', base_url, exc)
            continue
        except (ValueError, TypeError) as exc:
            last_error = exc
            logger.warning('Overpass invalid payload on %s: %s', base_url, exc)
            continue

    extra = {'fallback': overpass_client_fallback(lat, lng, radius_m=radius_m)}
    if isinstance(last_error, requests.Timeout) or (had_timeout and last_error is None):
        raise NearbyPoiError(
            'service_busy',
            'پاسخ سرویس نقشه طول کشید. لطفاً چند دقیقه بعد دوباره تلاش کنید.',
            status=504,
            extra=extra,
        )
    if had_busy and last_error is None:
        raise NearbyPoiError(
            'service_busy',
            'سرویس نقشه الان شلوغ است. لطفاً چند دقیقه بعد دوباره تلاش کنید.',
            status=503,
            extra=extra,
        )
    raise NearbyPoiError(
        'service_unavailable',
        'سرویس نقشه از سمت سرور در دسترس نیست. در حال تلاش از مرورگر شما…',
        status=503,
        extra=extra,
    )


_OVERPASS_RETRIABLE_CODES = frozenset({'service_busy', 'service_unavailable'})


def fetch_overpass_elements_with_retry(
    lat: float,
    lng: float,
    *,
    radius_m: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Overpass fetch with bounded retries and backoff — avoids blocking workers indefinitely."""
    retries = int(getattr(settings, 'PROPERTY_ACCESSIBILITY_OVERPASS_RETRIES', 2))
    backoff_s = int(getattr(settings, 'PROPERTY_ACCESSIBILITY_OVERPASS_RETRY_BACKOFF_S', 2))
    last_error: Optional[NearbyPoiError] = None
    for attempt in range(retries + 1):
        try:
            return fetch_overpass_elements(lat, lng, radius_m=radius_m)
        except NearbyPoiError as exc:
            last_error = exc
            if exc.code not in _OVERPASS_RETRIABLE_CODES or attempt >= retries:
                raise
            delay = backoff_s * (attempt + 1)
            logger.info('Overpass retry %s/%s after %ss (%s)', attempt + 1, retries, delay, exc.code)
            time.sleep(delay)
    if last_error:
        raise last_error
    raise NearbyPoiError('service_unavailable', 'سرویس نقشه در دسترس نیست.', status=503)


def sanitize_overpass_elements(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        raise NearbyPoiError('invalid_elements', 'داده نقشه نامعتبر است.', status=400)
    cleaned: List[Dict[str, Any]] = []
    for item in raw[:MAX_INGEST_ELEMENTS]:
        if not isinstance(item, dict):
            continue
        out: Dict[str, Any] = {}
        lat = item.get('lat')
        lon = item.get('lon')
        if lat is not None and lon is not None:
            try:
                out['lat'] = float(lat)
                out['lon'] = float(lon)
            except (TypeError, ValueError):
                pass
        center = item.get('center')
        if isinstance(center, dict) and center.get('lat') is not None and center.get('lon') is not None:
            try:
                out['center'] = {'lat': float(center['lat']), 'lon': float(center['lon'])}
            except (TypeError, ValueError):
                pass
        if 'lat' not in out and 'center' not in out:
            continue
        tags = item.get('tags')
        if isinstance(tags, dict):
            out['tags'] = {
                str(key)[:64]: str(value)[:256]
                for key, value in list(tags.items())[:50]
                if value is not None
            }
        else:
            out['tags'] = {}
        cleaned.append(out)
    return cleaned


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
    status: str = ACCESSIBILITY_STATUS_READY,
    location_precision: str = 'exact',
    location_source: str = 'manual_pin',
    generation_id: Optional[str] = None,
) -> Dict[str, Any]:
    lat_key, lng_key = _coords_key(lat, lng)
    item_dicts = [item.as_dict() for item in items]
    found_count = sum(1 for item in items if item.found)
    payload = {
        'version': PAYLOAD_VERSION,
        'status': status,
        'location_precision': location_precision,
        'location_source': location_source,
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
    if generation_id:
        payload['generation_id'] = generation_id
    return payload


def stored_nearby_pois_valid(prop, *, radius_m: Optional[int] = None) -> bool:
    data = getattr(prop, 'nearby_pois', None) or {}
    if not isinstance(data, dict) or not data.get('items'):
        return False
    status = _accessibility_status(data)
    if status and status != ACCESSIBILITY_STATUS_READY:
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
    precision = data.get('location_precision') or 'exact'
    return {
        'ok': True,
        'cached': cached,
        'status': data.get('status') or ACCESSIBILITY_STATUS_READY,
        'location_precision': precision,
        'approximate_note': (
            'بر اساس موقعیت تقریبی' if precision == 'approximate' else ''
        ),
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


def fetch_and_save_nearby_pois(
    prop,
    user,
    *,
    force_refresh: bool = False,
    elements: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return refresh_property_accessibilities(
        prop,
        user,
        force_refresh=force_refresh,
        elements=elements,
    )


def clear_nearby_pois(prop) -> None:
    if prop.nearby_pois:
        prop.nearby_pois = {}
        prop.save(update_fields=['nearby_pois', 'updated_at'])


def nearby_pois_page_context(prop) -> Dict[str, Any]:
    has_coords = prop.latitude is not None and prop.longitude is not None
    status = get_property_accessibility_status(prop)
    stored = get_stored_nearby_pois_payload(prop) if has_coords else None
    location = resolve_property_location(prop)
    radius_m = property_accessibility_radius_m()
    return {
        'has_coords': has_coords,
        'has_stored': bool(stored),
        'status': status,
        'pending': status == ACCESSIBILITY_STATUS_PENDING,
        'failed': status == ACCESSIBILITY_STATUS_FAILED,
        'unavailable': status == ACCESSIBILITY_STATUS_UNAVAILABLE,
        'location_precision': location.get('precision') or 'none',
        'initial_payload': stored,
        'category_count': len(POI_CATEGORIES),
        'radius_m': radius_m,
        'radius_label': accessibility_radius_label_fa(radius_m=radius_m),
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
        status = get_property_accessibility_status(prop)
        if status == ACCESSIBILITY_STATUS_PENDING:
            return 'امکانات و دسترسی‌ها در حال محاسبه است. پس از تکمیل می‌توانید در صفحه عمومی نمایش دهید.'
        return 'ابتدا امکانات و دسترسی‌های ملک باید محاسبه شود. اگر موقعیت دارید، چند لحظه صبر کنید یا دکمه «بروزرسانی» را بزنید.'
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


# ─── Tools: دسترسی‌های اطراف (shared engine, no DB persistence) ───────────────

TOOL_RADIUS_OPTIONS_M: Tuple[int, ...] = (500, 1000, 2000, 3000)
TOOL_DEFAULT_RADIUS_M = 1000
TOOL_MARKER_CAP = 250
TOOL_NEAREST_PER_CATEGORY = 3
_TOOL_CACHE_TTL = 60 * 60

TOOL_CATEGORY_PRIORITY: Tuple[str, ...] = (
    'metro', 'bus', 'supermarket', 'park', 'pharmacy', 'hospital', 'clinic',
    'school', 'university', 'cafe', 'restaurant', 'bank', 'atm', 'fuel',
    'parking', 'mall', 'gym', 'fire_station', 'police', 'mosque',
    'bakery', 'motorway', 'main_road', 'street_type',
)


def validate_tool_radius_m(radius_m: Any) -> int:
    try:
        radius = int(radius_m)
    except (TypeError, ValueError):
        return TOOL_DEFAULT_RADIUS_M
    if radius in TOOL_RADIUS_OPTIONS_M:
        return radius
    return min(TOOL_RADIUS_OPTIONS_M, key=lambda x: abs(x - radius))


def _radius_label_fa(radius_m: int) -> str:
    if radius_m >= 1000:
        km = radius_m / 1000
        label = f'{km:g}'.replace('.', '/')
        if '/' not in label:
            label = str(int(km))
        return f'شعاع {to_persian_digits(label)} کیلومتر'
    return f'شعاع {to_persian_digits(radius_m)} متر'


def _tool_cache_key(user_id: int, lat: float, lng: float, radius_m: int) -> str:
    lat_key, lng_key = _coords_key(lat, lng)
    return f'nearby_tool:v1:{user_id}:{lat_key}:{lng_key}:{radius_m}'


def _collect_category_matches(
    lat: float,
    lng: float,
    elements: Sequence[Dict[str, Any]],
    category: Dict[str, Any],
    radius_m: int,
) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for element in elements:
        tags = element.get('tags') or {}
        if not _element_matches_category(tags, category):
            continue
        coords = _element_coords(element)
        if not coords:
            continue
        el_lat, el_lng = coords
        dist = haversine_m(lat, lng, el_lat, el_lng)
        if dist > radius_m:
            continue
        dist_m = int(round(dist))
        matches.append({
            'name': _element_name(tags, category['fallback_name']),
            'distance_m': dist_m,
            'distance_label': format_distance_label(dist),
            'walk_label': estimate_walk_label(dist),
            'lat': el_lat,
            'lng': el_lng,
        })
    matches.sort(key=lambda x: x['distance_m'])
    return matches


def resolve_nearby_catalog(
    lat: float,
    lng: float,
    elements: Sequence[Dict[str, Any]],
    *,
    radius_m: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """شمارش و نزدیک‌ترین POIها برای ابزار — بدون تغییر رفتار CRM."""
    categories: List[Dict[str, Any]] = []
    markers: List[Dict[str, Any]] = []
    empty_label = _radius_empty_label(radius_m)

    for category in POI_CATEGORIES:
        group_key = category['group']
        base = {
            'key': category['key'],
            'group': group_key,
            'group_label': _GROUP_LABELS.get(group_key, group_key),
            'label': category['label'],
            'icon': category['icon'],
            'color': category['color'],
        }
        if category.get('kind') == 'street':
            item = _resolve_street_type_item(lat, lng, elements, category)
            d = item.as_dict()
            categories.append({
                **base,
                'count': 1 if item.found else 0,
                'nearest': [d] if item.found else [],
                'found': item.found,
                'empty_label': empty_label,
            })
            continue

        matches = _collect_category_matches(lat, lng, elements, category, radius_m)
        nearest_raw = matches[:TOOL_NEAREST_PER_CATEGORY]
        nearest = [{
            'name': m['name'],
            'distance_m': m['distance_m'],
            'distance_label': m['distance_label'],
            'walk_label': m['walk_label'],
        } for m in nearest_raw]
        categories.append({
            **base,
            'count': len(matches),
            'nearest': nearest,
            'found': len(matches) > 0,
            'empty_label': empty_label,
        })
        for m in matches:
            if len(markers) >= TOOL_MARKER_CAP:
                break
            markers.append({
                'key': category['key'],
                'label': category['label'],
                'icon': category['icon'],
                'color': category['color'],
                'name': m['name'],
                'distance_m': m['distance_m'],
                'distance_label': m['distance_label'],
                'lat': m['lat'],
                'lng': m['lng'],
            })

    priority = {key: idx for idx, key in enumerate(TOOL_CATEGORY_PRIORITY)}
    categories.sort(key=lambda c: (priority.get(c['key'], 999), -c['count']))
    return categories, markers


def _build_tool_payload(
    lat: float,
    lng: float,
    categories: Sequence[Dict[str, Any]],
    markers: Sequence[Dict[str, Any]],
    *,
    radius_m: int,
    fetched_at,
) -> Dict[str, Any]:
    lat_key, lng_key = _coords_key(lat, lng)
    with_results = [c for c in categories if c.get('count', 0) > 0]
    total_pois = sum(int(c.get('count') or 0) for c in categories)
    return {
        'version': PAYLOAD_VERSION,
        'mode': 'tools_catalog',
        'fetched_at': fetched_at.isoformat(),
        'fetched_at_label': format_jalali_datetime(fetched_at),
        'coords': {'lat': lat_key, 'lng': lng_key},
        'radius_m': radius_m,
        'radius_label': _radius_label_fa(radius_m),
        'categories': list(categories),
        'categories_with_results': with_results,
        'markers': list(markers),
        'category_count': len(categories),
        'categories_found': len(with_results),
        'total_pois': total_pois,
        'disclaimer': 'فاصله خط مستقیم',
    }


def build_accessibility_report_copy(payload: Dict[str, Any]) -> str:
    radius_label = payload.get('radius_label') or _radius_label_fa(
        int(payload.get('radius_m') or TOOL_DEFAULT_RADIUS_M),
    )
    lines = [
        'دسترسی‌های اطراف ملک',
        f'محدوده بررسی: {radius_label}',
        '',
    ]
    for cat in payload.get('categories_with_results') or []:
        count = int(cat.get('count') or 0)
        if count <= 0:
            continue
        lines.append(f'• {cat.get("label")}: {to_persian_digits(count)} مورد')

    highlights: List[str] = []
    for cat in payload.get('categories_with_results') or []:
        for item in (cat.get('nearest') or [])[:2]:
            name = item.get('name') or cat.get('label')
            dist = item.get('distance_label') or ''
            if name and dist:
                highlights.append(f'• {name} — {dist}')
        if len(highlights) >= 5:
            break

    if highlights:
        lines.extend(['', 'نزدیک‌ترین دسترسی‌ها:', *highlights[:5]])

    lines.append('')
    lines.append('(فاصله خط مستقیم)')
    return '\n'.join(lines)


def build_accessibility_customer_copy(payload: Dict[str, Any]) -> str:
    radius_m = int(payload.get('radius_m') or TOOL_DEFAULT_RADIUS_M)
    radius_phrase = (
        f'{to_persian_digits(radius_m // 1000)} کیلومتر'
        if radius_m >= 1000
        else f'{to_persian_digits(radius_m)} متر'
    )
    parts: List[str] = []
    for key in ('metro', 'bus', 'park', 'pharmacy', 'cafe', 'supermarket', 'school'):
        cat = next((c for c in (payload.get('categories') or []) if c.get('key') == key), None)
        if not cat or int(cat.get('count') or 0) <= 0:
            continue
        count = int(cat['count'])
        label = cat.get('label') or key
        if key == 'metro':
            parts.append(f'{to_persian_digits(count)} ایستگاه مترو')
        elif key == 'bus':
            parts.append(f'{to_persian_digits(count)} ایستگاه اتوبوس')
        else:
            parts.append(f'{to_persian_digits(count)} {label}')

    if not parts:
        return (
            f'در شعاع {radius_phrase} این موقعیت، دسترسی ثبت‌شده‌ای در نقشه عمومی پیدا نشد. '
            'می‌توانید شعاع جستجو را افزایش دهید.'
        )

    intro = (
        f'این موقعیت از دسترسی مناسبی برخوردار است. در شعاع {radius_phrase} آن '
        + '، '.join(parts)
        + ' قرار دارد.'
    )

    nearest_bits: List[str] = []
    for key, label in (('metro', 'ایستگاه مترو'), ('park', 'پارک'), ('pharmacy', 'داروخانه')):
        cat = next((c for c in (payload.get('categories') or []) if c.get('key') == key), None)
        nearest = (cat or {}).get('nearest') or []
        if nearest:
            item = nearest[0]
            nearest_bits.append(
                f'نزدیک‌ترین {label} حدود {item.get("distance_label") or ""} فاصله دارد'
            )
    if nearest_bits:
        intro += ' ' + ' و '.join(nearest_bits[:3]) + '.'
    return intro


def tools_accessibility_api_payload(data: Dict[str, Any], *, cached: bool = False) -> Dict[str, Any]:
    return {
        'ok': True,
        'cached': cached,
        'fetched_at': data.get('fetched_at'),
        'fetched_at_label': data.get('fetched_at_label'),
        'radius_m': data.get('radius_m'),
        'radius_label': data.get('radius_label'),
        'coords': data.get('coords'),
        'categories': data.get('categories') or [],
        'categories_with_results': data.get('categories_with_results') or [],
        'markers': data.get('markers') or [],
        'categories_found': data.get('categories_found', 0),
        'total_pois': data.get('total_pois', 0),
        'disclaimer': data.get('disclaimer', 'فاصله خط مستقیم'),
        'report_copy': build_accessibility_report_copy(data),
        'customer_copy': build_accessibility_customer_copy(data),
    }


def fetch_nearby_accessibility_for_tools(
    user,
    lat: float,
    lng: float,
    radius_m: int,
    *,
    elements: Optional[Sequence[Dict[str, Any]]] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """دریافت دسترسی‌های اطراف برای ابزار — بدون ذخیره در DB."""
    radius_m = validate_tool_radius_m(radius_m)
    parsed_lat, parsed_lng, error = parse_map_coordinates(lat, lng)
    if error:
        raise NearbyPoiError('invalid_coords', error, status=400)

    cache_key = _tool_cache_key(user.pk, parsed_lat, parsed_lng, radius_m)
    if use_cache and elements is None:
        cached = cache.get(cache_key)
        if isinstance(cached, dict) and cached.get('categories'):
            return tools_accessibility_api_payload(cached, cached=True)

    check_rate_limits(user)

    if elements is not None:
        cleaned = sanitize_overpass_elements(elements)
    else:
        cleaned = fetch_overpass_elements(parsed_lat, parsed_lng, radius_m=radius_m)

    categories, markers = resolve_nearby_catalog(
        parsed_lat, parsed_lng, cleaned, radius_m=radius_m,
    )
    payload = _build_tool_payload(
        parsed_lat, parsed_lng, categories, markers,
        radius_m=radius_m, fetched_at=timezone.now(),
    )
    increment_rate_limits(user)

    if use_cache and elements is None:
        cache.set(cache_key, payload, _TOOL_CACHE_TTL)

    return tools_accessibility_api_payload(payload, cached=False)
