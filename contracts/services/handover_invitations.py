"""دعوتنامه و SMS صورت‌جلسه تحویل."""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.phone_utils import normalize_phone
from accounts.services.sms import SmsError, send_simple_sms
from contracts.models import ContractHandover, ContractHandoverInvitation
from contracts.services.tokens import generate_bearer_token

logger = logging.getLogger(__name__)


def _accept_url(request, raw_token: str) -> str:
    path = reverse('public_handover_accept', kwargs={'token': raw_token})
    if request:
        return request.build_absolute_uri(path)
    site = getattr(settings, 'SITE_URL', '') or 'https://divarfiling.ir'
    return f'{site.rstrip("/")}{path}'


@transaction.atomic
def send_handover_invitations(handover: ContractHandover, *, request=None) -> list:
    snap = handover.snapshot_json or {}
    created = []
    for side in ('delivered_by', 'received_by'):
        party = snap.get(side) or {}
        mobile = party.get('mobile')
        if not mobile:
            continue
        raw, token_hash = generate_bearer_token()
        inv = ContractHandoverInvitation.objects.create(
            handover=handover,
            side=side,
            first_name=party.get('first_name', ''),
            last_name=party.get('last_name', ''),
            national_id=party.get('national_id', ''),
            mobile=normalize_phone(mobile),
            token_hash=token_hash,
            expires_at=timezone.now() + timedelta(days=14),
        )
        _send_sms(inv, handover, raw, request)
        created.append(inv)
    return created


def _send_sms(inv: ContractHandoverInvitation, handover: ContractHandover, raw: str, request=None) -> None:
    url = _accept_url(request, raw)
    msg = (
        f'فایلینگ دیوار\n'
        f'صورت‌جلسه تحویل ملک ({handover.contract.internal_number})\n'
        f'{url}'
    )
    now = timezone.now()
    try:
        send_simple_sms(inv.mobile, msg)
        inv.sms_status = 'sent'
        inv.sms_sent_at = now
        inv.last_sent_at = now
    except SmsError:
        logger.warning('handover SMS failed')
        inv.sms_status = 'failed'
    inv.save(update_fields=['sms_status', 'sms_sent_at', 'last_sent_at'])


def lookup_handover_invitation(raw_token: str) -> ContractHandoverInvitation | None:
    from contracts.models import ContractHandoverInvitation
    from contracts.services.tokens import hash_token
    if not raw_token:
        return None
    return (
        ContractHandoverInvitation.objects.select_related('handover', 'handover__contract')
        .filter(token_hash=hash_token(raw_token), is_revoked=False)
        .first()
    )
