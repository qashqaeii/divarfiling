"""داده نقشه تک‌ملکی — جزئیات میزکار و صفحه عمومی."""
from __future__ import annotations

import json
import math
from typing import Any, Dict, Optional

from workspace.services.display import (
    listing_map_deposit_label,
    listing_map_price_label,
    listing_map_rent_label,
    location_accuracy_for_map,
    market_tier_from_score,
    to_jalali_display,
)
from workspace.services.formatting import format_area, format_toman


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

    marker = {
        'lat': _json_safe_float(listing.latitude),
        'lng': _json_safe_float(listing.longitude),
        'title': listing.title or '',
        'price_label': listing_map_price_label(listing, tx),
        'deposit_label': listing_map_deposit_label(listing),
        'rent_label': listing_map_rent_label(listing),
        'area': _json_safe_float(listing.area) or 0,
        'area_label': format_area(listing.area) if listing.area else '',
        'rooms': listing.rooms or '',
        'pps_label': format_toman(listing.price_per_sqm, per_sqm=True) if listing.price_per_sqm else '',
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
