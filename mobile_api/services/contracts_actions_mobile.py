"""عملیات حساس قرارداد — API موبایل (بدون PATCH ویزارد)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from contracts.constants import CONTRACT_STATUS_DRAFT
from contracts.services.lifecycle import (
    ContractError,
    cancel_contract,
    copy_contract,
    create_new_version,
    prepare_for_send,
    validate_contract_ready,
)
from contracts.models import ContractInvitation
from contracts.services.invitations import resend_invitation, send_invitations
from contracts.services.scope import can_edit_contract, contract_for_user
from mobile_api.services.contracts_mobile import assert_mobile_contract_license


ALLOWED_ACTIONS = frozenset({'prepare_send', 'cancel', 'copy', 'resend_invitation', 'new_version'})


def contract_action_payload(
    user,
    contract_id: int,
    action: str,
    *,
    reason: str = '',
    invitation_id: int | None = None,
    request=None,
) -> Optional[Dict[str, Any]]:
    assert_mobile_contract_license(user)
    contract = contract_for_user(user, contract_id)
    if not contract:
        return None

    action = (action or '').strip().lower()
    if action not in ALLOWED_ACTIONS:
        raise ValueError('عملیات نامعتبر است.')

    if action == 'prepare_send':
        if contract.status != CONTRACT_STATUS_DRAFT:
            raise ValueError('فقط پیش‌نویس قابل ارسال است.')
        if not can_edit_contract(user, contract):
            raise ValueError('این قرارداد قابل ارسال نیست.')
        try:
            prepare_for_send(contract, user=user, request=request)
            send_invitations(contract, user=user, request=request)
        except ContractError as exc:
            raise ValueError(str(exc)) from exc
        contract.refresh_from_db()
    elif action == 'cancel':
        if not can_edit_contract(user, contract):
            raise ValueError('این قرارداد قابل لغو نیست.')
        try:
            cancel_contract(contract, reason or '', user=user, request=request)
        except ContractError as exc:
            raise ValueError(str(exc)) from exc
        contract.refresh_from_db()
    elif action == 'copy':
        try:
            new_contract = copy_contract(contract, user=user, request=request)
        except ContractError as exc:
            raise ValueError(str(exc)) from exc
        return _action_result(user, new_contract)
    elif action == 'new_version':
        if not can_edit_contract(user, contract):
            raise ValueError('نسخه جدید قابل ایجاد نیست.')
        try:
            create_new_version(contract, user=user, request=request)
        except ContractError as exc:
            raise ValueError(str(exc)) from exc
        contract.refresh_from_db()
    elif action == 'resend_invitation':
        if not invitation_id:
            raise ValueError('شناسه دعوت‌نامه الزامی است.')
        inv = ContractInvitation.objects.filter(contract=contract, pk=invitation_id).first()
        if not inv:
            raise ValueError('دعوت‌نامه یافت نشد.')
        try:
            resend_invitation(inv, request=request)
        except (ContractError, ValueError) as exc:
            raise ValueError(str(exc)) from exc
        contract.refresh_from_db()

    return _action_result(user, contract)


def _action_result(user, contract) -> Dict[str, Any]:
    version = contract.current_version
    validation_errors = validate_contract_ready(contract, version) if version else []
    return {
        'contract_id': contract.pk,
        'status': contract.status,
        'status_label': contract.get_status_display(),
        'can_edit': can_edit_contract(user, contract),
        'validation_errors': validation_errors,
        'validation_count': len(validation_errors),
    }
