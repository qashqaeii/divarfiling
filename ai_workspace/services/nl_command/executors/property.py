"""اجرای confirm برای create_personal_property."""
from __future__ import annotations

from typing import Any, Dict

from django.urls import reverse

from ai_workspace.services.nl_command.errors import NLCommandError
from ai_workspace.services.nl_command.state import save_state
from ai_workspace.services.nl_command.validators_property import (
    build_nl_property_title,
    validate_property_parse,
    validated_as_llm_shape,
)
from mobile_api.services.crm_service import create_property_from_nl


def confirm_create_personal_property(user, command_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    existing_id = state.get('created_property_id')
    if existing_id:
        url = reverse('workspace:crm_property_detail', kwargs={'property_id': existing_id})
        return {
            'ok': True,
            'entity_type': 'property',
            'entity_id': existing_id,
            'url': url,
            'duplicate': True,
            'message': 'فایل شخصی قبلاً ثبت شده است.',
        }

    validated = dict(state.get('validated') or {})
    revalidated, missing, ambiguous, _err = validate_property_parse(
        validated_as_llm_shape(validated),
        llm_missing=[],
        llm_ambiguous=[],
    )
    if missing or ambiguous or not revalidated.get('area') or not revalidated.get('deal_mode'):
        raise NLCommandError('اطلاعات فایل کامل یا معتبر نیست.', code='invalid_property')

    title = build_nl_property_title(revalidated)
    if not title:
        raise NLCommandError('عنوان فایل قابل ساخت نیست.', code='invalid_property')
    revalidated['title'] = title

    prop = create_property_from_nl(user, revalidated)
    state['created_property_id'] = prop.pk
    save_state(user.pk, command_id, state)

    url = reverse('workspace:crm_property_detail', kwargs={'property_id': prop.pk})
    return {
        'ok': True,
        'entity_type': 'property',
        'entity_id': prop.pk,
        'url': url,
        'message': 'فایل شخصی با موفقیت ثبت شد.',
    }
