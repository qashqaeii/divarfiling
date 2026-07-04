"""اعتبارسنجی و آماده‌سازی context قبل از LLM — صرفه‌جویی سهمیه."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

from ai_workspace.constants import (
    FEATURE_CRM_MESSAGE,
    FEATURE_LISTING_SUMMARY,
    FEATURE_UPLOAD_BRIEF,
)
from ai_workspace.context_builders.base import truncate

MAX_DESCRIPTION_LEN = 3000
MAX_GENERIC_TEXT_LEN = 800

_TEXT_FIELDS_BY_FEATURE = {
    FEATURE_LISTING_SUMMARY: (
        'description_excerpt',
        'benchmark_note',
        'tab_financial',
        'tab_property',
        'tab_location',
        'tab_text',
        'tab_features',
        'tab_extra',
    ),
    FEATURE_CRM_MESSAGE: (
        'recent_activities',
        'top_matches_text',
    ),
    FEATURE_UPLOAD_BRIEF: (),
}


@dataclass
class ValidationResult:
    context: Dict[str, Any]
    skip_llm: bool
    reason: str = ''


def _trim_text_fields(feature: str, context: Dict[str, Any]) -> Dict[str, Any]:
    ctx = dict(context)
    for key in _TEXT_FIELDS_BY_FEATURE.get(feature, ()):
        val = ctx.get(key)
        if isinstance(val, str) and len(val) > MAX_DESCRIPTION_LEN:
            ctx[key] = truncate(val, MAX_DESCRIPTION_LEN)
    for key, val in list(ctx.items()):
        if key.startswith('_') or key == 'content_version':
            continue
        if isinstance(val, str) and len(val) > MAX_GENERIC_TEXT_LEN:
            ctx[key] = truncate(val, MAX_GENERIC_TEXT_LEN)
    return ctx


def _should_skip_listing(ctx: Dict[str, Any]) -> str:
    if not str(ctx.get('title') or '').strip():
        return 'no_title'
    if not str(ctx.get('price_label') or '').strip():
        return 'no_price'
    return ''


def _should_skip_upload(ctx: Dict[str, Any]) -> str:
    total_files = int(ctx.get('total_files') or 0)
    total_added = int(ctx.get('total_added') or 0)
    if total_files <= 0 and total_added <= 0:
        return 'empty_upload'
    return ''


def _should_skip_crm(ctx: Dict[str, Any]) -> str:
    if not str(ctx.get('name') or '').strip():
        return 'no_customer_name'
    return ''


def prepare_context(feature: str, context: Dict[str, Any]) -> ValidationResult:
    """Trim متن‌های بلند؛ در صورت داده ناکافی LLM صدا زده نشود."""
    ctx = _trim_text_fields(feature, context)
    reason = ''
    if feature == FEATURE_LISTING_SUMMARY:
        reason = _should_skip_listing(ctx)
    elif feature == FEATURE_UPLOAD_BRIEF:
        reason = _should_skip_upload(ctx)
    elif feature == FEATURE_CRM_MESSAGE:
        reason = _should_skip_crm(ctx)
    return ValidationResult(context=ctx, skip_llm=bool(reason), reason=reason)
