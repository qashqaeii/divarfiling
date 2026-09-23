"""اجرای confirm برای create_contact."""
from __future__ import annotations

from typing import Any, Dict

from django.urls import reverse

from ai_workspace.services.nl_command.errors import NLCommandError
from ai_workspace.services.nl_command.state import save_state
from ai_workspace.services.nl_command.validators import validate_contact_parse, validated_as_llm_shape
from mobile_api.services.crm_service import create_customer_from_nl
from workspace.services.crm import find_customer_by_phone


def _duplicate_block_message(existing) -> str:
    return f'این شماره قبلاً برای {existing.name} ثبت شده است.'


def confirm_create_contact(user, command_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    existing_id = state.get('created_contact_id')
    if existing_id:
        url = reverse('workspace:crm_detail', kwargs={'customer_id': existing_id})
        return {
            'ok': True,
            'entity_type': 'contact',
            'entity_id': existing_id,
            'url': url,
            'duplicate': True,
            'message': 'مخاطب قبلاً ثبت شده است.',
        }

    validated = dict(state.get('validated') or {})
    prior_explicit = list(validated.get('_explicit_fields') or [])
    revalidated, missing, ambiguous, _err = validate_contact_parse(
        validated_as_llm_shape(validated),
        llm_missing=[],
        llm_ambiguous=[],
        user=user,
        prior_explicit=prior_explicit,
    )
    if missing or ambiguous or not revalidated.get('name'):
        raise NLCommandError('اطلاعات مخاطب کامل یا معتبر نیست.', code='invalid_contact')

    phone = revalidated.get('phone') or ''
    if phone:
        dup = find_customer_by_phone(user, phone)
        if dup:
            raise NLCommandError(
                _duplicate_block_message(dup),
                code='duplicate_contact',
            )

    customer = create_customer_from_nl(user, revalidated)
    state['created_contact_id'] = customer.pk
    save_state(user.pk, command_id, state)

    url = reverse('workspace:crm_detail', kwargs={'customer_id': customer.pk})
    return {
        'ok': True,
        'entity_type': 'contact',
        'entity_id': customer.pk,
        'url': url,
        'message': 'مخاطب با موفقیت ثبت شد.',
    }


def check_phone_duplicate(user, phone: str):
    if not phone:
        return None
    return find_customer_by_phone(user, phone)
