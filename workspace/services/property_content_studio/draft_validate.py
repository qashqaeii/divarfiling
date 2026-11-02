"""اعتبارسنجی و نرمال‌سازی پیش‌نویس استودیو."""
from __future__ import annotations

import copy
import json
import math
from typing import Any, Dict, List, Optional, Tuple

from workspace.services.property_content_studio.constants import (
    ALL_POSTER_TEMPLATE_IDS,
    DEFAULT_POSTER_TEMPLATE,
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
_TEMPLATE_IDS = ALL_POSTER_TEMPLATE_IDS
_ACTIVE_TEMPLATE_IDS = frozenset(t['id'] for t in POSTER_TEMPLATES)
_FORMAT_IDS = frozenset(OUTPUT_FORMATS.keys())
_PIP_CORNERS = frozenset({'br', 'bl', 'tr', 'tl'})
_PIP_SIZES = frozenset({'s', 'm', 'l'})
_PIP_SHAPES = frozenset({'rounded', 'circle', 'card'})
_PIP_BORDERS = frozenset({'light', 'brand', 'gold'})
_WARMTH = frozenset({'neutral', 'warm', 'cool'})
_FONT_KEYS = frozenset({'vazirmatn', 'estedad', 'lalezar', 'markazi', 'gulzar', 'parastoo'})
_LAYER_TYPES = frozenset({
    'text', 'bound_text', 'image', 'template_frame', 'logo', 'shape', 'group', 'decor',
})
_LAYER_STYLE_KEYS = frozenset({
    'fontKey', 'fontSize', 'fontWeight', 'fill', 'align', 'direction', 'lineHeight',
    'background', 'borderRadius', 'opacity', 'textPreset', 'objectFit', 'cropPanX',
    'cropPanY', 'cropZoom', 'fontStyle', 'textDecoration', 'brightness', 'blur',
    'imgOpacity', 'warmth', 'vignette', 'verticalAlign',
})
_BRAND_BINDING_FIELDS = frozenset({'contact_footer', 'consultant_name', 'contact_phone'})
_MAX_SCENE_LAYERS = 48
_MAX_SCENE_PARENT_DEPTH = 4
_SCENE_ALIGN = frozenset({'left', 'center', 'right'})
_SCENE_OBJECT_FIT = frozenset({'cover', 'contain', 'fill'})


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


def _finite_float(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise DraftValidationError(f'scene: {field} نامعتبر')
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise DraftValidationError(f'scene: {field} نامعتبر')
    if not math.isfinite(n):
        raise DraftValidationError(f'scene: {field} نامعتبر')
    return n


def _clip_float(value: Any, lo: float, hi: float, *, field: str) -> float:
    n = _finite_float(value, field=field)
    return max(lo, min(hi, n))


def _normalize_scene_binding(raw: Any) -> Optional[Dict[str, str]]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise DraftValidationError('scene: binding نامعتبر')
    mode = raw.get('mode')
    if mode not in ('linked', 'override', 'detached'):
        mode = 'linked'
    source = raw.get('source')
    if source not in ('property', 'user', 'brand'):
        source = 'property'
    field = _clip_str(raw.get('field'), 64)
    if source == 'brand':
        if field not in _BRAND_BINDING_FIELDS:
            return None
        return {'source': 'brand', 'field': field, 'mode': mode}
    if source == 'user' and not field:
        return {'source': 'user', 'field': field, 'mode': mode}
    if source == 'property' and not field:
        return None
    return {'source': source, 'field': field, 'mode': mode}


def _normalize_scene_style(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise DraftValidationError('scene: style نامعتبر')
    out: Dict[str, Any] = {}
    for key in raw:
        if key not in _LAYER_STYLE_KEYS:
            continue
        val = raw[key]
        if key == 'fontKey':
            fk = str(val or 'vazirmatn')
            out[key] = fk if fk in _FONT_KEYS else 'vazirmatn'
        elif key == 'fontSize':
            out[key] = _clip_float(val, 8, 200, field='fontSize')
        elif key == 'fontWeight':
            out[key] = int(_clip_float(val, 400, 900, field='fontWeight'))
        elif key == 'fill':
            out[key] = _clip_str(val, 16)
        elif key == 'align':
            a = str(val or 'right')
            out[key] = a if a in _SCENE_ALIGN else 'right'
        elif key == 'direction':
            out[key] = 'ltr' if val == 'ltr' else 'rtl'
        elif key == 'lineHeight':
            out[key] = _clip_float(val, 0.8, 3.0, field='lineHeight')
        elif key == 'background':
            out[key] = _clip_str(val, 32)
        elif key == 'borderRadius':
            out[key] = _clip_float(val, 0, 999, field='borderRadius')
        elif key == 'opacity':
            out[key] = _clip_float(val, 0, 1, field='style.opacity')
        elif key == 'textPreset':
            out[key] = _clip_str(val, 32)
        elif key == 'objectFit':
            fit = str(val or 'cover')
            out[key] = fit if fit in _SCENE_OBJECT_FIT else 'cover'
        elif key in ('cropPanX', 'cropPanY'):
            out[key] = _clip_float(val, 0, 100, field=key)
        elif key == 'cropZoom':
            out[key] = _clip_float(val, 0.5, 3.0, field='cropZoom')
        elif key == 'fontStyle':
            if str(val) == 'italic':
                out[key] = 'italic'
        elif key == 'textDecoration':
            if str(val) == 'underline':
                out[key] = 'underline'
        elif key == 'brightness':
            out[key] = _clip_float(val, 40, 160, field='brightness')
        elif key == 'blur':
            out[key] = _clip_float(val, 0, 12, field='blur')
        elif key == 'imgOpacity':
            out[key] = _clip_float(val, 35, 100, field='imgOpacity')
        elif key == 'warmth':
            w = str(val or '')
            if w in ('neutral', 'warm', 'cool'):
                out[key] = w
        elif key == 'vignette':
            out[key] = _clip_float(val, 0, 80, field='vignette')
        elif key == 'verticalAlign':
            va = str(val or '')
            if va in ('top', 'center', 'bottom'):
                out[key] = va
    return out


def _scene_parent_depth(layer_id: str, by_id: Dict[str, Dict[str, Any]]) -> int:
    depth = 0
    current = layer_id
    seen: set[str] = set()
    while True:
        layer = by_id.get(current)
        if not layer:
            return depth
        parent = layer.get('parentId')
        if not parent:
            return depth
        if parent in seen:
            raise DraftValidationError('scene: parentId حلقه دارد')
        seen.add(parent)
        depth += 1
        if depth > _MAX_SCENE_PARENT_DEPTH:
            raise DraftValidationError('scene: عمق parentId بیش از حد')
        current = parent


def _validate_and_normalize_scene(raw: Any, template_id: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise DraftValidationError('scene نامعتبر')

    schema_version = _clip_int(raw.get('schemaVersion'), 1, 3, 2)

    default_fmt = _clip_str(template_id, 20) or DEFAULT_POSTER_TEMPLATE
    base_canvas = OUTPUT_FORMATS.get('story', {'width': 1080, 'height': 1920})
    canvas_in = raw.get('canvas')
    if canvas_in is not None and not isinstance(canvas_in, dict):
        raise DraftValidationError('scene: canvas نامعتبر')
    if isinstance(canvas_in, dict):
        fmt = _clip_str(canvas_in.get('format'), 20) or 'story'
        if fmt not in _FORMAT_IDS:
            fmt = 'story'
        fmt_spec = OUTPUT_FORMATS.get(fmt, base_canvas)
        width = int(_clip_float(
            canvas_in.get('width', fmt_spec.get('width', 1080)),
            320,
            4096,
            field='canvas.width',
        ))
        height = int(_clip_float(
            canvas_in.get('height', fmt_spec.get('height', 1920)),
            320,
            4096,
            field='canvas.height',
        ))
        canvas = {'width': width, 'height': height, 'format': fmt}
    else:
        canvas = {
            'width': int(base_canvas.get('width', 1080)),
            'height': int(base_canvas.get('height', 1920)),
            'format': 'story',
        }

    tpl = _clip_str(raw.get('templateId') or template_id or DEFAULT_POSTER_TEMPLATE, 32) or DEFAULT_POSTER_TEMPLATE
    if tpl not in _TEMPLATE_IDS:
        tpl = DEFAULT_POSTER_TEMPLATE

    layers_in = raw.get('layers')
    if layers_in is None:
        layers_in = []
    if not isinstance(layers_in, list):
        raise DraftValidationError('scene: layers نامعتبر')
    if len(layers_in) > _MAX_SCENE_LAYERS:
        raise DraftValidationError('scene: layers بیش از حد')

    cw = canvas['width']
    ch = canvas['height']
    layers: List[Dict[str, Any]] = []
    ids: set[str] = set()
    for item in layers_in:
        if not isinstance(item, dict):
            raise DraftValidationError('scene: layer نامعتبر')
        layer_id = _clip_str(item.get('id'), 40)
        if not layer_id:
            raise DraftValidationError('scene: layer id نامعتبر')
        if layer_id in ids:
            raise DraftValidationError('scene: layer id تکراری')
        layer_type = _clip_str(item.get('type'), 40) or 'text'
        if layer_type not in _LAYER_TYPES:
            raise DraftValidationError('scene: type نامعتبر')
        parent_raw = item.get('parentId')
        parent_id = _clip_str(parent_raw, 40) if parent_raw not in (None, '') else None
        layer = {
            'id': layer_id,
            'type': layer_type,
            'name': _clip_str(item.get('name') or layer_id, 80),
            'visible': item.get('visible') is not False,
            'locked': bool(item.get('locked')),
            'parentId': parent_id,
            'x': _clip_float(item.get('x', 0), -cw, cw * 2, field='x'),
            'y': _clip_float(item.get('y', 0), -ch, ch * 2, field='y'),
            'width': _clip_float(item.get('width', 200), 1, cw * 2, field='width'),
            'height': _clip_float(item.get('height', 48), 1, ch * 2, field='height'),
            'rotation': _clip_float(item.get('rotation', 0), -360, 360, field='rotation'),
            'opacity': _clip_float(item.get('opacity', 1), 0, 1, field='opacity'),
            'binding': _normalize_scene_binding(item.get('binding')),
            'style': _normalize_scene_style(item.get('style')),
        }
        if 'text' in item:
            layer['text'] = _clip_str(item.get('text'), 2000)
        if item.get('assetRef'):
            ar = _clip_str(item.get('assetRef'), 80)
            if ar.startswith('tpl:') or ar.startswith('/'):
                layer['assetRef'] = ar
        if 'imageIndex' in item:
            layer['imageIndex'] = max(0, _clip_int(item.get('imageIndex'), 0, 64, 0))
        if item.get('templateRole'):
            layer['templateRole'] = _clip_str(item.get('templateRole'), 32)
        ids.add(layer_id)
        layers.append(layer)

    by_id = {layer['id']: layer for layer in layers}
    for layer in layers:
        parent_id = layer.get('parentId')
        if parent_id and parent_id not in by_id:
            raise DraftValidationError('scene: parentId نامعتبر')
        _scene_parent_depth(layer['id'], by_id)

    layer_ids = [layer['id'] for layer in layers]
    order_in = raw.get('layerOrder')
    if order_in is None:
        order = list(layer_ids)
    else:
        if not isinstance(order_in, list):
            raise DraftValidationError('scene: layerOrder نامعتبر')
        if len(order_in) > _MAX_SCENE_LAYERS:
            raise DraftValidationError('scene: layerOrder بیش از حد')
        order = []
        for oid in order_in:
            sid = _clip_str(oid, 40)
            if not sid:
                raise DraftValidationError('scene: layerOrder نامعتبر')
            if sid not in ids:
                raise DraftValidationError('scene: layerOrder نامعتبر')
            if sid in order:
                raise DraftValidationError('scene: layerOrder تکراری')
            order.append(sid)
        if set(order) != ids:
            raise DraftValidationError('scene: layerOrder نامعتبر')

    render_mode = 'legacy' if raw.get('renderMode') == 'legacy' else 'layers'
    scene: Dict[str, Any] = {
        'schemaVersion': schema_version,
        'canvas': canvas,
        'templateId': tpl,
        'renderMode': render_mode,
        'layers': layers,
        'layerOrder': order,
    }
    if raw.get('migratedAt'):
        scene['migratedAt'] = _clip_str(raw.get('migratedAt'), 40)
    return scene


def _normalize_poster_flat_fields(raw: Dict[str, Any], out: Dict[str, Any]) -> None:
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


def _normalize_poster_config(raw: Any, template_id: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Any] = {}
    poster_settings = raw.get('posterSettings')
    flat: Dict[str, Any] = {}
    if isinstance(poster_settings, dict):
        flat.update(poster_settings)
    for key, value in raw.items():
        if key in ('scene', 'posterSettings'):
            continue
        flat[key] = value
    _normalize_poster_flat_fields(flat, out)
    if 'scene' in raw:
        out['scene'] = _validate_and_normalize_scene(raw.get('scene'), template_id)
    if isinstance(poster_settings, dict):
        settings_out: Dict[str, Any] = {}
        _normalize_poster_flat_fields(poster_settings, settings_out)
        if settings_out:
            out['posterSettings'] = settings_out
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
        tpl = slide.get('template_id') or DEFAULT_POSTER_TEMPLATE
        slide['poster'] = _normalize_poster_config(
            raw.get('poster'),
            tpl if tpl in _TEMPLATE_IDS else DEFAULT_POSTER_TEMPLATE,
        )
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
                'template_id': (
                    _clip_str(ed.get('template_id'), 20)
                    if _clip_str(ed.get('template_id'), 20) in _ACTIVE_TEMPLATE_IDS
                    else DEFAULT_POSTER_TEMPLATE
                ),
            }

    merged['version'] = DRAFT_VERSION
    return merged, {'ok': True}
