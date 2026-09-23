"""ارزیابی کافی‌بودن context فایل شخصی CRM قبل از LLM — فقط property_summary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from workspace.models import CRMProperty

from ai_workspace.context_builders.base import redact_pii_text

SKIP_REASON_INSUFFICIENT = 'insufficient_context'
SKIP_MESSAGE_FA = 'برای تولید خلاصه هوشمند، اطلاعات بیشتری از ملک ثبت کنید.'

_NOTES_BOILERPLATE = frozenset({
    '',
    '-',
    '—',
    'ندارد',
    'ندار',
    '...',
    '….',
})


@dataclass(frozen=True)
class PropertyContextAssessment:
    meaningful: bool
    reason: str = ''
    core_score: int = 0
    detail_score: int = 0
    has_meaningful_notes: bool = False


def _has_price(prop: CRMProperty) -> bool:
    if prop.sale_price and prop.sale_price > 0:
        return True
    if prop.deposit and prop.deposit > 0:
        return True
    if prop.monthly_rent and prop.monthly_rent > 0:
        return True
    return False


def _has_area(prop: CRMProperty) -> bool:
    return bool(prop.area and prop.area > 0)


def _has_location(prop: CRMProperty) -> bool:
    return bool(
        (prop.neighborhood or '').strip()
        or (prop.city or '').strip()
        or (prop.district or '').strip()
    )


def _meaningful_notes(prop: CRMProperty) -> bool:
    raw = redact_pii_text((prop.notes or '').strip())
    if raw in _NOTES_BOILERPLATE:
        return False
    collapsed = raw.replace('[شماره]', '').replace('[ایمیل]', '').strip()
    if len(collapsed) < 15:
        return False
    alpha = sum(1 for ch in collapsed if ch.isalpha() or '\u0600' <= ch <= '\u06ff')
    return alpha >= 8


def _detail_score(prop: CRMProperty, feature_profile: Optional[Dict[str, Any]]) -> int:
    score = 0
    if (prop.rooms or '').strip():
        score += 1
    if prop.floor is not None:
        score += 1
    if prop.build_year:
        score += 1
    if prop.total_floors:
        score += 1
    if prop.has_parking:
        score += 1
    if prop.has_storage:
        score += 1
    if prop.has_elevator:
        score += 1
    if (prop.amenities or '').strip():
        score += 1
    if prop.feature_data and any(str(v).strip() for v in prop.feature_data.values()):
        score += 1

    profile = feature_profile or {}
    if profile.get('has_details'):
        detail_count = int(profile.get('detail_count') or 0)
        if detail_count > 0:
            score += min(2, detail_count)
    return score


def assess_property_context(
    prop: CRMProperty,
    *,
    feature_profile: Optional[Dict[str, Any]] = None,
) -> PropertyContextAssessment:
    """
    ملک برای خلاصه LLM مناسب است اگر مدل بتواند فراتر از تکرار یک‌دو فیلد بنویسد.

    هویت (title/token/id) و قیمت تنها کافی نیستند.
    """
    core_price = _has_price(prop)
    core_area = _has_area(prop)
    core_location = _has_location(prop)
    core_score = sum((core_price, core_area, core_location))

    detail_score = _detail_score(prop, feature_profile)
    notes_ok = _meaningful_notes(prop)

    if core_score < 2:
        return PropertyContextAssessment(
            meaningful=False,
            reason=SKIP_REASON_INSUFFICIENT,
            core_score=core_score,
            detail_score=detail_score,
            has_meaningful_notes=notes_ok,
        )

    if core_price and not core_area and not core_location and detail_score == 0 and not notes_ok:
        return PropertyContextAssessment(
            meaningful=False,
            reason=SKIP_REASON_INSUFFICIENT,
            core_score=core_score,
            detail_score=detail_score,
            has_meaningful_notes=notes_ok,
        )

    if core_score >= 3:
        return PropertyContextAssessment(
            meaningful=True,
            core_score=core_score,
            detail_score=detail_score,
            has_meaningful_notes=notes_ok,
        )

    if core_score >= 2 and (detail_score >= 1 or notes_ok):
        return PropertyContextAssessment(
            meaningful=True,
            core_score=core_score,
            detail_score=detail_score,
            has_meaningful_notes=notes_ok,
        )

    return PropertyContextAssessment(
        meaningful=False,
        reason=SKIP_REASON_INSUFFICIENT,
        core_score=core_score,
        detail_score=detail_score,
        has_meaningful_notes=notes_ok,
    )


def has_meaningful_property_context(
    prop: CRMProperty,
    *,
    feature_profile: Optional[Dict[str, Any]] = None,
) -> bool:
    return assess_property_context(prop, feature_profile=feature_profile).meaningful
