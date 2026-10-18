"""تنظیمات مدیریتی دریافت شماره از دیوار."""
from __future__ import annotations

from typing import Any

from workspace.divar_session_models import DivarContactFeatureConfig
from workspace.services.divar_session.feature import get_feature_config, update_rollout_mode
from workspace.services.divar_session.service import admin_stats


def build_divar_contact_admin_context() -> dict[str, Any]:
    cfg = get_feature_config()
    return {
        'divar_contact': {
            'rollout_mode': cfg.rollout_mode,
            'rollout_choices': DivarContactFeatureConfig.RolloutMode.choices,
            'stats': admin_stats(),
            'lac_fragment': 'divar-sessions',
        },
    }


def save_divar_contact_rollout(*, rollout_mode: str, user) -> dict[str, Any]:
    if not user.is_superuser:
        return {'ok': False, 'error': 'فقط مدیر اصلی سیستم مجاز است.'}
    try:
        update_rollout_mode(rollout_mode=rollout_mode, changed_by=user)
    except ValueError as exc:
        return {'ok': False, 'error': str(exc)}
    return {'ok': True, 'rollout_mode': rollout_mode}
