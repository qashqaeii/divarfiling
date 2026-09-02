"""سرکوب آگهی‌های حذف‌شده عمدی توسط کاربر — منبع حقیقت برای ingest و delete."""
from __future__ import annotations

import logging
from typing import Iterable, Set

from django.db import transaction

from workspace.constants import LISTING_SUPPRESSION_REASON_USER_DELETED
from workspace.models import UserListingSuppression
from workspace.services.listing_personal_status import DIVAR_SOURCE_PLATFORM

logger = logging.getLogger(__name__)

REASON_USER_DELETED = LISTING_SUPPRESSION_REASON_USER_DELETED


def _normalize_external_id(external_id: str) -> str:
    return str(external_id or '').strip()


def suppress_listing(
    user,
    platform: str,
    external_id: str,
    reason: str = REASON_USER_DELETED,
) -> UserListingSuppression:
    """ثبت/به‌روزرسانی سرکوب — idempotent."""
    platform = str(platform or '').strip()
    external_id = _normalize_external_id(external_id)
    if not platform or not external_id:
        raise ValueError('platform and external_id are required')
    obj, created = UserListingSuppression.objects.update_or_create(
        user=user,
        source_platform=platform,
        external_id=external_id,
        defaults={'reason': reason},
    )
    if created:
        logger.info(
            'listing suppressed user=%s platform=%s external_id=%s reason=%s',
            user.pk, platform, external_id, reason,
        )
    return obj


def unsuppress_listing(user, platform: str, external_id: str) -> bool:
    """حذف سرکوب — برای بازیابی آینده."""
    external_id = _normalize_external_id(external_id)
    if not external_id:
        return False
    deleted, _ = UserListingSuppression.objects.filter(
        user=user,
        source_platform=str(platform or '').strip(),
        external_id=external_id,
    ).delete()
    return deleted > 0


def get_suppressed_external_ids(
    user,
    platform: str,
    external_ids: Iterable[str],
) -> Set[str]:
    """batch lookup — یک query برای همه توکن‌های payload."""
    platform = str(platform or '').strip()
    if not platform:
        return set()
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in external_ids:
        token = _normalize_external_id(raw)
        if not token or token in seen:
            continue
        seen.add(token)
        normalized.append(token)
    if not normalized:
        return set()
    return set(
        UserListingSuppression.objects.filter(
            user=user,
            source_platform=platform,
            external_id__in=normalized,
        ).values_list('external_id', flat=True)
    )


def is_suppressed(user, platform: str, external_id: str) -> bool:
    external_id = _normalize_external_id(external_id)
    if not external_id:
        return False
    return UserListingSuppression.objects.filter(
        user=user,
        source_platform=str(platform or '').strip(),
        external_id=external_id,
    ).exists()


def divar_suppressed_tokens(user, tokens: Iterable[str]) -> Set[str]:
    return get_suppressed_external_ids(user, DIVAR_SOURCE_PLATFORM, tokens)
