"""دسترسی و ماسک خروجی تطبیق برای فایل‌های اشتراکی."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.models import CRMProperty
from workspace.services.crm_property_share import build_property_share_context, location_display
from workspace.services.crm_scope import properties_qs, property_for_user


def can_create_property_public_link(user, prop: CRMProperty) -> bool:
    """لینک عمومی فقط برای مالک یا اشتراک کامل — نه دریافت‌کننده محرمانه."""
    if not user or not prop:
        return False
    if prop.user_id == user.id:
        return True
    ctx = build_property_share_context(user, prop)
    return ctx.is_collaborative and not ctx.mask_sensitive


def _confidential_reasons() -> List[str]:
    return ['فایل اشتراک محرمانه']


def mask_crm_match_for_viewer(user, prop: CRMProperty, match: Dict[str, Any]) -> Dict[str, Any]:
    ctx = build_property_share_context(user, prop)
    out = dict(match)
    if not ctx.mask_sensitive:
        out['mask_sensitive'] = False
        return out
    out['mask_sensitive'] = True
    out['title'] = (prop.property_type or 'فایل').strip() or 'فایل محرمانه'
    out['price_label'] = ''
    out['neighborhood'] = location_display(prop, mask=True)
    out['city'] = prop.city or ''
    out['area'] = None
    out['rooms'] = ''
    out['property_type'] = prop.property_type or ''
    out['link'] = ''
    out['image'] = ''
    out['public_share_url'] = ''
    out['share_url'] = ''
    out['internal_url'] = ''
    out['token'] = ''
    out['reasons'] = _confidential_reasons()
    out['advertiser'] = ''
    out['deal_mode'] = ''
    return out


def match_alert_snapshot_for_viewer(user, match: Dict[str, Any]) -> Dict[str, Any]:
    """اسنپ‌شات اعلان — بدون افشای داده محرمانه."""
    safe = match
    if match.get('source') == 'crm' and match.get('property_id'):
        try:
            pid = int(match['property_id'])
        except (TypeError, ValueError):
            pid = 0
        if pid:
            prop = property_for_user(user, pid)
            if prop:
                safe = mask_crm_match_for_viewer(user, prop, match)
    return {
        'title': safe.get('title', ''),
        'price_label': safe.get('price_label', ''),
        'neighborhood': safe.get('neighborhood', ''),
        'reasons': list(safe.get('reasons') or [])[:4],
        'score': safe.get('score', 0),
    }


def sanitize_crm_matches_for_viewer(user, matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not matches:
        return []
    pids = [
        int(m['property_id'])
        for m in matches
        if m.get('source') == 'crm' and m.get('property_id')
    ]
    props = {p.pk: p for p in properties_qs(user).filter(pk__in=pids)}
    sanitized: List[Dict[str, Any]] = []
    for match in matches:
        if match.get('source') != 'crm':
            sanitized.append(match)
            continue
        try:
            pid = int(match.get('property_id') or 0)
        except (TypeError, ValueError):
            continue
        prop = props.get(pid)
        if prop is None:
            prop = property_for_user(user, pid)
        if prop is None:
            continue
        sanitized.append(mask_crm_match_for_viewer(user, prop, match))
    return sanitized


def sanitize_match_payload_for_viewer(user, payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload)
    out['crm_matches'] = sanitize_crm_matches_for_viewer(user, out.get('crm_matches') or [])
    groups = []
    for group in out.get('match_groups') or []:
        item = dict(group)
        item['crm_matches'] = sanitize_crm_matches_for_viewer(user, group.get('crm_matches') or [])
        groups.append(item)
    out['match_groups'] = groups
    return out
