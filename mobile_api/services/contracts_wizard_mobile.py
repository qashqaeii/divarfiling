"""API موبایل — ویزارد قرارداد (GET/PATCH)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils.dateparse import parse_datetime

from contracts.constants import WIZARD_DISPLAY_STEPS, WIZARD_STEP_LABELS
from contracts.services.clause_ux import build_clause_sections, clause_warnings, get_applicable_clauses
from contracts.services.lifecycle import ContractError, save_wizard_step, validate_contract_ready
from contracts.services.prefill import ensure_default_parties
from contracts.services.scope import can_edit_contract, contract_for_user
from contracts.services.wizard_json import (
    PATCHABLE_WIZARD_STEPS,
    WizardJsonError,
    display_step_keys,
    parse_wizard_json_step,
    wizard_choices_payload,
)
from mobile_api.services.contracts_mobile import assert_mobile_contract_license, workspace_paths


def _resolve_step(contract, requested: Optional[str]) -> str:
    step = (requested or contract.wizard_step or 'parties').strip()
    allowed = display_step_keys(contract.contract_type)
    if step == 'review':
        return 'review'
    if step not in allowed:
        step = contract.wizard_step if contract.wizard_step in allowed else allowed[0]
    return step


def _wizard_data_snapshot(wizard: Dict[str, Any]) -> Dict[str, Any]:
    keys = PATCHABLE_WIZARD_STEPS | {'selected_clauses', 'jv'}
    out = {}
    for key in keys:
        if key in wizard:
            out[key] = wizard[key]
    return out


def _display_steps(contract_type: str) -> List[Dict[str, str]]:
    rows = WIZARD_DISPLAY_STEPS.get(contract_type) or WIZARD_DISPLAY_STEPS['lease']
    return [{'key': key, 'label': label} for key, label in rows]


def _clause_ui(contract, wizard: Dict[str, Any]) -> Dict[str, Any]:
    from contracts.services.clause_ux import build_clause_context

    context_data = build_clause_context(wizard, contract.contract_type)
    return {
        'available_clauses': get_applicable_clauses(
            contract.contract_type, context_data, user=contract.user,
        ),
        'clause_sections': build_clause_sections(
            contract.contract_type,
            wizard,
            user=contract.user,
            is_staff=False,
        ),
        'clause_step_warnings': clause_warnings(wizard, contract.contract_type),
    }


def contract_wizard_get_payload(
    user,
    contract_id: int,
    *,
    step: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    assert_mobile_contract_license(user)
    contract = contract_for_user(user, contract_id)
    if not contract:
        return None

    wizard = dict(contract.wizard_data or {})
    ensured = ensure_default_parties(wizard.get('parties') or [], contract.contract_type)
    if ensured != (wizard.get('parties') or []):
        wizard['parties'] = ensured
        contract.wizard_data = wizard
        contract.save(update_fields=['wizard_data', 'updated_at'])

    current = _resolve_step(contract, step)
    display = _display_steps(contract.contract_type)
    step_keys = [row['key'] for row in display]
    step_index = step_keys.index(current) if current in step_keys else 0

    validation_errors: List[str] = []
    if contract.current_version:
        validation_errors = validate_contract_ready(contract, contract.current_version)

    payload: Dict[str, Any] = {
        'contract_id': contract.pk,
        'contract_type': contract.contract_type,
        'contract_type_label': contract.get_contract_type_display(),
        'status': contract.status,
        'status_label': contract.get_status_display(),
        'internal_number': contract.internal_number or '',
        'wizard_step': contract.wizard_step or step_keys[0],
        'current_step': current,
        'step_index': step_index,
        'step_total': len(display),
        'display_steps': display,
        'wizard_step_labels': {k: WIZARD_STEP_LABELS.get(k, k) for k in step_keys},
        'wizard_data': _wizard_data_snapshot(wizard),
        'can_edit': can_edit_contract(user, contract),
        'picker_enabled': contract.deal_id is None,
        'validation_errors': validation_errors,
        'validation_count': len(validation_errors),
        'choices': wizard_choices_payload(contract.contract_type),
        'workspace_paths': workspace_paths(contract),
        'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
    }
    if current in ('clauses', 'review') or wizard.get('selected_clauses') or wizard.get('optional_clauses'):
        payload['clause_ui'] = _clause_ui(contract, wizard)
    return payload


@transaction.atomic
def contract_wizard_patch_payload(
    user,
    contract_id: int,
    *,
    step: str,
    data: Any,
    if_match_updated_at: Optional[str] = None,
    request=None,
) -> Dict[str, Any]:
    assert_mobile_contract_license(user)
    contract = contract_for_user(user, contract_id)
    if not contract:
        raise ValueError('قرارداد یافت نشد.')
    if not can_edit_contract(user, contract):
        raise ValueError('این قرارداد قابل ویرایش نیست.')

    if if_match_updated_at and contract.updated_at:
        client_dt = parse_datetime(if_match_updated_at.replace('Z', '+00:00'))
        if client_dt and contract.updated_at > client_dt:
            raise WizardJsonError('CONFLICT:نسخه جدیدتری از قرارداد ذخیره شده — لطفاً دوباره بارگذاری کنید.')

    payload = parse_wizard_json_step(step, data, contract.contract_type)
    try:
        save_wizard_step(contract, step, payload, user=user, request=request)
    except ContractError as exc:
        raise ValueError(str(exc)) from exc

    contract.refresh_from_db()
    wizard = dict(contract.wizard_data or {})
    validation_errors: List[str] = []
    if contract.current_version:
        validation_errors = validate_contract_ready(contract, contract.current_version)

    return {
        'contract_id': contract.pk,
        'wizard_step': contract.wizard_step,
        'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
        'wizard_data': _wizard_data_snapshot(wizard),
        'validation_errors': validation_errors,
        'validation_count': len(validation_errors),
    }
