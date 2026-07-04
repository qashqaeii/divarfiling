"""سرویس پیام هوشمند CRM."""
from __future__ import annotations

from typing import Any, Dict

from workspace.models import Customer

from ai_workspace.constants import FEATURE_CRM_MESSAGE, normalize_crm_tone
from ai_workspace.context_builders import contact_context
from ai_workspace.services.crm_text import sanitize_message_text
from ai_workspace.services.gateway import GatewayResult, run


def generate_message(
    user,
    customer: Customer,
    *,
    channel: str = 'واتساپ',
    tone: str = 'رسمی',
) -> GatewayResult:
    tone = normalize_crm_tone(tone)
    context = contact_context.build(
        customer, user, channel=channel, tone=tone, include_matches=True,
    )
    return run(
        FEATURE_CRM_MESSAGE,
        user,
        context=context,
        entity_type='customer',
        entity_id=str(customer.id),
    )


def result_to_dict(result: GatewayResult) -> Dict[str, Any]:
    text = sanitize_message_text(result.data.get('text') or result.text or '')
    return {
        'ok': True,
        'feature': result.feature,
        'provider': result.provider,
        'model': result.model,
        'is_fallback': result.is_fallback,
        'from_cache': result.from_cache,
        'status': result.status,
        'text': text,
        'latency_ms': result.latency_ms,
    }
