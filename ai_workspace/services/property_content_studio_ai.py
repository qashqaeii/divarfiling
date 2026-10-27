"""AI Content Service — آگهی دیوار و شبکه‌های اجتماعی."""
from __future__ import annotations

from typing import Any, Dict, List

from workspace.models import CRMProperty
from workspace.services.crm_scope import property_for_user
from workspace.services.property_content_studio.adapter import build_studio_property_payload
from workspace.services.property_content_studio.constants import DIVAR_AD_DESCRIPTION_MAX_CHARS, DIVAR_AD_TITLE_MAX_CHARS

from ai_workspace.constants import FEATURE_PROPERTY_CONTENT_STUDIO
from ai_workspace.context_builders import property_context
from ai_workspace.services.gateway import GatewayResult, run
from ai_workspace.services.property_content_studio_payload import (
    normalize_studio_ai_payload,
    validate_studio_ai_payload,
)

_TASK_SCHEMAS = {
    'divar_titles': (
        '{"titles":[{"style":"رسمی","text":"..."},{"style":"جذاب","text":"..."},{"style":"کوتاه","text":"..."}]}'
    ),
    'divar_body': '{"body":"...","style":"رسمی|تبلیغاتی|مختصر|کامل"}',
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
    'divar_titles': 'سه عنوان متفاوت برای آگهی دیوار',
    'divar_body': 'متن کامل آگهی دیوار',
    'social_pack': 'کپشن، هشتگ، واتساپ، تلگرام و CTA',
}


def _studio_context(user, prop: CRMProperty, task: str, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    base = property_context.build(prop, include_address=False)
    studio = build_studio_property_payload(prop, mask_sensitive=False)
    ctx = {
        **base,
        'studio': studio,
        'task': task,
        'divar_title_max': DIVAR_AD_TITLE_MAX_CHARS,
        'divar_description_max': DIVAR_AD_DESCRIPTION_MAX_CHARS,
        'task_label': _TASK_LABELS.get(task, task),
        'task_schema': _TASK_SCHEMAS.get(task, '{}'),
    }
    if extra:
        ctx.update(extra)
    return ctx


def _run_task(user, prop: CRMProperty, task: str, extra: Dict[str, Any] | None = None) -> GatewayResult:
    context = _studio_context(user, prop, task, extra)
    return run(
        FEATURE_PROPERTY_CONTENT_STUDIO,
        user,
        context=context,
        entity_type='crm_property',
        entity_id=f'{prop.pk}:{task}',
    )


def generate_divar_titles(user, property_id: int) -> Dict[str, Any]:
    prop = property_for_user(user, property_id)
    if not prop:
        raise LookupError('property')
    result = _run_task(user, prop, 'divar_titles')
    data = normalize_studio_ai_payload('divar_titles', result.data, result.text)
    if not validate_studio_ai_payload('divar_titles', data):
        raise ValueError('invalid_ai_response')
    return _result_dict(result, data)


def generate_divar_body(user, property_id: int, style: str) -> Dict[str, Any]:
    prop = property_for_user(user, property_id)
    if not prop:
        raise LookupError('property')
    result = _run_task(user, prop, 'divar_body', {'body_style': style})
    data = normalize_studio_ai_payload('divar_body', result.data, result.text)
    if not validate_studio_ai_payload('divar_body', data):
        raise ValueError('invalid_ai_response')
    return _result_dict(result, data)


def generate_social_pack(user, property_id: int) -> Dict[str, Any]:
    prop = property_for_user(user, property_id)
    if not prop:
        raise LookupError('property')
    result = _run_task(user, prop, 'social_pack')
    data = normalize_studio_ai_payload('social_pack', result.data, result.text)
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
