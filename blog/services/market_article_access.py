"""تحلیل دسترسی و امکانات شهری محله برای مقالات بازار — مبتنی بر OSM/Overpass."""
from __future__ import annotations

import logging
import math
from typing import Any

from workspace.services.jalali_input import to_persian_digits
from workspace.services.nearby_pois import (
    POI_CATEGORIES,
    POI_GROUPS,
    NearbyPoiError,
    _element_coords,
    _element_matches_category,
    fetch_overpass_elements,
    haversine_m,
)

logger = logging.getLogger(__name__)

_GROUP_WEIGHTS = {
    'transport': 0.18,
    'daily': 0.22,
    'health': 0.18,
    'education': 0.14,
    'religion': 0.08,
    'leisure': 0.10,
    'safety': 0.10,
}

_COUNT_CAPS = {
    'bus': 12,
    'parking': 10,
    'atm': 8,
    'supermarket': 10,
    'bakery': 8,
    'cafe': 10,
    'restaurant': 12,
    'school': 8,
    'pharmacy': 8,
    'clinic': 8,
    'mosque': 8,
    'park': 6,
    'gym': 6,
    'police': 4,
    'fire_station': 3,
    'default': 6,
}

_CATEGORY_WEIGHT = {
    'metro': 1.35,
    'bus': 0.75,
    'motorway': 0.7,
    'main_road': 0.85,
    'supermarket': 1.2,
    'bakery': 0.9,
    'cafe': 0.85,
    'restaurant': 0.95,
    'bank': 0.85,
    'atm': 0.7,
    'fuel': 0.75,
    'parking': 0.7,
    'pharmacy': 1.1,
    'hospital': 1.4,
    'clinic': 1.0,
    'school': 1.15,
    'university': 1.05,
    'mosque': 1.0,
    'park': 1.15,
    'gym': 0.85,
    'mall': 0.95,
    'police': 1.2,
    'fire_station': 1.25,
}


def analyze_district_access(geo_points: list[dict] | None) -> dict[str, Any]:
    """امکانات اطراف مرکز تراکم فایل‌ها — شبیه پنل CRM + شمارش تعداد هر دسته."""
    from django.conf import settings

    if getattr(settings, 'MARKET_ARTICLE_SKIP_MAP_TILES', False) or getattr(
        settings, 'MARKET_ARTICLE_SKIP_ACCESS', False
    ):
        return {'ok': False, 'reason': 'skipped'}

    center = _geo_center(geo_points or [])
    if not center:
        return {'ok': False, 'reason': 'no_geo'}

    lat, lng = center
    radius_m = int(
        getattr(settings, 'MARKET_ARTICLE_ACCESS_RADIUS_M', None)
        or getattr(settings, 'NEARBY_POI_SEARCH_RADIUS_M', 3000)
        or 3000
    )
    radius_m = max(900, min(5000, radius_m))

    try:
        elements = fetch_overpass_elements(lat, lng, radius_m=radius_m)
    except NearbyPoiError as exc:
        logger.warning('district access overpass failed: %s', getattr(exc, 'message', str(exc)))
        return {
            'ok': False,
            'reason': 'overpass',
            'center': {'lat': lat, 'lng': lng},
            'radius_m': radius_m,
            'radius_label': _radius_label(radius_m),
            'message': str(getattr(exc, 'message', None) or exc),
        }
    except Exception as exc:
        logger.exception('district access unexpected error')
        return {
            'ok': False,
            'reason': 'error',
            'center': {'lat': lat, 'lng': lng},
            'radius_m': radius_m,
            'radius_label': _radius_label(radius_m),
            'message': str(exc),
        }

    tallies = _tally_categories(lat, lng, elements, radius_m=radius_m)
    categories = _categories_from_tallies(tallies)
    score_groups = _build_score_groups(categories)
    score, grade, grade_label = _score_access(score_groups)

    # گروه‌های UI فقط با تعداد (بدون فاصله / نوع معبر)
    groups_ui = []
    for g in score_groups:
        items = [i for i in (g.get('items') or []) if int(i.get('count') or 0) > 0]
        if not items:
            continue
        items = sorted(items, key=lambda x: int(x.get('count') or 0), reverse=True)
        groups_ui.append({
            'key': g['key'],
            'label': g['label'],
            'count': sum(int(i.get('count') or 0) for i in items),
            'score': g.get('score'),
            'items': items,
        })

    highlights = sorted(
        [c for c in categories if int(c.get('count') or 0) >= 1],
        key=lambda c: int(c.get('count') or 0),
        reverse=True,
    )[:4]
    gaps = [
        {
            'key': c['key'],
            'label': c['label'],
            'icon': c.get('icon'),
            'color': c.get('color'),
        }
        for c in categories
        if int(c.get('count') or 0) == 0
        and c['key'] in {
            'hospital', 'pharmacy', 'supermarket', 'school', 'park',
            'metro', 'fire_station', 'police', 'cafe', 'restaurant',
        }
    ][:6]

    found_count = sum(1 for c in categories if int(c.get('count') or 0) > 0)
    total_count = len(categories)
    total_pois = sum(int(c.get('count') or 0) for c in categories)

    return {
        'ok': True,
        'source': 'OpenStreetMap',
        'center': {'lat': round(lat, 6), 'lng': round(lng, 6)},
        'radius_m': radius_m,
        'radius_label': _radius_label(radius_m),
        'score': score,
        'grade': grade,
        'grade_label': grade_label,
        'summary': _summary_fa(score, grade_label, categories, gaps),
        'items': categories,
        'groups': groups_ui,
        'categories': categories,
        'highlights': highlights,
        'gaps': gaps,
        'found_count': found_count,
        'total_count': total_count,
        'missing_count': max(0, total_count - found_count),
        'map_markers': _map_markers(tallies, limit=28),
        'total_pois': total_pois,
    }


def _radius_label(radius_m: int) -> str:
    if radius_m >= 1000:
        km = radius_m / 1000.0
        if abs(km - round(km)) < 1e-6:
            return f'{to_persian_digits(int(round(km)))} کیلومتر'
        label = f'{km:.1f}'.rstrip('0').rstrip('.')
        return f'{to_persian_digits(label)} کیلومتر'
    return f'{to_persian_digits(radius_m)} متر'


def _geo_center(points: list[dict]) -> tuple[float, float] | None:
    coords = []
    for p in points:
        try:
            lat = float(p.get('lat'))
            lng = float(p.get('lng'))
        except (TypeError, ValueError):
            continue
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            coords.append((lat, lng))
    if len(coords) < 3:
        return None
    lats = sorted(c[0] for c in coords)
    lngs = sorted(c[1] for c in coords)
    mid = len(coords) // 2
    return lats[mid], lngs[mid]


_SKIP_CATEGORY_KEYS = frozenset({'street_type', 'motorway', 'main_road'})


def _tally_categories(
    lat: float,
    lng: float,
    elements: list[dict],
    *,
    radius_m: int,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for category in POI_CATEGORIES:
        if category.get('kind') == 'street' or category['key'] in _SKIP_CATEGORY_KEYS:
            continue
        seen_ids: set[Any] = set()
        samples: list[dict[str, Any]] = []
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
            eid = element.get('id')
            key_id = (element.get('type'), eid) if eid is not None else (el_lat, el_lng)
            if key_id in seen_ids:
                continue
            seen_ids.add(key_id)
            name = (
                (tags.get('name:fa') or tags.get('name') or tags.get('brand') or '')
            ).strip() or category['fallback_name']
            samples.append({
                'lat': round(el_lat, 6),
                'lng': round(el_lng, 6),
                'name': name,
                'distance_m': int(round(dist)),
            })
        samples.sort(key=lambda s: s['distance_m'])
        out[category['key']] = {
            'count': len(seen_ids),
            'samples': samples[:6],
            'label': category['label'],
            'icon': category['icon'],
            'color': category['color'],
            'group': category['group'],
        }
    return out


def _categories_from_tallies(
    tallies: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for category in POI_CATEGORIES:
        if category.get('kind') == 'street' or category['key'] in _SKIP_CATEGORY_KEYS:
            continue
        key = category['key']
        tally = tallies.get(key) or {}
        count = int(tally.get('count') or 0)
        out.append({
            'key': key,
            'group': category['group'],
            'label': category['label'],
            'icon': category['icon'],
            'color': category['color'],
            'count': count,
            'found': count > 0,
            'samples': tally.get('samples') or [],
        })
    return out


def _build_score_groups(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_group: dict[str, list] = {g['key']: [] for g in POI_GROUPS}
    for cat in categories:
        by_group.setdefault(cat['group'], []).append(cat)

    groups = []
    for g in POI_GROUPS:
        items = by_group.get(g['key']) or []
        total = sum(int(i.get('count') or 0) for i in items)
        groups.append({
            'key': g['key'],
            'label': g['label'],
            'count': total,
            'score': _group_score(items),
            'items': items,
        })
    return groups


def _count_to_score(count: int, *, cap: int) -> float:
    if count <= 0:
        return 0.0
    c = min(count, cap)
    ratio = c / max(cap, 1)
    return min(100.0, 38.0 + 62.0 * math.sqrt(ratio))


def _group_score(items: list[dict[str, Any]]) -> int:
    if not items:
        return 0
    weighted = 0.0
    wsum = 0.0
    for item in items:
        key = item['key']
        w = float(_CATEGORY_WEIGHT.get(key, 1.0))
        cap = int(_COUNT_CAPS.get(key, _COUNT_CAPS['default']))
        s = _count_to_score(int(item.get('count') or 0), cap=cap)
        nearest = item.get('nearest_m')
        if nearest is not None and int(item.get('count') or 0) > 0:
            if nearest <= 250:
                s = min(100.0, s + 8)
            elif nearest <= 500:
                s = min(100.0, s + 4)
        weighted += s * w
        wsum += w
    return int(round(weighted / wsum)) if wsum else 0


def _score_access(groups: list[dict[str, Any]]) -> tuple[int, str, str]:
    total_w = 0.0
    acc = 0.0
    for g in groups:
        w = float(_GROUP_WEIGHTS.get(g['key'], 0.08))
        acc += float(g.get('score') or 0) * w
        total_w += w
    score = int(round(acc / total_w)) if total_w else 0
    score = max(0, min(100, score))
    if score >= 90:
        return score, 'A+', 'دسترسی ممتاز'
    if score >= 80:
        return score, 'A', 'دسترسی عالی'
    if score >= 70:
        return score, 'B+', 'دسترسی خوب'
    if score >= 60:
        return score, 'B', 'دسترسی قابل قبول'
    if score >= 45:
        return score, 'C', 'دسترسی متوسط'
    return score, 'D', 'دسترسی محدود'


def _summary_fa(
    score: int,
    grade_label: str,
    categories: list,
    gaps: list,
) -> str:
    parts = [f'امتیاز دسترسی محله {to_persian_digits(score)} از ۱۰۰ ({grade_label}).']
    tops = sorted(categories, key=lambda c: int(c.get('count') or 0), reverse=True)
    tops = [c for c in tops if int(c.get('count') or 0) >= 2][:3]
    if tops:
        parts.append(
            'نقاط قوت: '
            + '، '.join(f'{h["label"]} ({to_persian_digits(h["count"])})' for h in tops)
            + '.'
        )
    if gaps:
        miss = '، '.join(g['label'] for g in gaps[:3])
        parts.append(f'کمبود نسبی در شعاع بررسی: {miss}.')
    else:
        parts.append('خدمات کلیدی در فاصلهٔ قابل پیاده‌روی در دسترس است.')
    return ' '.join(parts)


def _map_markers(tallies: dict[str, dict[str, Any]], *, limit: int = 28) -> list[dict[str, Any]]:
    priority = [
        'hospital', 'fire_station', 'police', 'metro', 'school', 'mosque',
        'supermarket', 'pharmacy', 'park', 'clinic', 'restaurant', 'cafe',
        'bakery', 'bank',
    ]
    markers = []
    for key in priority:
        tally = tallies.get(key) or {}
        for sample in tally.get('samples') or []:
            markers.append({
                'lat': sample['lat'],
                'lng': sample['lng'],
                'key': key,
                'label': tally.get('label') or key,
                'color': tally.get('color') or '#0d9488',
                'name': sample.get('name') or tally.get('label') or key,
            })
            if len(markers) >= limit:
                return markers
    return markers
