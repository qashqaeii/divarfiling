"""اعتبارسنجی و نرمال‌سازی پیش‌نویس استودیو."""
from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional, Tuple

from workspace.services.property_content_studio.constants import (
    DRAFT_VERSION,
    OUTPUT_FORMATS,
    POSTER_TEMPLATES,
)

_MAX_PAYLOAD_BYTES = 512_000
_MAX_SLIDES = 24
_MAX_POSTER_KEYS = 8
_HEADLINE_MAX = 200
_AI_BODY_MAX = 8000
_AI_TITLE_MAX = 120
_ALLOWED_TOP_KEYS = frozenset({
    'version', 'active_tab', 'format', 'brand_override', 'posters', 'storyboard', 'ai', 'editor',
})
_ALLOWED_TABS = frozenset({'posters', 'divar', 'social', 'share'})
_TEMPLATE_IDS = frozenset(t['id'] for t in POSTER_TEMPLATES)
_FORMAT_IDS = frozenset(OUTPUT_FORMATS.keys())
_PIP_CORNERS = frozenset({'br', 'bl', 'tr', 'tl'})
_PIP_SIZES = frozenset({'s', 'm', 'l'})
_PIP_SHAPES = frozenset({'rounded', 'circle', 'card'})
_PIP_BORDERS = frozenset({'light', 'brand', 'gold'})
_WARMTH = frozenset({'neutral', 'warm', 'cool'})
_FONT_KEYS = frozenset({'vazirmatn', 'estedad', 'lalezar', 'markazi', 'gulzar', 'parastoo'})


class DraftValidationError(ValueError):
    pass


def _clip_str(value: Any, max_len: int) -> str:
    return str(value or '').strip()[:max_len]


def _clip_int(value: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _normalize_visibility(raw: Any) -> Dict[str, bool]:
    from workspace.services.property_content_studio.constants import DEFAULT_VISIBILITY

    out = dict(DEFAULT_VISIBILITY)
    if not isinstance(raw, dict):
        return out
    for key in out:
        if key in raw:
            out[key] = bool(raw[key])
    return out


def _normalize_poster_config(raw: Any, template_id: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    if 'headline' in raw:
        out['headline'] = _clip_str(raw.get('headline'), _HEADLINE_MAX)
    for key in (
        'primary_image_index', 'crop_y', 'img_brightness', 'img_blur', 'img_opacity',
        'headline_scale', 'price_scale', 'pip_image_index', 'pip_crop_y', 'pip_tilt', 'hero_vignette',
    ):
        if key in raw:
            if key == 'primary_image_index' or key == 'pip_image_index':
                out[key] = max(0, _clip_int(raw.get(key), 0, 64, 0))
            elif key == 'crop_y' or key == 'pip_crop_y':
                out[key] = _clip_int(raw.get(key), 0, 100, 50)
            elif key == 'pip_tilt':
                out[key] = _clip_int(raw.get(key), -12, 12, 0)
            elif key == 'hero_vignette':
                out[key] = _clip_int(raw.get(key), 0, 80, 0)
            elif key in ('img_brightness',):
                out[key] = _clip_int(raw.get(key), 40, 160, 100)
            elif key in ('img_blur',):
                out[key] = _clip_int(raw.get(key), 0, 12, 0)
            elif key in ('img_opacity', 'headline_scale', 'price_scale'):
                out[key] = _clip_int(raw.get(key), 35, 160, 100)
    if 'pip_enabled' in raw:
        out['pip_enabled'] = bool(raw.get('pip_enabled'))
    if 'pip_corner' in raw:
        c = str(raw.get('pip_corner') or 'br')
        out['pip_corner'] = c if c in _PIP_CORNERS else 'br'
    if 'pip_size' in raw:
        s = str(raw.get('pip_size') or 'm')
        out['pip_size'] = s if s in _PIP_SIZES else 'm'
    if 'pip_shape' in raw:
        s = str(raw.get('pip_shape') or 'rounded')
        out['pip_shape'] = s if s in _PIP_SHAPES else 'rounded'
    if 'pip_border' in raw:
        b = str(raw.get('pip_border') or 'light')
        out['pip_border'] = b if b in _PIP_BORDERS else 'light'
    if 'hero_warmth' in raw:
        w = str(raw.get('hero_warmth') or 'neutral')
        out['hero_warmth'] = w if w in _WARMTH else 'neutral'
    if 'font_key' in raw:
        fk = str(raw.get('font_key') or 'vazirmatn')
        out['font_key'] = fk if fk in _FONT_KEYS else 'vazirmatn'
    for wkey in ('headline_weight', 'price_weight'):
        if wkey in raw:
            n = _clip_int(raw.get(wkey), 500, 900, 900)
            out[wkey] = 900 if n >= 850 else 700 if n >= 650 else 600 if n >= 550 else 500
    for bkey in ('headline_italic', 'headline_underline', 'price_italic', 'price_underline'):
        if bkey in raw:
            out[bkey] = bool(raw.get(bkey))
    for ckey in ('headline_color', 'price_color', 'brand_primary'):
        if ckey in raw:
            c = str(raw.get(ckey) or '').strip()
            out[ckey] = c if len(c) == 7 and c.startswith('#') else ''
    if 'text_layout' in raw and isinstance(raw.get('text_layout'), dict):
        tl_in = raw['text_layout']
        tl_out: Dict[str, Any] = {}
        for role in ('headline', 'meta', 'price'):
            item = tl_in.get(role)
            if not isinstance(item, dict):
                continue
            try:
                x = float(item.get('x', 0))
                y = float(item.get('y', 0))
                s = float(item.get('s', item.get('scale', 100)))
            except (TypeError, ValueError):
                continue
            tl_out[role] = {
                'x': max(-55.0, min(55.0, x)),
                'y': max(-55.0, min(55.0, y)),
                's': max(50.0, min(180.0, s)),
            }
        if tl_out:
            out['text_layout'] = tl_out
    if 'image_order' in raw and isinstance(raw.get('image_order'), list):
        order = []
        for item in raw['image_order'][:32]:
            order.append(max(0, _clip_int(item, 0, 64, 0)))
        out['image_order'] = order
    return out


def _normalize_slide(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    slide_id = _clip_str(raw.get('id'), 40)
    slide_type = _clip_str(raw.get('type'), 40)
    if not slide_id or not slide_type:
        return None
    slide: Dict[str, Any] = {'id': slide_id, 'type': slide_type}
    if 'title' in raw:
        slide['title'] = _clip_str(raw.get('title'), _HEADLINE_MAX)
    if 'subtitle' in raw:
        slide['subtitle'] = _clip_str(raw.get('subtitle'), 200)
    if 'cta' in raw:
        slide['cta'] = _clip_str(raw.get('cta'), 200)
    if 'price_label' in raw:
        slide['price_label'] = _clip_str(raw.get('price_label'), 120)
    if 'lines' in raw and isinstance(raw.get('lines'), list):
        slide['lines'] = [_clip_str(x, 80) for x in raw['lines'][:16] if _clip_str(x, 80)]
    if 'image_index' in raw:
        idx = raw.get('image_index')
        slide['image_index'] = None if idx is None else max(0, _clip_int(idx, 0, 64, 0))
    if 'image_indices' in raw and isinstance(raw.get('image_indices'), list):
        slide['image_indices'] = [
            max(0, _clip_int(x, 0, 64, 0)) for x in raw['image_indices'][:12]
        ]
    if 'template_id' in raw:
        tid = _clip_str(raw.get('template_id'), 20)
        slide['template_id'] = tid if tid in _TEMPLATE_IDS else ''
    if 'label' in raw:
        slide['label'] = _clip_str(raw.get('label'), 40)
    if 'poster' in raw and isinstance(raw.get('poster'), dict):
        tpl = slide.get('template_id') or 'luxury'
        slide['poster'] = _normalize_poster_config(raw.get('poster'), tpl if tpl in _TEMPLATE_IDS else 'luxury')
    return slide


def _normalize_ai_block(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    divar = raw.get('divar')
    if isinstance(divar, dict):
        titles = []
        for item in (divar.get('titles') or [])[:8]:
            if not isinstance(item, dict):
                continue
            text = _clip_str(item.get('text'), _AI_TITLE_MAX)
            if text:
                titles.append({
                    'style': _clip_str(item.get('style'), 40) or 'پیشنهادی',
                    'text': text,
                })
        out['divar'] = {
            'titles': titles,
            'selected_title_index': _clip_int(divar.get('selected_title_index'), 0, 7, 0),
            'body': _clip_str(divar.get('body'), _AI_BODY_MAX),
            'body_style': _clip_str(divar.get('body_style'), 30),
        }
    social = raw.get('social')
    if isinstance(social, dict):
        caps = []
        for item in (social.get('captions') or [])[:8]:
            if not isinstance(item, dict):
                continue
            text = _clip_str(item.get('text'), 2500)
            if text:
                caps.append({
                    'style': _clip_str(item.get('style'), 40) or 'پیشنهادی',
                    'text': text,
                })
        hashtags = [_clip_str(t, 80) for t in (social.get('hashtags') or [])[:40] if _clip_str(t, 80)]
        out['social'] = {
            'captions': caps,
            'hashtags': hashtags,
            'whatsapp_short': _clip_str(social.get('whatsapp_short'), 1500),
            'whatsapp_full': _clip_str(social.get('whatsapp_full'), 2500),
            'telegram': _clip_str(social.get('telegram'), 2500),
            'ctas': [_clip_str(x, 120) for x in (social.get('ctas') or [])[:8] if _clip_str(x, 120)],
        }
    return out


def validate_and_merge_draft(
    stored: Optional[Dict[str, Any]],
    incoming: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """ادغام incoming روی stored با اعتبارسنجی. خروجی: (merged, meta)."""
    from workspace.services.property_content_studio.draft import empty_draft_payload

    try:
        size = len(json.dumps(incoming, ensure_ascii=False))
    except (TypeError, ValueError):
        raise DraftValidationError('فرمت پیش‌نویس نامعتبر است')
    if size > _MAX_PAYLOAD_BYTES:
        raise DraftValidationError('حجم پیش‌نویس بیش از حد مجاز است')

    base = empty_draft_payload()
    merged = copy.deepcopy(base)
    if stored and isinstance(stored, dict):
        for key in base:
            if key not in stored:
                continue
            if isinstance(base[key], dict) and isinstance(stored[key], dict):
                merged[key] = copy.deepcopy(stored[key])
            else:
                merged[key] = copy.deepcopy(stored[key])

    if not isinstance(incoming, dict):
        raise DraftValidationError('فرمت پیش‌نویس نامعتبر است')

    unknown = set(incoming.keys()) - _ALLOWED_TOP_KEYS
    if unknown:
        raise DraftValidationError('فیلدهای غیرمجاز در پیش‌نویس')

    if 'active_tab' in incoming:
        tab = _clip_str(incoming.get('active_tab'), 20)
        if tab not in _ALLOWED_TABS:
            raise DraftValidationError('تب نامعتبر')
        merged['active_tab'] = tab
    if 'format' in incoming:
        fmt = _clip_str(incoming.get('format'), 20)
        if fmt not in _FORMAT_IDS:
            raise DraftValidationError('فرمت نامعتبر')
        merged['format'] = fmt
    if 'brand_override' in incoming:
        bo = incoming.get('brand_override')
        if bo is not None and not isinstance(bo, dict):
            raise DraftValidationError('brand_override نامعتبر')
        if isinstance(bo, dict):
            if not bo:
                merged['brand_override'] = {}
            else:
                clean: Dict[str, Any] = {}
                for k in ('brand_name', 'consultant_name', 'contact_phone', 'instagram', 'logo_url'):
                    if k in bo:
                        clean[k] = _clip_str(bo.get(k), 200 if k != 'contact_phone' else 20)
                if 'colors' in bo and isinstance(bo['colors'], dict):
                    clean['colors'] = {
                        kk: _clip_str(bo['colors'].get(kk), 16)
                        for kk in ('primary', 'accent', 'text_on_primary')
                        if kk in bo['colors']
                    }
                if 'visibility' in bo:
                    clean['visibility'] = _normalize_visibility(bo.get('visibility'))
                merged['brand_override'] = clean
    if 'posters' in incoming:
        posters_in = incoming.get('posters')
        if not isinstance(posters_in, dict):
            raise DraftValidationError('posters نامعتبر')
        posters = dict(merged.get('posters') or {})
        for tpl, conf in list(posters_in.items())[:_MAX_POSTER_KEYS]:
            if tpl not in _TEMPLATE_IDS:
                continue
            if conf is None:
                posters.pop(tpl, None)
                continue
            posters[tpl] = _normalize_poster_config(conf, tpl)
        merged['posters'] = posters
    if 'storyboard' in incoming:
        sb_in = incoming.get('storyboard')
        if not isinstance(sb_in, dict):
            raise DraftValidationError('storyboard نامعتبر')
        slides = []
        for raw_slide in (sb_in.get('slides') or [])[:_MAX_SLIDES]:
            norm = _normalize_slide(raw_slide)
            if norm:
                slides.append(norm)
        order = []
        for oid in (sb_in.get('order') or [])[:_MAX_SLIDES]:
            sid = _clip_str(oid, 40)
            if sid and sid in {s['id'] for s in slides}:
                order.append(sid)
        if not order:
            order = [s['id'] for s in slides]
        merged['storyboard'] = {'slides': slides, 'order': order}
    if 'ai' in incoming:
        ai_clean = _normalize_ai_block(incoming.get('ai'))
        merged_ai = dict(merged.get('ai') or {})
        for section, data in ai_clean.items():
            merged_ai[section] = {**(merged_ai.get(section) or {}), **data}
        merged['ai'] = merged_ai
    if 'editor' in incoming:
        ed = incoming.get('editor')
        if isinstance(ed, dict):
            merged['editor'] = {
                'open': bool(ed.get('open')),
                'template_id': _clip_str(ed.get('template_id'), 20) or 'luxury',
            }

    merged['version'] = DRAFT_VERSION
    return merged, {'ok': True}
