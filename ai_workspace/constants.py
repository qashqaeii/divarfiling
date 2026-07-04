"""ثابت‌ها و Feature Flag — فاز صفر AI."""
from __future__ import annotations

from django.conf import settings

from workspace.services.access import has_active_bot_license

FEATURE_LISTING_SUMMARY = 'listing_summary'
FEATURE_CRM_MESSAGE = 'crm_message'
FEATURE_UPLOAD_BRIEF = 'upload_brief'

AI_FEATURES = {
    FEATURE_LISTING_SUMMARY: True,
    FEATURE_CRM_MESSAGE: True,
    FEATURE_UPLOAD_BRIEF: True,
}

FEATURE_DAILY_LIMITS = {
    FEATURE_LISTING_SUMMARY: 10,
    FEATURE_CRM_MESSAGE: 8,
    FEATURE_UPLOAD_BRIEF: 2,
}

DEFAULT_DAILY_LIMIT = 10

FEATURE_LABELS = {
    FEATURE_LISTING_SUMMARY: 'خلاصه آگهی',
    FEATURE_CRM_MESSAGE: 'پیام CRM',
    FEATURE_UPLOAD_BRIEF: 'تحلیل آپلود',
}

JSON_FEATURES = frozenset({FEATURE_LISTING_SUMMARY, FEATURE_UPLOAD_BRIEF})

# نسخه دستی prompt — فقط وقتی محتوا عوض شد افزایش دهید (نه mtime)
PROMPT_VERSIONS = {
    FEATURE_LISTING_SUMMARY: 'listing_summary_v2',
    FEATURE_CRM_MESSAGE: 'crm_message_v1',
    FEATURE_UPLOAD_BRIEF: 'upload_brief_v1',
}


def is_ai_enabled() -> bool:
    return bool(getattr(settings, 'AI_ENABLED', False))


def is_feature_enabled(feature: str, user) -> bool:
    if not is_ai_enabled():
        return False
    if feature not in AI_FEATURES or not AI_FEATURES[feature]:
        return False
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        return True
    return has_active_bot_license(user)


def feature_uses_json(feature: str) -> bool:
    return feature in JSON_FEATURES
