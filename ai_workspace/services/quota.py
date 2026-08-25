"""سهمیه روزانه AI — درخواست + توکن."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

from ai_workspace.constants import (
    DEFAULT_DAILY_LIMIT,
    FEATURE_DAILY_LIMITS,
    FEATURE_LABELS,
)
from ai_workspace.models import AIQuota
from workspace.services.access import has_active_bot_license


class QuotaExceededError(Exception):
    def __init__(self, message: str, code: str = 'quota_exceeded'):
        super().__init__(message)
        self.code = code


@dataclass
class QuotaStatus:
    daily_limit: int
    used_today: int
    remaining: int
    daily_token_limit: int
    tokens_used_today: int
    tokens_remaining: int
    is_unlimited: bool
    features: Dict[str, Dict[str, int]]
    has_license: bool


def _daily_token_limit() -> int:
    return int(getattr(settings, 'AI_DAILY_TOKEN_LIMIT', 30000) or 0)


def _is_unlimited(user) -> bool:
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        return True
    quota = getattr(user, 'ai_quota', None)
    return bool(quota and quota.is_unlimited)


def get_or_create_quota(user) -> AIQuota:
    today = timezone.localdate()
    quota, created = AIQuota.objects.get_or_create(
        user=user,
        defaults={'reset_date': today, 'daily_limit': DEFAULT_DAILY_LIMIT},
    )
    if not created and quota.reset_date < today:
        quota.used_today = 0
        quota.tokens_used_today = 0
        quota.listing_summary_used = 0
        quota.crm_message_used = 0
        quota.upload_brief_used = 0
        quota.reset_date = today
        quota.save(
            update_fields=[
                'used_today', 'tokens_used_today', 'listing_summary_used',
                'crm_message_used', 'upload_brief_used', 'reset_date',
            ]
        )
    return quota


def check_quota(user, feature: str) -> None:
    if _is_unlimited(user):
        return
    if not has_active_bot_license(user):
        raise QuotaExceededError(
            'برای استفاده از هوش مصنوعی، لایسنس فعال ربات استخراج دیوار لازم است.',
            code='no_license',
        )
    quota = get_or_create_quota(user)
    if quota.used_today >= quota.daily_limit:
        raise QuotaExceededError(
            f'سقف روزانه {quota.daily_limit} درخواست AI تمام شده است.',
            code='daily_limit',
        )
    token_limit = _daily_token_limit()
    if token_limit > 0 and quota.tokens_used_today >= token_limit:
        raise QuotaExceededError(
            f'سقف روزانه {token_limit:,} توکن AI تمام شده است.',
            code='token_limit',
        )
    feature_limit = FEATURE_DAILY_LIMITS.get(feature, 0)
    feature_used = quota.feature_used(feature)
    if feature_used >= feature_limit:
        label = FEATURE_LABELS.get(feature, feature)
        raise QuotaExceededError(
            f'سقف روزانه «{label}» ({feature_limit} درخواست) تمام شده است.',
            code='feature_limit',
        )


def consume_quota(
    user,
    feature: str,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
) -> None:
    if _is_unlimited(user):
        return
    quota = get_or_create_quota(user)
    field = quota.feature_field(feature)
    setattr(quota, field, quota.feature_used(feature) + 1)
    quota.used_today += 1
    total_tokens = (input_tokens or 0) + (output_tokens or 0)
    if total_tokens:
        quota.tokens_used_today += total_tokens
        quota.save(update_fields=['used_today', 'tokens_used_today', field])
    else:
        quota.save(update_fields=['used_today', field])


def get_status(user) -> QuotaStatus:
    unlimited = _is_unlimited(user)
    licensed = has_active_bot_license(user) or unlimited
    quota = get_or_create_quota(user) if user.is_authenticated else None
    daily_limit = quota.daily_limit if quota else DEFAULT_DAILY_LIMIT
    used = quota.used_today if quota else 0
    token_limit = _daily_token_limit()
    tokens_used = quota.tokens_used_today if quota else 0
    features = {}
    for feat, lim in FEATURE_DAILY_LIMITS.items():
        used_f = quota.feature_used(feat) if quota else 0
        features[feat] = {
            'limit': lim,
            'used': used_f,
            'remaining': max(0, lim - used_f),
        }
    return QuotaStatus(
        daily_limit=daily_limit,
        used_today=used,
        remaining=max(0, daily_limit - used) if not unlimited else 9999,
        daily_token_limit=token_limit,
        tokens_used_today=tokens_used,
        tokens_remaining=max(0, token_limit - tokens_used) if not unlimited and token_limit else 9999,
        is_unlimited=unlimited,
        features=features,
        has_license=licensed,
    )


def status_to_dict(status: QuotaStatus) -> Dict[str, Any]:
    return {
        'daily_limit': status.daily_limit,
        'used_today': status.used_today,
        'remaining': status.remaining,
        'daily_token_limit': status.daily_token_limit,
        'tokens_used_today': status.tokens_used_today,
        'tokens_remaining': status.tokens_remaining,
        'is_unlimited': status.is_unlimited,
        'has_license': status.has_license,
        'features': status.features,
    }


def feature_quota_dict(user, feature: str) -> Dict[str, Any]:
    """سهمیه یک قابلیت AI — برای UI وب و پاسخ JSON."""
    status = get_status(user)
    feat = status.features.get(feature) or {}
    limit = int(feat.get('limit') or 0)
    used = int(feat.get('used') or 0)
    remaining = int(feat.get('remaining') or 0)
    return {
        'feature': feature,
        'feature_label': FEATURE_LABELS.get(feature, feature),
        'feature_limit': limit,
        'feature_used': used,
        'feature_remaining': remaining,
        'feature_percent_used': round(used * 100 / limit) if limit else 0,
        'daily_limit': status.daily_limit,
        'daily_used': status.used_today,
        'daily_remaining': status.remaining,
        'is_unlimited': status.is_unlimited,
    }
