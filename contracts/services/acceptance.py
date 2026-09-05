"""تأیید قرارداد توسط طرفین."""
from __future__ import annotations

import secrets

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from contracts.constants import IDENTITY_STATUS_MOBILE_VERIFIED, VERIFICATION_MISMATCH_MSG
from contracts.models import ContractAcceptance, ContractInvitation, ContractSignature
from contracts.services.audit import log_audit_event
from contracts.services.hashing import compute_content_hash
from contracts.services.invitations import create_final_access_tokens
from contracts.services.lifecycle import finalize_contract, update_acceptance_status
from contracts.services.notifications import notify_contract_event
from contracts.services.otp_service import verify_contract_otp


def _client_ip(request) -> str:
    if request is None:
        return ''
    forwarded = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    return forwarded or (request.META.get('REMOTE_ADDR') or '')[:64]


def _user_agent(request) -> str:
    if request is None:
        return ''
    return (request.META.get('HTTP_USER_AGENT') or '')[:500]


def _verify_identity(invitation: ContractInvitation, phone: str, national_id: str) -> None:
    from accounts.phone_utils import normalize_phone
    normalized = normalize_phone(phone)
    if normalize_phone(invitation.mobile) != normalized:
        raise ValueError(VERIFICATION_MISMATCH_MSG)
    entity = invitation.party or invitation.witness
    if entity and (entity.national_id or '').strip():
        if national_id.strip() != (entity.national_id or '').strip():
            raise ValueError(VERIFICATION_MISMATCH_MSG)


@transaction.atomic
def accept_contract(
    invitation: ContractInvitation,
    *,
    phone: str,
    national_id: str,
    otp_code: str = '',
    ack_checkboxes: list,
    signature_image=None,
    request=None,
    otp_already_verified: bool = False,
) -> ContractAcceptance:
    contract = invitation.contract
    version = invitation.version

    _verify_identity(invitation, phone, national_id)

    if not otp_already_verified:
        verify_contract_otp(invitation, phone, otp_code, request=request)

    content_hash = version.content_hash or compute_content_hash(version)

    acceptance = ContractAcceptance.objects.create(
        contract=contract,
        version=version,
        party=invitation.party,
        witness=invitation.witness,
        invitation=invitation,
        accepted_content_hash=content_hash,
        content_hash=content_hash,
        mobile=phone,
        national_id_entered=national_id,
        otp_verified_at=timezone.now(),
        ip_address=_client_ip(request) or None,
        user_agent=_user_agent(request),
        session_identifier=secrets.token_hex(16),
        ack_checkboxes=ack_checkboxes,
    )

    ContractSignature.objects.create(acceptance=acceptance, signature_type='otp_acceptance')
    if signature_image:
        sig = acceptance.signature
        sig.signature_type = 'drawn_signature'
        if hasattr(signature_image, 'read'):
            raw = signature_image.read()
            sig.image.save('signature.png', ContentFile(raw), save=False)
        else:
            sig.image = signature_image
        sig.save()

    if invitation.party_id:
        party = invitation.party
        party.mobile_verified = True
        party.national_id_claimed = True
        party.identity_verification_status = IDENTITY_STATUS_MOBILE_VERIFIED
        party.save(update_fields=[
            'mobile_verified', 'national_id_claimed', 'identity_verification_status',
        ])
        log_audit_event(contract, 'PARTY_ACCEPTED', version=version, party=party, request=request)
        notify_contract_event(contract, 'accepted', party_name=party.display_name)
    else:
        witness = invitation.witness
        witness.mobile_verified = True
        witness.accepted_at = timezone.now()
        witness.save(update_fields=['mobile_verified', 'accepted_at'])
        log_audit_event(contract, 'WITNESS_ACCEPTED', version=version, request=request)

    version.is_locked = True
    version.save(update_fields=['is_locked'])

    update_acceptance_status(contract)
    if contract.status == 'fully_accepted':
        finalize_contract(contract, request=request)
        create_final_access_tokens(contract, request=request)
        notify_contract_event(contract, 'finalized')

    return acceptance
