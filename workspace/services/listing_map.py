"""داده نقشه تک‌ملکی — جزئیات میزکار و صفحه عمومی."""
from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple

from workspace.services.display import (
    listing_map_deposit_label,
    listing_map_price_label,
    listing_map_rent_label,
    location_accuracy_for_map,
    market_tier_from_score,
    to_jalali_display,
    transaction_profile,
)
from workspace.services.formatting import format_area, format_toman
from workspace.services.public_share_common import build_map_navigation

# محدوده تقریبی ایران — جلوگیری از مختصات تصادفی خارج از کشور
IRAN_LAT_RANGE = (24.0, 41.0)
IRAN_LNG_RANGE = (43.0, 65.0)
DEFAULT_MAP_CENTER = {'lat': 35.6892, 'lng': 51.3890, 'zoom': 11}


def _json_safe_float(value: Any) -> Optional[float]:
    """تبدیل عدد به مقدار قابل سریال‌سازی JSON (بدون NaN/Inf)."""
    if value is None or value == '':
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def build_listing_map_marker(
    listing,
    tx,
    feat=None,
    *,
    data=None,
    location_accuracy=None,
    thumb: str = '',
    platform_url: str = '',
    show_divar_link: bool = True,
    benchmark: Optional[Dict[str, Any]] = None,
    public: bool = False,
) -> Dict[str, Any]:
    """ساخت payload مارکر برای popup و نقشه جزئیات ملک."""
    feat = feat or {}
    raw_data = data if data is not None else (getattr(listing, 'data', None) or {})
    loc_acc = location_accuracy if location_accuracy is not None else location_accuracy_for_map(raw_data)

    is_consultant = 'مشاور' in (listing.business_type or '')
    if not is_consultant and feat.get('advertiser_label'):
        is_consultant = 'مشاور' in str(feat['advertiser_label'])

    score = None
    verdict = ''
    market_tier = 'unknown'
    if benchmark:
        score = _json_safe_float(benchmark.get('diff_pct'))
        verdict = (benchmark.get('verdict') or '').strip()
        market_tier = market_tier_from_score(score)

    area_value = _json_safe_float(listing.area)
    pps_value = _json_safe_float(listing.price_per_sqm)

    marker = {
        'lat': _json_safe_float(listing.latitude),
        'lng': _json_safe_float(listing.longitude),
        'title': listing.title or '',
        'price_label': listing_map_price_label(listing, tx),
        'deposit_label': listing_map_deposit_label(listing),
        'rent_label': listing_map_rent_label(listing),
        'area': area_value or 0,
        'area_label': format_area(area_value) if area_value else '',
        'rooms': listing.rooms or '',
        'pps_label': format_toman(pps_value, per_sqm=True) if pps_value else '',
        'neighborhood': listing.neighborhood or '',
        'city': listing.city or '',
        'is_consultant': is_consultant,
        'seller_type': 'مشاور' if is_consultant else 'شخصی',
        'token': listing.token or '',
        'link': listing.link if show_divar_link else '',
        'platform_url': platform_url,
        'thumb': thumb or '',
        'published': to_jalali_display(listing.published_at) if listing.published_at else '',
        'location_label': loc_acc.get('label', ''),
        'location_kind': loc_acc.get('kind', ''),
        'location_radius_m': int(loc_acc.get('radius_m') or 0),
        'value_score': score,
        'market_tier': market_tier,
        'verdict': verdict,
    }
    if public:
        marker['token'] = ''
        marker['platform_url'] = ''
    return marker


def parse_map_coordinates(latitude, longitude) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """اعتبارسنجی مختصات نقشه فایل شخصی. برمی‌گرداند (lat, lng, error)."""
    lat = _json_safe_float(latitude)
    lng = _json_safe_float(longitude)
    if lat is None or lng is None:
        return None, None, 'مختصات نامعتبر است.'
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None, None, 'مختصات خارج از محدوده مجاز است.'
    if lat == 0 and lng == 0:
        return None, None, 'مختصات نامعتبر است.'
    if not (IRAN_LAT_RANGE[0] <= lat <= IRAN_LAT_RANGE[1] and IRAN_LNG_RANGE[0] <= lng <= IRAN_LNG_RANGE[1]):
        return None, None, 'موقعیت باید داخل محدوده ایران باشد.'
    return lat, lng, None


def build_crm_property_map_context(prop, *, platform_url: str = '') -> Dict[str, Any]:
    """کانتکست نقشه برای صفحه جزئیات فایل شخصی CRM."""
    location_accuracy = {'label': 'موقعیت دقیق', 'kind': 'exact', 'radius_m': 0}
    has_coords = (
        _json_safe_float(prop.latitude) is not None
        and _json_safe_float(prop.longitude) is not None
        and not (prop.latitude == 0 and prop.longitude == 0)
    )

    pps = None
    if prop.sale_price and prop.area and float(prop.area) > 0:
        pps = float(prop.sale_price) / float(prop.area)

    thumb = ''
    images = getattr(prop, 'images', None) or []
    if images:
        thumb = str(images[0] or '')

    marker_listing = SimpleNamespace(
        latitude=prop.latitude if has_coords else None,
        longitude=prop.longitude if has_coords else None,
        title=prop.title or '',
        area=prop.area,
        rooms=prop.rooms,
        price_per_sqm=pps,
        price=prop.sale_price,
        deposit=prop.deposit,
        rent=prop.monthly_rent,
        neighborhood=prop.neighborhood or prop.district or '',
        city=prop.city or '',
        business_type=prop.business_type or '',
        token=prop.token or '',
        link=prop.link or '',
        published_at=None,
        data={},
        transaction_type=prop.deal_mode or '',
    )
    tx = transaction_profile(prop.deal_mode or '')
    marker = build_listing_map_marker(
        marker_listing,
        tx,
        {},
        data={},
        location_accuracy=location_accuracy,
        thumb=thumb,
        platform_url=platform_url,
        show_divar_link=bool(prop.link),
    )
    if not has_coords:
        marker['lat'] = None
        marker['lng'] = None

    return {
        'has_coords': has_coords,
        'location_accuracy': location_accuracy,
        'listing_map_marker': marker,
        'map_navigation': build_map_navigation(prop.latitude, prop.longitude) if has_coords else None,
        'default_map_center': DEFAULT_MAP_CENTER,
    }
