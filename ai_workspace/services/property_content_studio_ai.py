"""AI Content Service — آگهی دیوار و شبکه‌های اجتماعی."""
from __future__ import annotations

from typing import Any, Dict

from workspace.models import CRMProperty
from workspace.services.crm_scope import property_for_user
from workspace.services.property_content_studio.adapter import (
    build_studio_property_payload,
    format_divar_facts_outline,
)
from workspace.services.property_content_studio.constants import (
    DIVAR_AD_DESCRIPTION_MAX_CHARS,
    DIVAR_AD_TITLE_MAX_CHARS,
    DIVAR_BODY_STYLE_GUIDES,
    POSTER_AD_HEADLINE_MAX_CHARS,
)

from ai_workspace.constants import FEATURE_PROPERTY_CONTENT_STUDIO
from ai_workspace.context_builders import property_context
from ai_workspace.services.gateway import GatewayResult, run
from ai_workspace.services.property_content_studio_payload import (
    enforce_property_facts,
    normalize_studio_ai_payload,
    validate_studio_ai_payload,
)

_DIVAR_EMOJI_RULES = """
- Use clean Unicode emojis at the START of lines (one emoji per line), like real premium Divar listings.
- Preferred set: ✅ 📍 📐 🏠 🛗 🚗 📦 💰 🔑 ✨ 📞 — only when the line matches a fact in context.
- ✅ for highlights or confirmed specs; 📍 location; 📐 size/rooms/floor/year; 🏠 type; 🛗/🚗/📦 only if true in context; 💰 price/deposit/rent.
- Do NOT spam emoji, use cartoon chains, or put emoji inside Divar titles.
- End the body with a short CTA line starting with 📞 (e.g. هماهنگی بازدید — without inventing a phone number).
"""

_DIVAR_BODY_STRUCTURE = """
Suggested body flow (adapt to body_style_guide length):
1) Opening hook (1–2 lines, no fake urgency)
2) One line per item in divar_facts_outline (with matching emoji)
3) Extra detail_chips / amenities from studio if not already covered
4) Optional rewrite of description_excerpt (if non-empty) in fresh words
5) Closing CTA with 📞
"""

_TASK_SCHEMAS = {
    'divar_titles': (
        '{"titles":['
        '{"style":"رسمی حرفه‌ای","text":"..."},'
        '{"style":"جذاب و کلیک‌پذیر","text":"..."},'
        '{"style":"کوتاه دیوار","text":"..."},'
        '{"style":"لوکس","text":"..."},'
        '{"style":"مشاورانه","text":"..."}'
        ']}'
    ),
    'divar_body': '{"body":"...","style":"label from body_style_label in context"}',
    'poster_headlines': (
        '{"titles":['
        '{"style":"کوتاه واکنشی","text":"..."},'
        '{"style":"لوکس","text":"..."},'
        '{"style":"مشخصات‌محور","text":"..."},'
        '{"style":"محله‌محور","text":"..."},'
        '{"style":"بازدید","text":"..."}'
        ']}'
    ),
    'social_pack': (
        '{"captions":[{"style":"حرفه‌ای","text":"..."},{"style":"صمیمی","text":"..."},{"style":"کوتاه","text":"..."}],'
        '"hashtags":["#..."],'
        '"whatsapp_short":"...",'
        '"whatsapp_full":"...",'
        '"telegram":"...",'
        '"ctas":["...","...","..."]}'
    ),
}

_TASK_LABELS = {
    'divar_titles': 'پنج عنوان حرفه‌ای و متنوع برای آگهی دیوار',
    'divar_body': 'متن کامل آگهی دیوار با ایموجی حرفه‌ای و همه مشخصات ثبت‌شده',
    'poster_headlines': 'پنج عنوان تبلیغاتی کوتاه برای پوستر و استوری شبکه‌های اجتماعی',
    'social_pack': 'کپشن، هشتگ، واتساپ، تلگرام و CTA',
}


def _divar_copy_rules(task: str) -> str:
    base = _DIVAR_EMOJI_RULES.strip()
    if task == 'divar_titles':
        return (
            base
            + '\n- Titles: include deal type, area or rooms, and neighborhood/city when available; vary angle across the 5 styles.'
        )
    if task == 'poster_headlines':
        return (
            '- Short overlay headlines for Instagram story / poster templates (NOT Divar listing titles).\n'
            f'- Each title max {POSTER_AD_HEADLINE_MAX_CHARS} characters; 3–8 words when possible; one line only.\n'
            '- No emoji, no quotation marks, no phone, no invented amenities.\n'
            '- Use deal_mode, area, rooms, neighborhood/city, and one real benefit from context when space allows.\n'
            '- Vary angle across styles: punchy, luxury, specs-first, location-first, visit-oriented.\n'
            '- Natural Persian; avoid long chains with «و».'
        )
    if task == 'divar_body':
        return (
            base
            + '\n'
            + _DIVAR_BODY_STRUCTURE.strip()
            + '\n- Include every line from divar_facts_outline unless body_style_guide says shorter.'
            + '\n- Never copy tab_text CRM notes verbatim.'
        )
    return base


def _resolve_body_style(style: str) -> tuple[str, str, str]:
    key = (style or 'formal').strip().lower()
    meta = DIVAR_BODY_STYLE_GUIDES.get(key) or DIVAR_BODY_STYLE_GUIDES['formal']
    if key not in DIVAR_BODY_STYLE_GUIDES:
        key = 'formal'
    return key, meta['label'], meta['guide']


def _studio_context(
    user,
    prop: CRMProperty,
    task: str,
    extra: Dict[str, Any] | None = None,
    *,
    mask_sensitive: bool = False,
) -> Dict[str, Any]:
    base = property_context.build(
        prop,
        include_address=False,
        include_crm_notes=False,
        mask_sensitive=mask_sensitive,
    )
    studio = build_studio_property_payload(prop, mask_sensitive=mask_sensitive)
    ctx = {
        **base,
        'studio': studio,
        'task': task,
        'divar_title_max': DIVAR_AD_TITLE_MAX_CHARS,
        'divar_description_max': DIVAR_AD_DESCRIPTION_MAX_CHARS,
        'poster_headline_max': POSTER_AD_HEADLINE_MAX_CHARS,
        'divar_facts_outline': format_divar_facts_outline(studio),
        'divar_copy_rules': _divar_copy_rules(task),
        'task_label': _TASK_LABELS.get(task, task),
        'task_schema': _TASK_SCHEMAS.get(task, '{}'),
        'property_facts': {
            'has_parking': bool(prop.has_parking),
            'has_storage': bool(prop.has_storage),
            'has_elevator': bool(prop.has_elevator),
            'property_type': prop.property_type or '',
            'deal_mode': prop.deal_mode or '',
            'area': prop.area,
            'rooms': prop.rooms or '',
        },
    }
    if extra:
        ctx.update(extra)
    if task == 'divar_body':
        key, label, guide = _resolve_body_style(str(ctx.get('body_style') or 'formal'))
        ctx['body_style'] = key
        ctx['body_style_label'] = label
        ctx['body_style_guide'] = guide
    return ctx


def _run_task(
    user,
    prop: CRMProperty,
    task: str,
    extra: Dict[str, Any] | None = None,
    *,
    mask_sensitive: bool = False,
) -> GatewayResult:
    context = _studio_context(user, prop, task, extra, mask_sensitive=mask_sensitive)
    return run(
        FEATURE_PROPERTY_CONTENT_STUDIO,
        user,
        context=context,
        entity_type='crm_property',
        entity_id=f'{prop.pk}:{task}',
    )


def generate_divar_titles(user, property_id: int, *, mask_sensitive: bool = False) -> Dict[str, Any]:
    prop = property_for_user(user, property_id)
    if not prop:
        raise LookupError('property')
    result = _run_task(user, prop, 'divar_titles', mask_sensitive=mask_sensitive)
    data = normalize_studio_ai_payload('divar_titles', result.data, result.text)
    data = enforce_property_facts(prop, 'divar_titles', data)
    if not validate_studio_ai_payload('divar_titles', data):
        raise ValueError('invalid_ai_response')
    return _result_dict(result, data)


def generate_divar_body(
    user,
    property_id: int,
    style: str,
    *,
    mask_sensitive: bool = False,
) -> Dict[str, Any]:
    prop = property_for_user(user, property_id)
    if not prop:
        raise LookupError('property')
    style_key, _, _ = _resolve_body_style(style)
    result = _run_task(
        user,
        prop,
        'divar_body',
        {'body_style': style_key},
        mask_sensitive=mask_sensitive,
    )
    data = normalize_studio_ai_payload('divar_body', result.data, result.text)
    data = enforce_property_facts(prop, 'divar_body', data)
    if not validate_studio_ai_payload('divar_body', data):
        raise ValueError('invalid_ai_response')
    data['style'] = style_key
    return _result_dict(result, data)


def generate_poster_headlines(user, property_id: int, *, mask_sensitive: bool = False) -> Dict[str, Any]:
    prop = property_for_user(user, property_id)
    if not prop:
        raise LookupError('property')
    result = _run_task(user, prop, 'poster_headlines', mask_sensitive=mask_sensitive)
    data = normalize_studio_ai_payload('poster_headlines', result.data, result.text)
    data = enforce_property_facts(prop, 'poster_headlines', data)
    if not validate_studio_ai_payload('poster_headlines', data):
        raise ValueError('invalid_ai_response')
    return _result_dict(result, data)


def generate_social_pack(user, property_id: int, *, mask_sensitive: bool = False) -> Dict[str, Any]:
    prop = property_for_user(user, property_id)
    if not prop:
        raise LookupError('property')
    result = _run_task(user, prop, 'social_pack', mask_sensitive=mask_sensitive)
    data = normalize_studio_ai_payload('social_pack', result.data, result.text)
    data = enforce_property_facts(prop, 'social_pack', data)
    if not validate_studio_ai_payload('social_pack', data):
        raise ValueError('invalid_ai_response')
    return _result_dict(result, data)


def _result_dict(result: GatewayResult, data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'ok': True,
        'feature': result.feature,
        'provider': result.provider,
        'model': result.model,
        'is_fallback': result.is_fallback,
        'from_cache': result.from_cache,
        'latency_ms': result.latency_ms,
        'data': data,
    }
