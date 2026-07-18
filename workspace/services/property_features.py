"""ویژگی‌های تفصیلی فایل شخصی CRM — هم‌تراز با LISTING_FEATURE_COLUMNS."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.constants import (
    LISTING_FEATURE_COLUMNS,
    LISTING_FEATURE_GROUPS,
    PROPERTY_BOOL_AMENITY_LABELS,
)

# فیلدهایی که در فرم CRM فیلد اختصاصی / چک‌باکس دارند
CRM_FEATURE_SKIP_KEYS = frozenset({
    'تعداد کل طبقات ساختمان',  # → total_floors
    'وضعیت سکونت',  # → is_vacant / tenant
}) | frozenset(PROPERTY_BOOL_AMENITY_LABELS) | frozenset({
    'بالکن', 'جکوزی', 'سونا', 'حیوان خانگی مجاز', 'قابل معاوضه',
    'بازسازی شده', 'سند', 'مجوز ساخت',
    'پارکینگ', 'انباری', 'آسانسور',
})

CRM_FEATURE_FORM_KEYS = tuple(
    key for key in LISTING_FEATURE_COLUMNS if key not in CRM_FEATURE_SKIP_KEYS
)

CRM_FEATURE_FORM_GROUPS = tuple(
    {
        'id': group['id'],
        'title': group['title'],
        'icon': group['icon'],
        'accent': group.get('accent', ''),
        'keys': tuple(k for k in group['keys'] if k in CRM_FEATURE_FORM_KEYS),
    }
    for group in LISTING_FEATURE_GROUPS
    if any(k in CRM_FEATURE_FORM_KEYS for k in group['keys'])
)


def extract_feature_data_from_listing_data(data: Optional[dict]) -> Dict[str, str]:
    """کپی کلیدهای فرم CRM از data آگهی."""
    raw = data or {}
    out: Dict[str, str] = {}
    for key in CRM_FEATURE_FORM_KEYS:
        val = raw.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if text and text.lower() not in ('nan', 'none', '-', 'null'):
            out[key] = text
    return out


def parse_feature_data_from_post(post) -> Dict[str, str]:
    """
    خواندن ویژگی‌ها از POST:
    - feat__{key}=value (اولویت)
    - یا features_json (JSON object)
    کلیدهای skip نادیده گرفته می‌شوند.
    """
    import json

    out: Dict[str, str] = {}
    getlist = getattr(post, 'getlist', None)
    keys = list(post.keys()) if hasattr(post, 'keys') else []
    has_feat_fields = any(str(k).startswith('feat__') for k in keys)

    if has_feat_fields:
        for key in keys:
            if not str(key).startswith('feat__'):
                continue
            feat_key = str(key)[6:].strip()
            if feat_key not in CRM_FEATURE_FORM_KEYS:
                continue
            if callable(getlist):
                vals = getlist(key)
                text = str(vals[0] if vals else '').strip()
            else:
                text = str(post.get(key) or '').strip()
            if text:
                out[feat_key] = text
        return out

    raw_json = (post.get('features_json') or '').strip() if hasattr(post, 'get') else ''
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                for key, val in parsed.items():
                    k = str(key).strip()
                    if k not in CRM_FEATURE_FORM_KEYS:
                        continue
                    text = str(val).strip() if val is not None else ''
                    if text:
                        out[k] = text
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return out


def feature_form_groups_with_values(feature_data: Optional[dict] = None) -> List[Dict[str, Any]]:
    """گروه‌های فرم با مقدار فعلی برای رندر قالب."""
    data = feature_data or {}
    groups: List[Dict[str, Any]] = []
    for group in CRM_FEATURE_FORM_GROUPS:
        items = [
            {
                'key': key,
                'label': key,
                'value': str(data.get(key) or '').strip(),
                'input_name': f'feat__{key}',
            }
            for key in group['keys']
        ]
        if items:
            groups.append({
                'id': group['id'],
                'title': group['title'],
                'icon': group['icon'],
                'items': items,
            })
    return groups


def feature_profile_groups_from_data(feature_data: Optional[dict]) -> List[Dict[str, Any]]:
    """گروه‌های نمایش پرونده/اشتراک عمومی از feature_data."""
    data = feature_data or {}
    groups: List[Dict[str, Any]] = []
    for group in LISTING_FEATURE_GROUPS:
        items: List[Dict[str, Any]] = []
        for key in group['keys']:
            if key in CRM_FEATURE_SKIP_KEYS and key not in data:
                continue
            val = data.get(key)
            if val is None or not str(val).strip():
                continue
            text = str(val).strip()
            items.append({
                'key': key,
                'label': key,
                'value': text,
                'state': 'neutral',
                'known': True,
            })
        if items:
            groups.append({
                'id': group['id'],
                'title': group['title'],
                'icon': group['icon'],
                'accent': group.get('accent', ''),
                'items': items,
            })
    return groups
