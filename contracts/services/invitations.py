"""دعوتنامه و ارسال SMS — idempotent و امن."""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.phone_utils import normalize_phone
from accounts.services.sms import SmsError, send_simple_sms
from contracts.constants import CONTRACT_STATUS_SENT
from contracts.models import Contract, ContractAccessToken, ContractInvitation
from contracts.services.audit import log_audit_event
from contracts.services.lifecycle import ContractError
from contracts.services.state_machine import InvalidStateTransition, transition_contract
from contracts.services.notifications import notify_contract_event
from contracts.services.tokens import generate_bearer_token

logger = logging.getLogger(__name__)


def _build_accept_url(request, raw_token: str) -> str:
    path = reverse('public_accept', kwargs={'token': raw_token})
    if request:
        return request.build_absolute_uri(path)
    site = getattr(settings, 'SITE_URL', '') or 'https://divarfiling.ir'
    return f'{site.rstrip("/")}{path}'


def _create_invitation(contract, version, *, party=None, witness=None, mobile: str):
    raw, token_hash = generate_bearer_token()
    expires = timezone.now() + timedelta(days=30)
    inv = ContractInvitation.objects.create(
        contract=contract,
        version=version,
        party=party,
        witness=witness,
        token_hash=token_hash,
        mobile=normalize_phone(mobile),
        expires_at=expires,
    )
    return inv, raw


@transaction.atomic
def send_invitations(contract: Contract, *, user=None, request=None) -> list:
    version = contract.current_version
    if not version or not version.is_published:
        raise ValueError('نسخه منتشر نشده است.')

    if contract.status == CONTRACT_STATUS_SENT:
        existing = contract.invitations.filter(version=version, is_revoked=False).exists()
        if existing:
            raise ContractError('دعوتنامه‌ها قبلاً ارسال شده‌اند. از ارسال مجدد استفاده کنید.')

    invitations = []
    for party in version.parties.all():
        if not party.mobile:
            continue
        inv, raw = _create_invitation(contract, version, party=party, mobile=party.mobile)
        invitations.append((inv, raw))
        _send_invitation_sms(inv, contract, raw, request)
        log_audit_event(
            contract, 'INVITATION_CREATED', version=version,
            party=party, actor_user=user, request=request,
        )

    for witness in version.witnesses.all():
        if not witness.mobile:
            continue
        inv, raw = _create_invitation(contract, version, witness=witness, mobile=witness.mobile)
        invitations.append((inv, raw))
        _send_invitation_sms(inv, contract, raw, request)

    try:
        transition_contract(contract, CONTRACT_STATUS_SENT)
    except InvalidStateTransition as exc:
        raise ContractError(str(exc)) from exc
    notify_contract_event(contract, 'sent', user=user)
    return [inv for inv, _ in invitations]


def _send_invitation_sms(
    inv: ContractInvitation,
    contract: Contract,
    raw_token: str,
    request=None,
    *,
    is_resend: bool = False,
) -> None:
    url = _build_accept_url(request, raw_token)
    ctype = contract.get_contract_type_display()
    msg = (
        f'فایلینگ دیوار\n'
        f'قرارداد {ctype} برای تأیید شما ارسال شد.\n'
        f'{url}\n'
        f'این پیام به معنی ثبت رسمی قرارداد نیست.'
    )
    now = timezone.now()
    try:
        result = send_simple_sms(inv.mobile, msg)
        inv.sms_status = 'sent'
        inv.sms_sent_at = now
        inv.last_sent_at = now
        if is_resend:
            inv.resend_count = (inv.resend_count or 0) + 1
        if hasattr(result, 'message_id'):
            inv.sms_provider_ref = str(result.message_id or '')
    except SmsError as exc:
        logger.warning('contract invite SMS failed')
        inv.sms_status = 'failed'
    inv.save(update_fields=['sms_status', 'sms_sent_at', 'sms_provider_ref', 'resend_count', 'last_sent_at'])
    log_audit_event(
        contract, 'SMS_SENT', version=inv.version,
        metadata={'invitation_id': inv.pk, 'status': inv.sms_status, 'resend': is_resend},
    )


@transaction.atomic
def resend_invitation(invitation: ContractInvitation, *, request=None) -> tuple:
    if invitation.is_revoked:
        raise ValueError('دعوتنامه ابطال شده است.')
    raw, new_hash = generate_bearer_token()
    invitation.token_hash = new_hash
    invitation.save(update_fields=['token_hash'])
    _send_invitation_sms(invitation, invitation.contract, raw, request, is_resend=True)
    return invitation, raw


@transaction.atomic
def create_final_access_tokens(contract: Contract, *, request=None) -> list:
    version = contract.current_version
    tokens = []
    for party in version.parties.all():
        raw, token_hash = generate_bearer_token()
        tok = ContractAccessToken.objects.create(
            contract=contract, party=party, token_hash=token_hash,
        )
        tokens.append((tok, raw))
        _send_final_sms(tok, contract, raw, request)
        log_audit_event(contract, 'ACCESS_LINK_CREATED', version=version,
                        party=party, metadata={'token_id': tok.pk})
    for witness in version.witnesses.all():
        raw, token_hash = generate_bearer_token()
        tok = ContractAccessToken.objects.create(
            contract=contract, witness=witness, token_hash=token_hash,
        )
        tokens.append((tok, raw))
        _send_final_sms(tok, contract, raw, request)
    return [t for t, _ in tokens]


def _send_final_sms(tok: ContractAccessToken, contract: Contract, raw_token: str, request=None) -> None:
    path = reverse('public_view', kwargs={'token': raw_token})
    if request:
        url = request.build_absolute_uri(path)
    else:
        site = getattr(settings, 'SITE_URL', '') or 'https://divarfiling.ir'
        url = f'{site.rstrip("/")}{path}'
    mobile = tok.party.mobile if tok.party_id else (tok.witness.mobile if tok.witness_id else '')
    if not mobile:
        return
    msg = f'فایلینگ دیوار\nقرارداد شما نهایی شد.\nمشاهده: {url}'
    try:
        send_simple_sms(mobile, msg)
    except SmsError:
        logger.warning('final contract SMS failed')
