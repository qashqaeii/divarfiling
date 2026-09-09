"""چرخه عمر صورت‌جلسه تحویل."""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict

from django.db import transaction
from django.utils import timezone

from contracts.constants import HANDOVER_STATUS_DRAFT, HANDOVER_STATUS_FINALIZED, HANDOVER_STATUS_SENT
from contracts.models import Contract, ContractHandover, ContractHandoverAcceptance, ContractHandoverInvitation
from contracts.services.scope import contract_for_user


class HandoverError(Exception):
    pass


def _canonical_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def build_handover_snapshot(handover: ContractHandover) -> Dict[str, Any]:
    snap = copy.deepcopy(handover.snapshot_json or {})
    snap.update({
        'handover_type': handover.handover_type,
        'handover_date': handover.handover_date.isoformat() if handover.handover_date else None,
        'handover_time': handover.handover_time.isoformat() if handover.handover_time else None,
        'notes': handover.notes,
        'contract_internal_number': handover.contract.internal_number,
    })
    return snap


def compute_handover_hash(handover: ContractHandover) -> str:
    payload = build_handover_snapshot(handover)
    return hashlib.sha256(_canonical_json(payload).encode('utf-8')).hexdigest()


@transaction.atomic
def create_handover(user, contract_id: int, *, request=None) -> ContractHandover:
    contract = contract_for_user(user, contract_id)
    if not contract:
        raise HandoverError('قرارداد یافت نشد.')
    if contract.status != 'finalized':
        raise HandoverError('صورت‌جلسه تحویل فقط برای قرارداد نهایی‌شده امکان‌پذیر است.')
    if not contract.deal_id:
        raise HandoverError('صورت‌جلسه تحویل فقط برای قراردادهای متصل به معامله امکان‌پذیر است.')
    if contract.handovers.filter(status__in=(HANDOVER_STATUS_DRAFT, HANDOVER_STATUS_SENT)).exists():
        raise HandoverError('یک صورت‌جلسه تحویل فعال وجود دارد.')

    version = contract.current_version
    snap = version.snapshot_json if version and version.snapshot_json else {}
    parties = snap.get('parties') or []
    handover = ContractHandover.objects.create(
        contract=contract,
        version=version,
        deal=contract.deal,
        user=user,
        handover_type='initial_delivery',
        status=HANDOVER_STATUS_DRAFT,
        snapshot_json={
            'property': snap.get('property') or {},
            'parties': parties,
            'keys': [],
            'meters': [],
            'conditions': [],
            'equipment': [],
            'delivered_by': {},
            'received_by': {},
        },
    )
    return handover


@transaction.atomic
def save_handover_step(handover: ContractHandover, step: str, data: Dict[str, Any], *, user=None) -> ContractHandover:
    if handover.is_locked:
        raise HandoverError('صورت‌جلسه قفل شده و قابل ویرایش نیست.')
    snap = dict(handover.snapshot_json or {})
    if step == 'basic':
        if data.get('handover_date'):
            from workspace.services.jalali_input import parse_jalali_date_string
            parsed = parse_jalali_date_string(data['handover_date']) if isinstance(data['handover_date'], str) else data['handover_date']
            if parsed:
                handover.handover_date = parsed
        if data.get('handover_time'):
            from datetime import datetime
            try:
                handover.handover_time = datetime.strptime(data['handover_time'], '%H:%M').time()
            except ValueError:
                pass
        snap['delivered_by'] = data.get('delivered_by') or {}
        snap['received_by'] = data.get('received_by') or {}
        handover.notes = data.get('notes', handover.notes)
    elif step == 'keys':
        snap['keys'] = data.get('keys') or []
    elif step == 'meters':
        snap['meters'] = data.get('meters') or []
    elif step == 'conditions':
        snap['conditions'] = data.get('conditions') or []
    elif step == 'equipment':
        snap['equipment'] = data.get('equipment') or []
    handover.snapshot_json = snap
    handover.save(update_fields=['handover_date', 'handover_time', 'notes', 'snapshot_json', 'updated_at'])
    return handover


@transaction.atomic
def publish_handover(handover: ContractHandover, *, user=None, request=None) -> ContractHandover:
    if handover.is_locked:
        return handover
    from contracts.services.handover_wizard import sync_handover_delivery_parties

    sync_handover_delivery_parties(handover)
    handover.refresh_from_db()
    snap = handover.snapshot_json or {}
    if not snap.get('delivered_by') or not snap.get('received_by'):
        raise HandoverError('تحویل‌دهنده و تحویل‌گیرنده الزامی است. به مرحله «مشخصات» برگردید و طرفین را انتخاب کنید.')
    if not handover.handover_date:
        raise HandoverError('تاریخ تحویل ثبت نشده است. به مرحله «مشخصات» برگردید و تاریخ را وارد کنید.')
    handover.content_hash = compute_handover_hash(handover)
    handover.status = HANDOVER_STATUS_SENT
    handover.save(update_fields=['content_hash', 'status', 'updated_at'])
    from contracts.services.handover_invitations import send_handover_invitations
    invitations = send_handover_invitations(handover, request=request)
    if not invitations:
        raise HandoverError('شماره موبایل طرفین تحویل در قرارداد ثبت نشده است.')
    return handover


@transaction.atomic
def accept_handover(
    invitation: ContractHandoverInvitation,
    *,
    phone: str,
    national_id: str,
    otp_code: str = '',
    ack_checkboxes: list,
    request=None,
    otp_already_verified: bool = False,
) -> ContractHandoverAcceptance:
    from accounts.phone_utils import normalize_phone
    from contracts.constants import VERIFICATION_MISMATCH_MSG
    from contracts.services.otp_service import verify_handover_otp

    handover = invitation.handover
    normalized = normalize_phone(phone)
    if normalize_phone(invitation.mobile) != normalized:
        raise HandoverError(VERIFICATION_MISMATCH_MSG)
    if national_id.strip() != (invitation.national_id or '').strip():
        raise HandoverError(VERIFICATION_MISMATCH_MSG)

    if not otp_already_verified:
        verify_handover_otp(invitation, phone, otp_code, request=request)

    content_hash = handover.content_hash or compute_handover_hash(handover)
    acc, created = ContractHandoverAcceptance.objects.get_or_create(
        handover=handover,
        side=invitation.side,
        defaults={
            'invitation': invitation,
            'accepted_content_hash': content_hash,
            'mobile': normalized,
            'national_id_entered': national_id,
            'otp_verified_at': timezone.now(),
            'ack_checkboxes': ack_checkboxes,
        },
    )
    if not created:
        raise HandoverError('این طرف قبلاً تأیید کرده است.')
    required_sides = {'delivered_by', 'received_by'}
    if required_sides.issubset(set(handover.acceptances.values_list('side', flat=True))):
        finalize_handover(handover, request=request)
    return acc


@transaction.atomic
def finalize_handover(handover: ContractHandover, *, request=None) -> ContractHandover:
    handover = ContractHandover.objects.select_for_update().get(pk=handover.pk)
    if handover.status == HANDOVER_STATUS_FINALIZED:
        return handover
    if handover.acceptances.count() < 2:
        raise HandoverError('هر دو طرف تأیید نکرده‌اند.')
    handover.content_hash = compute_handover_hash(handover)
    handover.is_locked = True
    handover.status = HANDOVER_STATUS_FINALIZED
    handover.finalized_at = timezone.now()
    handover.save()
    from contracts.services.handover_pdf import generate_handover_pdf
    generate_handover_pdf(handover, request=request)
    return handover
