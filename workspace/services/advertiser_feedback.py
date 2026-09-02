"""ثبت بازخورد کاربر روی تشخیص آگهی‌دهنده."""
from __future__ import annotations

import json
from typing import Optional, Tuple

from django.db.models import Count, Q

from workspace.models import AdvertiserSignalFeedback, Listing


def save_advertiser_feedback(
    *,
    user,
    listing: Listing,
    feedback: str,
    predicted_classification: str,
    detector_version: int,
    user_correction: str = '',
) -> Tuple[Optional[AdvertiserSignalFeedback], Optional[str]]:
    """ذخیره یا به‌روزرسانی بازخورد — یک رکورد per user/listing/version."""
    if feedback not in (
        AdvertiserSignalFeedback.FEEDBACK_CORRECT,
        AdvertiserSignalFeedback.FEEDBACK_INCORRECT,
    ):
        return None, 'بازخورد نامعتبر است.'

    correction = ''
    if feedback == AdvertiserSignalFeedback.FEEDBACK_INCORRECT:
        valid = {c[0] for c in AdvertiserSignalFeedback.CORRECTION_CHOICES}
        if user_correction not in valid:
            return None, 'لطفاً نوع صحیح آگهی‌دهنده را انتخاب کنید.'
        correction = user_correction

    obj, _created = AdvertiserSignalFeedback.objects.update_or_create(
        user=user,
        listing=listing,
        detector_version=detector_version,
        defaults={
            'listing_token': listing.token,
            'predicted_classification': predicted_classification,
            'feedback': feedback,
            'user_correction': correction,
        },
    )
    return obj, None


def feedback_analytics_summary() -> dict:
    """خلاصه آماری برای Admin."""
    qs = AdvertiserSignalFeedback.objects.all()
    total = qs.count()
    if not total:
        return {
            'total': 0,
            'correct_count': 0,
            'incorrect_count': 0,
            'correct_pct': 0,
            'incorrect_pct': 0,
            'by_version': [],
            'incorrect_genuine': 0,
            'incorrect_disguised': 0,
        }

    correct = qs.filter(feedback=AdvertiserSignalFeedback.FEEDBACK_CORRECT).count()
    incorrect = total - correct
    incorrect_genuine = qs.filter(
        feedback=AdvertiserSignalFeedback.FEEDBACK_INCORRECT,
        predicted_classification='genuine_personal',
    ).count()
    incorrect_disguised = qs.filter(
        feedback=AdvertiserSignalFeedback.FEEDBACK_INCORRECT,
        predicted_classification='disguised_consultant',
    ).count()
    by_version = list(
        qs.values('detector_version')
        .annotate(
            total=Count('id'),
            correct=Count('id', filter=Q(feedback=AdvertiserSignalFeedback.FEEDBACK_CORRECT)),
            incorrect=Count('id', filter=Q(feedback=AdvertiserSignalFeedback.FEEDBACK_INCORRECT)),
        )
        .order_by('-detector_version')
    )
    return {
        'total': total,
        'correct_count': correct,
        'incorrect_count': incorrect,
        'correct_pct': round(correct * 100 / total),
        'incorrect_pct': round(incorrect * 100 / total),
        'by_version': by_version,
        'incorrect_genuine': incorrect_genuine,
        'incorrect_disguised': incorrect_disguised,
    }


def parse_feedback_payload(body: bytes) -> Tuple[dict, Optional[str]]:
    try:
        data = json.loads(body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}, 'درخواست نامعتبر است.'
    if not isinstance(data, dict):
        return {}, 'درخواست نامعتبر است.'
    return data, None
