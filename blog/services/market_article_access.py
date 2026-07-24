"""تحلیل دسترسی و امکانات شهری محله برای مقالات بازار — مبتنی بر OSM/Overpass."""
from __future__ import annotations

import logging
import math
from typing import Any

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

# وزن گروه‌ها برای امتیاز دسترسی محله (جمع ≈ ۱)
_GROUP_WEIGHTS = {
    'transport': 0.18,
    'daily': 0.22,
    'health': 0.18,
    'education': 0.14,
    'religion': 0.08,
    'leisure': 0.10,
    'safety': 0.10,
}

# سقف شمارش برای امتیاز (از تورم ایستگاه اتوبوس جلوگیری می‌کند)
_COUNT_CAPS = {
    'bus': 12,
    'parking': 10,
    'atm': 8,
    'supermarket': 10,
    'bakery': 8,
    'school': 8,
    'pharmacy': 8,
    'clinic': 8,
    'mosque': 8,
    'park': 6,
    'gym': 6,
    'default': 6,
}

# اهمیت نسبی داخل گروه
_CATEGORY_WEIGHT = {
    'metro': 1.35,
    'bus': 0.75,
    'motorway': 0.7,
    'main_road': 0.85,
    'supermarket': 1.2,
    'bakery': 0.9,
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
    """شمارش امکانات اطراف مرکز تراکم فایل‌ها + امتیاز دسترسی محله."""
    from django.conf import settings

    if getattr(settings, 'MARKET_ARTICLE_SKIP_MAP_TILES', False) or getattr(
        settings, 'MARKET_ARTICLE_SKIP_ACCESS', False
    ):
        return {'ok': False, 'reason': 'skipped'}

    center = _geo_center(geo_points or [])
    if not center:
        return {'ok': False, 'reason': 'no_geo'}

    lat, lng = center
    radius_m = _adaptive_radius_m(geo_points or [])
    try:
        elements = fetch_overpass_elements(lat, lng, radius_m=radius_m)
    except NearbyPoiError as exc:
        logger.warning('district access overpass failed: %s', getattr(exc, 'message', str(exc)))
        return {
            'ok': False,
            'reason': 'overpass',
            'center': {'lat': lat, 'lng': lng},
            'radius_m': radius_m,
            'message': str(getattr(exc, 'message', None) or exc),
        }
    except Exception as exc:
        logger.exception('district access unexpected error')
        return {
            'ok': False,
            'reason': 'error',
            'center': {'lat': lat, 'lng': lng},
            'radius_m': radius_m,
            'message': str(exc),
        }

    categories = _count_categories(lat, lng, elements, radius_m=radius_m)
    groups = _build_groups(categories)
    score, grade, grade_label = _score_access(groups)
    highlights, gaps = _highlights_and_gaps(categories)

    return {
        'ok': True,
        'source': 'OpenStreetMap',
        'center': {'lat': round(lat, 6), 'lng': round(lng, 6)},
        'radius_m': radius_m,
        'radius_label': f'{radius_m} متر',
        'score': score,
        'grade': grade,
        'grade_label': grade_label,
        'summary': _summary_fa(score, grade_label, highlights, gaps),
        'groups': groups,
        'categories': categories,
        'highlights': highlights,
        'gaps': gaps,
        'map_markers': _map_markers(categories, limit=28),
        'total_pois': sum(int(c.get('count') or 0) for c in categories),
    }


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
    coords.sort(key=lambda x: x[0])
    mid = len(coords) // 2
    # میانه جغرافیایی پایدارتر از میانگین در برابر پرت
    lats = sorted(c[0] for c in coords)
    lngs = sorted(c[1] for c in coords)
    return lats[mid], lngs[mid]


def _adaptive_radius_m(points: list[dict]) -> int:
    coords = []
    for p in points:
        try:
            coords.append((float(p['lat']), float(p['lng'])))
        except (KeyError, TypeError, ValueError):
            continue
    if len(coords) < 3:
        return 1200
    lats = [c[0] for c in coords]
    lngs = [c[1] for c in coords]
    # فاصله تقریبی گوشه bbox (درجه → متر)
    dlat = max(lats) - min(lats)
    dlng = max(lngs) - min(lngs)
    mid_lat = (max(lats) + min(lats)) / 2
    m_lat = dlat * 111_320
    m_lng = dlng * 111_320 * max(0.2, math.cos(math.radians(mid_lat)))
    half_diag = 0.5 * math.hypot(m_lat, m_lng)
    # کمی بزرگ‌تر از هسته تراکم تا امکانات لبه محله دیده شود
    radius = int(half_diag * 1.15)
    return max(900, min(2000, radius or 1200))


def _count_categories(
    lat: float,
    lng: float,
    elements: list[dict],
    *,
    radius_m: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for category in POI_CATEGORIES:
        if category.get('kind') == 'street':
            continue
        seen_ids: set[Any] = set()
        nearest_m = None
        nearest_name = ''
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
            if nearest_m is None or dist < nearest_m:
                nearest_m = int(round(dist))
                nearest_name = name
            if len(samples) < 4:
                samples.append({
                    'lat': round(el_lat, 6),
                    'lng': round(el_lng, 6),
                    'name': name,
                    'distance_m': int(round(dist)),
                })

        count = len(seen_ids)
        out.append({
            'key': category['key'],
            'group': category['group'],
            'label': category['label'],
            'icon': category['icon'],
            'color': category['color'],
            'count': count,
            'nearest_m': nearest_m,
            'nearest_name': nearest_name or None,
            'samples': samples,
        })
    return out


def _build_groups(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_group: dict[str, list] = {g['key']: [] for g in POI_GROUPS}
    for cat in categories:
        by_group.setdefault(cat['group'], []).append(cat)

    groups = []
    for g in POI_GROUPS:
        items = by_group.get(g['key']) or []
        total = sum(int(i.get('count') or 0) for i in items)
        score = _group_score(items)
        groups.append({
            'key': g['key'],
            'label': g['label'],
            'count': total,
            'score': score,
            'items': items,
        })
    return groups


def _count_to_score(count: int, *, cap: int) -> float:
    """نقشه شمارش به امتیاز ۰–۱۰۰ با اشباع نرم."""
    if count <= 0:
        return 0.0
    c = min(count, cap)
    # ۱ → ۴۵، نزدیک cap → ۹۵+
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
        # نزدیک‌بودن نزدیک‌ترین مورد کمی پاداش می‌دهد
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


def _highlights_and_gaps(categories: list[dict]) -> tuple[list[dict], list[dict]]:
    ranked = sorted(categories, key=lambda c: int(c.get('count') or 0), reverse=True)
    highlights = [
        {
            'key': c['key'],
            'label': c['label'],
            'count': c['count'],
            'icon': c['icon'],
            'color': c['color'],
            'nearest_m': c.get('nearest_m'),
        }
        for c in ranked
        if int(c.get('count') or 0) >= 2
    ][:5]

    important_gaps = {'hospital', 'pharmacy', 'supermarket', 'school', 'park', 'metro', 'fire_station', 'police'}
    gaps = [
        {
            'key': c['key'],
            'label': c['label'],
            'count': c['count'],
            'icon': c['icon'],
            'color': c['color'],
        }
        for c in categories
        if c['key'] in important_gaps and int(c.get('count') or 0) == 0
    ][:5]
    return highlights, gaps


def _summary_fa(score: int, grade_label: str, highlights: list, gaps: list) -> str:
    parts = [f'امتیاز دسترسی محله {score} از ۱۰۰ ({grade_label}).']
    if highlights:
        tops = '، '.join(f'{h["label"]} ({h["count"]})' for h in highlights[:3])
        parts.append(f'نقاط قوت: {tops}.')
    if gaps:
        miss = '، '.join(g['label'] for g in gaps[:3])
        parts.append(f'کمبود نسبی در شعاع بررسی: {miss}.')
    else:
        parts.append('در شعاع بررسی، کمبود جدی در خدمات کلیدی دیده نشد.')
    return ' '.join(parts)


def _map_markers(categories: list[dict], *, limit: int = 28) -> list[dict[str, Any]]:
    markers = []
    # اولویت دسته‌های مهم برای نمایش روی نقشه
    priority = [
        'hospital', 'fire_station', 'police', 'metro', 'school', 'mosque',
        'supermarket', 'pharmacy', 'park', 'clinic', 'bakery', 'bank',
    ]
    by_key = {c['key']: c for c in categories}
    for key in priority:
        cat = by_key.get(key)
        if not cat:
            continue
        for sample in cat.get('samples') or []:
            markers.append({
                'lat': sample['lat'],
                'lng': sample['lng'],
                'key': key,
                'label': cat['label'],
                'color': cat['color'],
                'name': sample.get('name') or cat['label'],
            })
            if len(markers) >= limit:
                return markers
    return markers
