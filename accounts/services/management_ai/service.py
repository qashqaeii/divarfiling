"""Public API for Management AI — GET never calls provider."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache

from accounts.services.management_ai.analyzer import (
    ManagementAIDisabled,
    ManagementAIError,
    run_management_analysis,
)
from accounts.services.management_ai.fingerprint import compute_fingerprint
from accounts.services.management_ai.registry import (
    build_section_snapshot,
    days_key_to_int,
    normalize_period,
)
from accounts.services.management_ai.schemas import PHASE1_SECTIONS
from accounts.services.management_ai.storage import get_stored_analysis, save_analysis

logger = logging.getLogger(__name__)

RATE_LIMIT_SECONDS = 60
LOCK_SECONDS = 120


def is_management_ai_enabled() -> bool:
    return bool(getattr(settings, 'ADMIN_MANAGEMENT_AI_ENABLED', False))


def _rate_limit_key(user_id: int, section: str, days_key: str, compare: bool) -> str:
    return f'mgmt_ai:rl:{user_id}:{section}:{days_key}:c{int(compare)}'


def _lock_key(user_id: int, section: str, days_key: str, compare: bool) -> str:
    return f'mgmt_ai:lock:{user_id}:{section}:{days_key}:c{int(compare)}'


def _attach_action_targets(analysis: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    targets = snapshot.get('action_targets') or {}
    actions = analysis.get('actions') or []
    for action in actions:
        ref = action.get('action_target_ref')
        if ref and ref in targets:
            action['action_target'] = targets[ref]
    return analysis


def get_latest_analysis(
    section: str,
    days: int,
    compare: bool,
) -> Dict[str, Any]:
    if section not in PHASE1_SECTIONS:
        return {'status': 'error', 'error': 'invalid_section'}

    if not is_management_ai_enabled():
        return {'status': 'disabled'}

    days_int, compare_enabled, days_key = normalize_period(days, compare)
    stored = get_stored_analysis(section, days_key, compare_enabled)
    if not stored:
        return {'status': 'not_generated', 'days_key': days_key, 'compare': compare_enabled}

    current_snapshot = build_section_snapshot(section, days_int, compare_enabled)
    current_fp = compute_fingerprint(current_snapshot)
    is_stale = current_fp != stored.snapshot_fingerprint

    analysis = dict(stored.analysis_json or {})
    _attach_action_targets(analysis, current_snapshot)

    return {
        'status': 'available',
        'analysis': analysis,
        'generated_at': stored.generated_at.isoformat(),
        'generated_by': stored.generated_by_id,
        'provider': stored.provider,
        'model': stored.model,
        'is_stale': is_stale,
        'snapshot_fingerprint': stored.snapshot_fingerprint,
        'days_key': days_key,
        'compare': compare_enabled,
    }


def generate_analysis(
    section: str,
    days: int,
    compare: bool,
    staff_user,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    if section not in PHASE1_SECTIONS:
        return {'ok': False, 'error': 'invalid_section'}

    if not is_management_ai_enabled():
        return {'ok': False, 'error': 'disabled'}

    days_int, compare_enabled, days_key = normalize_period(days, compare)
    user_id = staff_user.pk

    rl_key = _rate_limit_key(user_id, section, days_key, compare_enabled)
    if cache.get(rl_key):
        return {'ok': False, 'error': 'rate_limited', 'retry_after': RATE_LIMIT_SECONDS}

    lock_key = _lock_key(user_id, section, days_key, compare_enabled)
    if cache.get(lock_key):
        return {'ok': False, 'error': 'in_progress'}

    cache.set(lock_key, '1', LOCK_SECONDS)

    try:
        snapshot = build_section_snapshot(section, days_int, compare_enabled)
        fingerprint = compute_fingerprint(snapshot)

        if not force:
            stored = get_stored_analysis(section, days_key, compare_enabled)
            if stored and stored.snapshot_fingerprint == fingerprint:
                analysis = dict(stored.analysis_json or {})
                _attach_action_targets(analysis, snapshot)
                return {
                    'ok': True,
                    'cached': True,
                    'analysis': analysis,
                    'generated_at': stored.generated_at.isoformat(),
                    'is_stale': False,
                }

        analysis, provider, model = run_management_analysis(
            user=staff_user,
            section=section,
            snapshot=snapshot,
            fingerprint=fingerprint,
        )
        _attach_action_targets(analysis, snapshot)

        save_analysis(
            section=section,
            days_key=days_key,
            compare=compare_enabled,
            snapshot_fingerprint=fingerprint,
            analysis=analysis,
            user=staff_user,
            provider=provider,
            model=model,
        )

        cache.set(rl_key, '1', RATE_LIMIT_SECONDS)

        return {
            'ok': True,
            'cached': False,
            'analysis': analysis,
            'provider': provider,
            'model': model,
            'is_stale': False,
        }
    except ManagementAIDisabled as exc:
        return {'ok': False, 'error': 'disabled', 'detail': str(exc)}
    except ManagementAIError as exc:
        return {'ok': False, 'error': 'provider_failed', 'detail': str(exc)}
    except Exception:
        logger.exception('generate_analysis failed section=%s', section)
        return {'ok': False, 'error': 'internal_error'}
    finally:
        cache.delete(lock_key)
