"""قرارداد ارزیابی مشترک Matching V3 — تطبیق دوطرفه با یک منطق."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

MATCH_TIER_STRONG = 'strong'
MATCH_TIER_ALTERNATIVE = 'alternative'
MATCH_TIER_INSUFFICIENT = 'insufficient_info'
MATCH_TIER_REJECTED = 'rejected'

MATCH_ENGINE_VERSION = '3.2.1-sort-provenance'

# ترتیب lexicographic: tier → display_score → relevance (هر پله جدا از بعدی)
_TIER_SORT_BASE = {
    MATCH_TIER_STRONG: 3_000_000,
    MATCH_TIER_ALTERNATIVE: 2_000_000,
    MATCH_TIER_INSUFFICIENT: 1_000_000,
    MATCH_TIER_REJECTED: 0,
}
_DISPLAY_SCORE_SCALE = 10_000
_RELEVANCE_SORT_CAP = 9999

_NOTIFY_ALLOWED_TIERS = frozenset({MATCH_TIER_STRONG})


def index_sort_score(display_score: int, tier: str, relevance_rank: int = 0) -> int:
    """
    کلید مرتب‌سازی ایندکس — lexicographic:
    tier > display_score > relevance_rank؛ item_id در _sort_refs.
    """
    tier_base = _TIER_SORT_BASE.get(tier or MATCH_TIER_STRONG, 0)
    ds = min(100, max(0, int(display_score)))
    rel = min(_RELEVANCE_SORT_CAP, max(0, int(relevance_rank or 0)))
    return tier_base + ds * _DISPLAY_SCORE_SCALE + rel


def match_eligible_for_auto_notify(match: Dict[str, Any]) -> bool:
    """اعلان خودکار فقط برای پیشنهادهای با اطمینان کافی."""
    tier = match.get('match_tier') or MATCH_TIER_STRONG
    if tier not in _NOTIFY_ALLOWED_TIERS:
        return False
    return True


@dataclass
class DimensionScores:
    price_s: float = 0.0
    area_s: float = 0.0
    hood_s: float = 0.0
    type_s: float = 0.0
    room_s: float = 0.0
    price_label: str = ''
    area_note: str = ''
    hood_note: str = ''
    type_note: str = ''
    room_note: str = ''
    geo_level: str = ''


@dataclass
class MatchEvaluation:
    eligible: bool
    tier: str
    score: int
    reasons: List[str] = field(default_factory=list)
    reject_codes: List[str] = field(default_factory=list)
    evidence_completeness: float = 0.0
    geo_confidence: str = ''
    property_type_confidence: str = ''
    property_type_source: str = ''
    is_alternative: bool = False


def compute_match_score(d: DimensionScores) -> int:
    total = (
        d.price_s * 0.40
        + d.hood_s * 0.25
        + d.area_s * 0.15
        + d.type_s * 0.10
        + d.room_s * 0.10
    )
    return min(100, max(0, int(round(total * 100))))


def build_reasons(d: DimensionScores, *, limit: int = 4) -> List[str]:
    raw = [n for n in (d.price_label, d.area_note, d.hood_note, d.type_note, d.room_note) if n]
    return raw[:limit]


def _profile_has_sale_criteria(profile) -> bool:
    return getattr(profile, 'budget_min', None) is not None or getattr(profile, 'budget_max', None) is not None


def _profile_has_rent_criteria(profile) -> bool:
    return any(
        getattr(profile, f, None) is not None
        for f in ('deposit_min', 'deposit_max', 'rent_min', 'rent_max')
    )


def _profile_has_area_criteria(profile) -> bool:
    return getattr(profile, 'min_area', None) is not None or getattr(profile, 'max_area', None) is not None


def _profile_has_geo_criteria(profile) -> bool:
    from workspace.services.crm_matching_geo import preferred_areas_from_profile

    return bool(preferred_areas_from_profile(profile))


def _profile_has_rooms_criteria(profile) -> bool:
    if getattr(profile, 'rooms_min', None) is not None or getattr(profile, 'rooms_max', None) is not None:
        return True
    legacy = getattr(profile, 'rooms', None)
    if legacy is None or legacy == '':
        return False
    return str(legacy).strip() not in ('', '-', '0')


def _profile_has_amenity_criteria(profile) -> bool:
    return any([
        bool(getattr(profile, 'want_parking', False)),
        bool(getattr(profile, 'want_storage', False)),
        bool(getattr(profile, 'want_elevator', False)),
    ])


def _profile_has_year_floor_criteria(profile) -> bool:
    return any([
        getattr(profile, 'year_min', None) is not None,
        getattr(profile, 'year_max', None) is not None,
        getattr(profile, 'floor_min', None) is not None,
        getattr(profile, 'floor_max', None) is not None,
    ])


def _profile_has_detail_criteria(profile) -> bool:
    return (
        _profile_has_rooms_criteria(profile)
        or _profile_has_amenity_criteria(profile)
        or _profile_has_year_floor_criteria(profile)
    )


def _profile_has_type_criteria(profile) -> bool:
    from workspace.services.crm_matching import _profile_allowed_property_types

    allowed = _profile_allowed_property_types(profile)
    if allowed:
        return True
    want = (getattr(profile, 'property_type', None) or '').strip()
    return bool(want and want != 'سایر')


def _deal_criteria(profile, *, is_rent_deal: bool) -> bool:
    return _profile_has_rent_criteria(profile) if is_rent_deal else _profile_has_sale_criteria(profile)


def profile_evidence_completeness(profile, *, is_rent_deal: bool) -> float:
    """۰–۱: چقدر نیاز مخاطب برای تطبیق قابل اتکا است."""
    parts = 0
    total = 5
    if _deal_criteria(profile, is_rent_deal=is_rent_deal):
        parts += 1
    if _profile_has_geo_criteria(profile):
        parts += 1
    if _profile_has_area_criteria(profile):
        parts += 1
    if _profile_has_type_criteria(profile):
        parts += 1
    if _profile_has_detail_criteria(profile):
        parts += 1
    return parts / total


def profile_has_confident_need(profile, *, is_rent_deal: bool) -> bool:
    """
    آیا شواهد کافی برای ادعای تطبیق باکیفیت وجود دارد؟
    نوع ملک به‌تنهایی، یا فقط پارکینگ/انباری، کافی نیست.
    """
    deal = _deal_criteria(profile, is_rent_deal=is_rent_deal)
    geo = _profile_has_geo_criteria(profile)
    area = _profile_has_area_criteria(profile)
    typ = _profile_has_type_criteria(profile)
    rooms = _profile_has_rooms_criteria(profile)
    amenities = _profile_has_amenity_criteria(profile)

    if typ and not any([deal, geo, area, rooms, amenities]):
        return False
    if amenities and not any([deal, geo, area, typ, rooms]):
        return False
    if deal:
        return True
    if geo and (area or typ):
        return True
    if area and typ:
        return True
    if geo and rooms:
        return True
    return False


def contact_meaningful_for_property_suggestion(
    profile,
    *,
    is_rent_listing: bool,
    is_sale_listing: bool,
) -> bool:
    """
    مسیر معکوس: سرنخ/مخاطب بدون ترجیح معنادار نباید به‌عنوان خریدار/مستأجر باکیفیت پیشنهاد شود.
    """
    ctype = getattr(profile, 'customer_type', '') or ''
    if ctype == 'سازنده':
        return True
    if ctype not in {'سرنخ'} and ctype not in {
        'خریدار', 'متقاضی خرید', 'مستاجر', 'متقاضی اجاره', 'سرمایه‌گذار',
    }:
        return True

    if is_sale_listing and profile_has_confident_need(profile, is_rent_deal=False):
        return True
    if is_rent_listing and profile_has_confident_need(profile, is_rent_deal=True):
        return True

    has_need = False
    if is_sale_listing and _profile_has_sale_criteria(profile):
        has_need = True
    if is_rent_listing and _profile_has_rent_criteria(profile):
        has_need = True
    if _profile_has_geo_criteria(profile):
        has_need = True
    if _profile_has_area_criteria(profile):
        has_need = True
    if _profile_has_type_criteria(profile):
        has_need = True
    if _profile_has_detail_criteria(profile):
        has_need = True
    if ctype == 'سرنخ':
        return has_need
    if not has_need and ctype in {'خریدار', 'متقاضی خرید', 'مستاجر', 'متقاضی اجاره'}:
        return False
    return True


def _dimension_is_alternative(score: float, *, has_criterion: bool) -> bool:
    if not has_criterion:
        return False
    if score >= 0.99:
        return False
    if score <= 0.2:
        return False
    if score == 0.5:
        return False
    return True


def classify_match_tier(
    profile,
    dims: DimensionScores,
    *,
    eligible: bool,
    is_rent_deal: bool,
    prop_type_known: bool,
    prop_type_required: bool,
) -> MatchEvaluation:
    if not eligible:
        return MatchEvaluation(
            eligible=False,
            tier=MATCH_TIER_REJECTED,
            score=0,
            reject_codes=['hard_filter'],
            evidence_completeness=profile_evidence_completeness(profile, is_rent_deal=is_rent_deal),
        )

    score = compute_match_score(dims)
    reasons = build_reasons(dims)
    evidence = profile_evidence_completeness(profile, is_rent_deal=is_rent_deal)

    if prop_type_required and not prop_type_known:
        tier = MATCH_TIER_INSUFFICIENT
    elif not profile_has_confident_need(profile, is_rent_deal=is_rent_deal):
        tier = MATCH_TIER_INSUFFICIENT
    else:
        alt_flags = [
            _dimension_is_alternative(
                dims.price_s,
                has_criterion=_deal_criteria(profile, is_rent_deal=is_rent_deal),
            ),
            _dimension_is_alternative(
                dims.area_s,
                has_criterion=_profile_has_area_criteria(profile),
            ),
            _dimension_is_alternative(
                dims.hood_s,
                has_criterion=_profile_has_geo_criteria(profile),
            ),
            _dimension_is_alternative(
                dims.room_s,
                has_criterion=_profile_has_rooms_criteria(profile),
            ),
        ]
        tier = MATCH_TIER_ALTERNATIVE if any(alt_flags) else MATCH_TIER_STRONG

    return MatchEvaluation(
        eligible=True,
        tier=tier,
        score=score,
        reasons=reasons,
        evidence_completeness=evidence,
        geo_confidence=dims.geo_level or '',
        is_alternative=tier == MATCH_TIER_ALTERNATIVE,
    )


def evaluation_to_result_fields(ev: MatchEvaluation) -> Dict[str, Any]:
    """فیلدهای افزودنی سازگار با API — بدون شکستن قرارداد قبلی."""
    return {
        'match_tier': ev.tier,
        'match_engine_version': MATCH_ENGINE_VERSION,
        'evidence_completeness': round(ev.evidence_completeness, 2),
        'geo_confidence': ev.geo_confidence,
        'property_type_confidence': ev.property_type_confidence,
        'property_type_source': ev.property_type_source,
        'is_alternative_match': ev.is_alternative,
    }
