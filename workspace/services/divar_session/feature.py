"""Feature flag و مجوز استفاده از قابلیت دریافت شماره از دیوار."""
from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from workspace.divar_session_models import DivarContactFeatureConfig


def get_feature_config() -> DivarContactFeatureConfig:
    row, _ = DivarContactFeatureConfig.objects.get_or_create(singleton_key='default')
    return row


def get_rollout_mode() -> str:
    return get_feature_config().rollout_mode


def user_can_use_divar_contact(user: AbstractBaseUser | AnonymousUser) -> bool:
    if not user or not user.is_authenticated:
        return False
    mode = get_rollout_mode()
    if mode == DivarContactFeatureConfig.RolloutMode.DISABLED:
        return False
    if mode == DivarContactFeatureConfig.RolloutMode.ADMIN_ONLY:
        return bool(getattr(user, 'is_superuser', False))
    return True


def update_rollout_mode(
    *,
    rollout_mode: str,
    changed_by,
) -> DivarContactFeatureConfig:
    cfg = get_feature_config()
    old = cfg.rollout_mode
    if old == rollout_mode:
        return cfg
    valid = {c.value for c in DivarContactFeatureConfig.RolloutMode}
    if rollout_mode not in valid:
        raise ValueError('وضعیت انتشار نامعتبر است.')
    cfg.rollout_mode = rollout_mode
    cfg.updated_by = changed_by
    cfg.save(update_fields=['rollout_mode', 'updated_by', 'updated_at'])
    from workspace.divar_session_models import DivarContactFeatureAuditLog

    DivarContactFeatureAuditLog.objects.create(
        changed_by=changed_by,
        field_name='rollout_mode',
        old_value=old,
        new_value=rollout_mode,
    )
    return cfg
