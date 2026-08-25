"""مراحل سفارشی pipeline معامله — تعریف غنی با رنگ، احتمال و کهنگی."""
from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional

from django.db.models import Count

from workspace.constants import (
    DEAL_ACTIVE_STAGES,
    DEAL_STAGE_COLOR_PALETTE,
    DEAL_STAGE_COLORS,
    DEAL_STAGE_ICON_CATALOG,
    DEAL_STAGE_ICONS,
    DEAL_STAGE_KIND_ACTIVE,
    DEAL_STAGE_KIND_LOST,
    DEAL_STAGE_KIND_WON,
    DEAL_STAGE_LOST,
    DEAL_STAGE_PRESETS,
    DEAL_STAGE_WON,
    DEAL_TERMINAL_STAGES,
    DEFAULT_DEAL_STAGE_DEFS,
)
from workspace.models import CRMDeal, WorkspaceSettings

MAX_STAGES = 14
MIN_STAGES = 3
MAX_NAME_LEN = 40
MAX_DESC_LEN = 140


def _settings(user) -> WorkspaceSettings:
    obj, _ = WorkspaceSettings.objects.get_or_create(user=user)
    return obj


def _slugify(name: str, used: set) -> str:
    ascii_slug = re.sub(r'[^a-z0-9]+', '-', (name or '').lower()).strip('-')
    base = ascii_slug[:24] if ascii_slug else 'stage'
    slug = base
    idx = 2
    while slug in used:
        slug = f'{base}-{idx}'
        idx += 1
    used.add(slug)
    return slug


def _lighten_hex(color: str, factor: float = 0.86) -> str:
    raw = (color or '').strip().lstrip('#')
    if len(raw) != 6:
        return '#f1f5f9'
    try:
        r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    except ValueError:
        return '#f1f5f9'
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f'#{r:02x}{g:02x}{b:02x}'


def _normalize_hex(color: str, fallback: str = '#475569') -> str:
    raw = (color or '').strip()
    if re.fullmatch(r'#[0-9A-Fa-f]{6}', raw):
        return raw.lower()
    if re.fullmatch(r'[0-9A-Fa-f]{6}', raw):
        return f'#{raw.lower()}'
    return fallback


def _known_def(name: str) -> Optional[dict]:
    for item in DEFAULT_DEAL_STAGE_DEFS:
        if item['name'] == name:
            return copy.deepcopy(item)
    return None


def _def_from_name(name: str, index: int, used_ids: set) -> dict:
    known = _known_def(name)
    if known:
        used_ids.add(known['id'])
        return known
    bg, color = DEAL_STAGE_COLORS.get(name, ('#f1f5f9', '#475569'))
    palette_color = DEAL_STAGE_COLOR_PALETTE[index % len(DEAL_STAGE_COLOR_PALETTE)]
    color = color or palette_color
    kind = DEAL_STAGE_KIND_ACTIVE
    locked = False
    probability = 40
    rot_days = 5
    if name == DEAL_STAGE_WON:
        kind = DEAL_STAGE_KIND_WON
        locked = True
        probability = 100
        rot_days = 0
    elif name == DEAL_STAGE_LOST:
        kind = DEAL_STAGE_KIND_LOST
        locked = True
        probability = 0
        rot_days = 0
    return {
        'id': _slugify(name, used_ids),
        'name': name,
        'color': color,
        'bg': bg or _lighten_hex(color),
        'icon': DEAL_STAGE_ICONS.get(name, 'fa-handshake'),
        'probability': probability,
        'rot_days': rot_days,
        'kind': kind,
        'description': '',
        'locked': locked,
    }


def normalize_stage_def(raw: Any, index: int, used_ids: set) -> dict:
    if isinstance(raw, str):
        name = raw.strip()
        if not name:
            raise ValueError('نام مرحله خالی است')
        return _def_from_name(name, index, used_ids)

    if not isinstance(raw, dict):
        raise ValueError('فرمت مرحله نامعتبر است')

    name = str(raw.get('name') or '').strip()
    if not name:
        raise ValueError('نام مرحله الزامی است')
    if len(name) > MAX_NAME_LEN:
        raise ValueError(f'نام مرحله «{name[:16]}…» خیلی طولانی است')

    known = _known_def(name)
    requested_id = str(raw.get('id') or '').strip()
    if requested_id and re.fullmatch(r'[a-zA-Z0-9_-]{1,32}', requested_id) and requested_id not in used_ids:
        stage_id = requested_id
        used_ids.add(stage_id)
    elif known and known['id'] not in used_ids:
        stage_id = known['id']
        used_ids.add(stage_id)
    else:
        stage_id = _slugify(name or f'stage-{index}', used_ids)

    color = _normalize_hex(
        raw.get('color') or (known or {}).get('color') or DEAL_STAGE_COLOR_PALETTE[index % len(DEAL_STAGE_COLOR_PALETTE)],
    )
    bg = _normalize_hex(raw.get('bg') or '', fallback='') or _lighten_hex(color)
    icon = str(raw.get('icon') or (known or {}).get('icon') or 'fa-handshake').strip()
    if icon not in DEAL_STAGE_ICON_CATALOG:
        icon = DEAL_STAGE_ICONS.get(name, 'fa-handshake')

    try:
        probability = int(raw.get('probability', (known or {}).get('probability', 50)))
    except (TypeError, ValueError) as exc:
        raise ValueError(f'احتمال مرحله «{name}» نامعتبر است') from exc
    probability = max(0, min(100, probability))

    try:
        rot_days = int(raw.get('rot_days', (known or {}).get('rot_days', 0)) or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'مهلت کهنگی مرحله «{name}» نامعتبر است') from exc
    rot_days = max(0, min(90, rot_days))

    kind = str(raw.get('kind') or (known or {}).get('kind') or DEAL_STAGE_KIND_ACTIVE)
    if kind not in {DEAL_STAGE_KIND_ACTIVE, DEAL_STAGE_KIND_WON, DEAL_STAGE_KIND_LOST}:
        kind = DEAL_STAGE_KIND_ACTIVE

    description = str(raw.get('description') or (known or {}).get('description') or '').strip()
    if len(description) > MAX_DESC_LEN:
        description = description[:MAX_DESC_LEN]

    locked = bool(raw.get('locked') or kind in {DEAL_STAGE_KIND_WON, DEAL_STAGE_KIND_LOST})
    return {
        'id': stage_id,
        'name': name,
        'color': color,
        'bg': bg,
        'icon': icon,
        'probability': probability,
        'rot_days': rot_days,
        'kind': kind,
        'description': description,
        'locked': locked,
    }


def hydrate_stage_defs(raw: Any) -> List[dict]:
    if not raw:
        return copy.deepcopy(DEFAULT_DEAL_STAGE_DEFS)
    if not isinstance(raw, list):
        return copy.deepcopy(DEFAULT_DEAL_STAGE_DEFS)
    used_ids: set = set()
    defs: List[dict] = []
    for idx, item in enumerate(raw):
        try:
            defs.append(normalize_stage_def(item, idx, used_ids))
        except ValueError:
            continue
    if len(defs) < MIN_STAGES:
        return copy.deepcopy(DEFAULT_DEAL_STAGE_DEFS)
    return defs


def validate_deal_stage_defs(raw_list: list) -> List[dict]:
    if not isinstance(raw_list, list):
        raise ValueError('فرمت مراحل نامعتبر است')
    used_ids: set = set()
    defs: List[dict] = []
    seen_names = set()
    for idx, item in enumerate(raw_list):
        stage = normalize_stage_def(item, idx, used_ids)
        if stage['name'] in seen_names:
            raise ValueError(f'مرحله تکراری: {stage["name"]}')
        seen_names.add(stage['name'])
        defs.append(stage)

    if len(defs) < MIN_STAGES:
        raise ValueError(f'حداقل {MIN_STAGES} مرحله لازم است')
    if len(defs) > MAX_STAGES:
        raise ValueError(f'حداکثر {MAX_STAGES} مرحله مجاز است')
    if defs[-2]['name'] != DEAL_STAGE_WON or defs[-1]['name'] != DEAL_STAGE_LOST:
        raise ValueError(f'دو مرحله آخر باید «{DEAL_STAGE_WON}» و «{DEAL_STAGE_LOST}» باشند')

    defs[-2]['kind'] = DEAL_STAGE_KIND_WON
    defs[-2]['locked'] = True
    defs[-2]['probability'] = 100
    defs[-2]['rot_days'] = 0
    defs[-1]['kind'] = DEAL_STAGE_KIND_LOST
    defs[-1]['locked'] = True
    defs[-1]['probability'] = 0
    defs[-1]['rot_days'] = 0
    for item in defs[:-2]:
        item['kind'] = DEAL_STAGE_KIND_ACTIVE
        item['locked'] = False
    return defs


def validate_deal_stages(stages: list) -> List[str]:
    """سازگاری با API قدیمی که فقط نام مراحل را می‌فرستد."""
    defs = validate_deal_stage_defs(stages)
    return [d['name'] for d in defs]


def get_user_deal_stage_defs(user) -> List[dict]:
    return hydrate_stage_defs(_settings(user).crm_deal_stages or [])


def get_user_deal_stages(user) -> List[str]:
    return [d['name'] for d in get_user_deal_stage_defs(user)]


def get_active_deal_stages(user) -> List[str]:
    return [
        d['name']
        for d in get_user_deal_stage_defs(user)
        if d.get('kind') == DEAL_STAGE_KIND_ACTIVE
    ]


def is_valid_deal_stage(user, stage: str) -> bool:
    return stage in get_user_deal_stages(user)


def stage_def_for(user, stage: str) -> Optional[dict]:
    for item in get_user_deal_stage_defs(user):
        if item['name'] == stage:
            return item
    return None


def stage_meta_map(user) -> Dict[str, dict]:
    return {d['name']: d for d in get_user_deal_stage_defs(user)}


def probability_for_stage(user, stage: str) -> int:
    item = stage_def_for(user, stage)
    if item:
        return int(item.get('probability') or 0)
    if stage == DEAL_STAGE_WON:
        return 100
    if stage == DEAL_STAGE_LOST:
        return 0
    return 50


def save_user_deal_stage_defs(user, raw_list: list) -> List[dict]:
    new_defs = validate_deal_stage_defs(raw_list)
    old_defs = get_user_deal_stage_defs(user)
    settings = _settings(user)

    old_by_id = {d['id']: d for d in old_defs}
    renamed = []
    for new in new_defs:
        old = old_by_id.get(new['id'])
        if old and old['name'] != new['name']:
            renamed.append((old['name'], new['name']))
    for old_name, new_name in renamed:
        CRMDeal.objects.filter(user=user, stage=old_name).update(stage=new_name)

    old_names = {d['name'] for d in old_defs}
    # After rename, remaining old names that disappeared fall back to first stage.
    current_names = {d['name'] for d in new_defs}
    removed = old_names - current_names - {new for _, new in renamed}
    fallback = new_defs[0]['name'] if new_defs else 'سرنخ'
    for stage_name in removed:
        CRMDeal.objects.filter(user=user, stage=stage_name).update(stage=fallback)

    settings.crm_deal_stages = new_defs
    settings.save(update_fields=['crm_deal_stages', 'updated_at'])
    return new_defs


def save_user_deal_stages(user, stages: list) -> List[str]:
    defs = save_user_deal_stage_defs(user, stages)
    return [d['name'] for d in defs]


def apply_stage_preset(user, preset_id: str) -> List[dict]:
    preset = DEAL_STAGE_PRESETS.get(preset_id)
    if not preset:
        raise ValueError('قالب مراحل یافت نشد')
    return save_user_deal_stage_defs(user, copy.deepcopy(preset['definitions']))


def reset_user_deal_stages(user) -> List[dict]:
    return save_user_deal_stage_defs(user, copy.deepcopy(DEFAULT_DEAL_STAGE_DEFS))


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


def preset_catalog() -> List[dict]:
    rows = []
    for preset in DEAL_STAGE_PRESETS.values():
        defs = copy.deepcopy(preset['definitions'])
        rows.append({
            'id': preset['id'],
            'name': preset['name'],
            'description': preset['description'],
            'definitions': defs,
            'stage_names': [d['name'] for d in defs],
        })
    return rows


def serialize_stages_payload(user, *, include_presets: bool = True) -> dict:
    from workspace.services.crm_scope import deals_qs

    defs = get_user_deal_stage_defs(user)
    names = [d['name'] for d in defs]
    counts = dict(deals_qs(user).values('stage').annotate(c=Count('id')).values_list('stage', 'c'))
    payload = {
        'stages': names,
        'definitions': defs,
        'won_stage': DEAL_STAGE_WON,
        'lost_stage': DEAL_STAGE_LOST,
        'counts': counts,
        'icons': DEAL_STAGE_ICON_CATALOG,
        'colors': DEAL_STAGE_COLOR_PALETTE,
        'max_stages': MAX_STAGES,
        'min_stages': MIN_STAGES,
    }
    if include_presets:
        payload['presets'] = preset_catalog()
    return payload
