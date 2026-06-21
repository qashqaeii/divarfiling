"""مراحل سفارشی pipeline معامله — B2."""
from __future__ import annotations

from typing import List

from workspace.constants import (
    DEAL_ACTIVE_STAGES, DEAL_STAGE_LOST, DEAL_STAGE_WON, DEAL_STAGES, DEAL_TERMINAL_STAGES,
)
from workspace.models import CRMDeal, WorkspaceSettings


def _settings(user) -> WorkspaceSettings:
    obj, _ = WorkspaceSettings.objects.get_or_create(user=user)
    return obj


def get_user_deal_stages(user) -> List[str]:
    stages = _settings(user).crm_deal_stages or []
    if stages:
        return list(stages)
    return list(DEAL_STAGES)


def get_active_deal_stages(user) -> List[str]:
    return [s for s in get_user_deal_stages(user) if s not in DEAL_TERMINAL_STAGES]


def is_valid_deal_stage(user, stage: str) -> bool:
    return stage in get_user_deal_stages(user)


def validate_deal_stages(stages: list) -> List[str]:
    if not isinstance(stages, list):
        raise ValueError('فرمت مراحل نامعتبر است')
    cleaned = []
    seen = set()
    for raw in stages:
        name = str(raw or '').strip()
        if not name:
            continue
        if len(name) > 60:
            raise ValueError(f'نام مرحله «{name[:20]}…» خیلی طولانی است')
        if name in seen:
            raise ValueError(f'مرحله تکراری: {name}')
        seen.add(name)
        cleaned.append(name)
    if len(cleaned) < 3:
        raise ValueError('حداقل ۳ مرحله لازم است')
    if len(cleaned) > 12:
        raise ValueError('حداکثر ۱۲ مرحله مجاز است')
    if cleaned[-2] != DEAL_STAGE_WON or cleaned[-1] != DEAL_STAGE_LOST:
        raise ValueError(f'دو مرحله آخر باید «{DEAL_STAGE_WON}» و «{DEAL_STAGE_LOST}» باشند')
    return cleaned


def save_user_deal_stages(user, stages: list) -> List[str]:
    new_stages = validate_deal_stages(stages)
    old_stages = get_user_deal_stages(user)
    settings = _settings(user)

    for idx, old_name in enumerate(old_stages):
        if idx >= len(new_stages):
            break
        new_name = new_stages[idx]
        if old_name != new_name:
            CRMDeal.objects.filter(user=user, stage=old_name).update(stage=new_name)

    removed = set(old_stages) - set(new_stages)
    fallback = new_stages[0] if new_stages else 'سرنخ'
    for stage_name in removed:
        CRMDeal.objects.filter(user=user, stage=stage_name).update(stage=fallback)

    settings.crm_deal_stages = new_stages
    settings.save(update_fields=['crm_deal_stages', 'updated_at'])
    return new_stages


def active_stages_for_user(user) -> List[str]:
    """مراحل فعال — سازگار با تنظیمات سفارشی یا پیش‌فرض."""
    custom = _settings(user).crm_deal_stages or []
    if custom:
        return get_active_deal_stages(user)
    return list(DEAL_ACTIVE_STAGES)


def is_won_stage(stage: str) -> bool:
    return stage == DEAL_STAGE_WON


def is_lost_stage(stage: str) -> bool:
    return stage == DEAL_STAGE_LOST


def is_terminal_stage(stage: str) -> bool:
    return stage in DEAL_TERMINAL_STAGES
