"""Context builder for public handover acceptance pages."""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.urls import reverse

from contracts.services.handover_wizard import ROLE_LABELS, build_handover_wizard_context

SIDE_LABELS = {
    'delivered_by': 'تحویل‌دهنده',
    'received_by': 'تحویل‌گیرنده',
}


def build_handover_accept_context(
    invitation,
    *,
    token: str,
    request=None,
    **extra: Any,
) -> Dict[str, Any]:
    handover = invitation.handover
    wizard = build_handover_wizard_context(handover, step='review')
    review = wizard.get('review') or {}
    side = invitation.side or ''
    role = ''
    if side == 'delivered_by':
        party = review.get('delivered') or {}
        role = party.get('role_label') or ROLE_LABELS.get(party.get('role', ''), '')
    elif side == 'received_by':
        party = review.get('received') or {}
        role = party.get('role_label') or ROLE_LABELS.get(party.get('role', ''), '')

    pdf_path = reverse('public_handover_invitation_pdf', kwargs={'token': token})
    pdf_url = request.build_absolute_uri(pdf_path) if request else pdf_path

    ctx = {
        'handover': handover,
        'invitation': invitation,
        'snapshot': handover.snapshot_json or {},
        'review': review,
        'property_data': wizard.get('property_data') or {},
        'side_label': SIDE_LABELS.get(side, 'طرف قرارداد'),
        'role_label': role,
        'handover_date_jalali': review.get('date_display') or '',
        'handover_time_display': review.get('time_display') or '',
        'contract_number': handover.contract.internal_number,
        'handover_type_label': handover.get_handover_type_display(),
        'pdf_url': pdf_url,
        'content_hash_short': (
            (handover.content_hash[:12] + '…') if handover.content_hash and len(handover.content_hash) > 12
            else (handover.content_hash or '')
        ),
    }
    ctx.update(extra)
    return ctx
