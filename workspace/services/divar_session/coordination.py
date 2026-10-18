"""قفل و Rate Limit مبتنی بر دیتابیس — سازگار با چند Worker."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from workspace.divar_session_models import DivarAccountSession, DivarContactThrottle
from workspace.services.divar_session.errors import DivarRateLimited, DivarSessionError

LOCK_SECONDS = 120


def assert_rate_limit(key: str, *, seconds: int) -> None:
    now = timezone.now()
    with transaction.atomic():
        row = (
            DivarContactThrottle.objects.select_for_update()
            .filter(throttle_key=key)
            .first()
        )
        if row and row.expires_at > now:
            raise DivarRateLimited()
        DivarContactThrottle.objects.update_or_create(
            throttle_key=key,
            defaults={'expires_at': now + timedelta(seconds=seconds)},
        )


@contextmanager
def session_operation_lock(session: DivarAccountSession):
    now = timezone.now()
    with transaction.atomic():
        row = DivarAccountSession.objects.select_for_update().get(pk=session.pk)
        if row.operation_lock_until and row.operation_lock_until > now:
            raise DivarSessionError(
                'عملیات دیگری روی این نشست در حال انجام است. لحظه‌ای بعد دوباره تلاش کنید.',
                code='session_busy',
            )
        row.operation_lock_until = now + timedelta(seconds=LOCK_SECONDS)
        row.save(update_fields=['operation_lock_until', 'updated_at'])
    try:
        yield
    finally:
        DivarAccountSession.objects.filter(pk=session.pk).update(
            operation_lock_until=None,
            updated_at=timezone.now(),
        )
