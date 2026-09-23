"""پاسخ کنترل‌شده وقتی context فایل شخصی برای LLM کافی نیست."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ai_workspace.constants import FEATURE_LISTING_SUMMARY
from ai_workspace.services.property_context_gate import (
    SKIP_MESSAGE_FA,
    SKIP_REASON_INSUFFICIENT,
)
from ai_workspace.services.quota import feature_quota_dict


class PropertySummaryInsufficientContext(Exception):
    """بدون فراخوانی provider — quota مصرف نمی‌شود."""

    def __init__(self, reason: str = SKIP_REASON_INSUFFICIENT, message: str = SKIP_MESSAGE_FA):
        self.reason = reason
        self.message = message
        super().__init__(message)


def property_summary_skipped_dict(
    user,
    *,
    reason: str = SKIP_REASON_INSUFFICIENT,
    message: str = SKIP_MESSAGE_FA,
) -> Dict[str, Any]:
    return {
        'ok': True,
        'skipped': True,
        'skip_reason': reason,
        'message': message,
        'feature': FEATURE_LISTING_SUMMARY,
        'provider': '',
        'model': '',
        'is_fallback': False,
        'from_cache': False,
        'status': 'skipped',
        'data': {},
        'latency_ms': 0,
        'quota': feature_quota_dict(user, FEATURE_LISTING_SUMMARY),
    }
