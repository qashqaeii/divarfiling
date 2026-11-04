"""رتبه‌بندی ثانویه تطبیق — بدون تغییر امتیاز نمایشی."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from django.utils import timezone

from workspace.services.crm_matching_eval import DimensionScores, MatchEvaluation
from workspace.services.crm_matching_geo import (
    GEO_MATCH_ALIAS,
    GEO_MATCH_EXACT,
    GEO_MATCH_STRUCTURED,
)

_RELEVANCE_CAP = 9999

_TYPE_CONF_RANK = {
    'high': 2200,
    'medium': 1200,
    'low': 450,
    'none': 0,
}

_GEO_LEVEL_RANK = {
    GEO_MATCH_EXACT: 2400,
    GEO_MATCH_ALIAS: 2000,
    GEO_MATCH_STRUCTURED: 1600,
}


def _midpoint(lo, hi):
    if lo is not None and hi is not None:
        return (int(lo) + int(hi)) / 2.0
    if lo is not None:
        return float(lo)
    if hi is not None:
        return float(hi)
    return None


def _proximity_rank(value: Optional[float], lo, hi, *, max_pts: int) -> int:
    if value is None or value <= 0:
        return 0
    mid = _midpoint(lo, hi)
    if mid is None:
        return 0
    span = max(abs((hi or mid) - (lo or mid)), mid * 0.05, 1.0)
    dist = abs(float(value) - mid)
    ratio = max(0.0, 1.0 - (dist / span))
    return int(round(ratio * max_pts))


def _recency_rank(ts) -> int:
    if ts is None:
        return 0
    if isinstance(ts, datetime):
        dt = ts
    else:
        return 0
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    age_days = max(0.0, (timezone.now() - dt).total_seconds() / 86400.0)
    if age_days <= 3:
        return 500
    if age_days <= 14:
        return 350
    if age_days <= 45:
        return 200
    if age_days <= 120:
        return 80
    return 0


def compute_relevance_rank(
    profile,
    dims: DimensionScores,
    evaluation: MatchEvaluation,
    *,
    is_rent_deal: bool,
    sale_price: Optional[int] = None,
    deposit: Optional[int] = None,
    rent: Optional[int] = None,
    area: Optional[float] = None,
    property_type_confidence: str = '',
    published_at=None,
) -> int:
    rank = 0

    rank += int(round((evaluation.evidence_completeness or 0) * 600))

    rank += _GEO_LEVEL_RANK.get(dims.geo_level or '', 0)
    rank += _TYPE_CONF_RANK.get(property_type_confidence or 'none', 0)

    if dims.price_s >= 0.99:
        rank += 800
    elif dims.price_s >= 0.85:
        rank += 400

    if dims.area_s >= 0.99:
        rank += 600
    elif dims.area_s >= 0.85:
        rank += 300

    if dims.type_s >= 0.99:
        rank += 500

    if is_rent_deal:
        rank += _proximity_rank(
            float(deposit) if deposit else None,
            getattr(profile, 'deposit_min', None),
            getattr(profile, 'deposit_max', None),
            max_pts=900,
        )
        rank += _proximity_rank(
            float(rent) if rent else None,
            getattr(profile, 'rent_min', None),
            getattr(profile, 'rent_max', None),
            max_pts=900,
        )
    else:
        rank += _proximity_rank(
            float(sale_price) if sale_price else None,
            getattr(profile, 'budget_min', None),
            getattr(profile, 'budget_max', None),
            max_pts=1400,
        )

    rank += _proximity_rank(
        float(area) if area else None,
        getattr(profile, 'min_area', None),
        getattr(profile, 'max_area', None),
        max_pts=700,
    )

    rank += _recency_rank(published_at)
    return min(_RELEVANCE_CAP, max(0, rank))
