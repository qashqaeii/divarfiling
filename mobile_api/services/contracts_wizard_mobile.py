"""API موبایل — ویزارد قرارداد (GET/PATCH)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils.dateparse import parse_datetime

from contracts.constants import CONTRACT_TYPE_LEASE, WIZARD_DISPLAY_STEPS, WIZARD_STEP_LABELS
from contracts.services.clause_ux import (
    LEASE_PENALTY_FIELDS,
    SALE_PENALTY_FIELDS,
    build_clause_context,
    build_clause_sections,
    clause_warnings,
    get_applicable_clauses,
)
from contracts.services.clauses import render_clause_body
from contracts.services.lifecycle import ContractError, save_wizard_step, validate_contract_ready
from contracts.services.prefill import ensure_default_parties
from contracts.services.wizard_json import (
    PATCHABLE_WIZARD_STEPS,
    WizardJsonError,
    display_step_keys,
    parse_wizard_json_step,
    wizard_choices_payload,
)
from mobile_api.services.contracts_mobile import (
    assert_mobile_contract_license,
    can_edit_contract_mobile,
    contract_for_mobile_user,
    workspace_paths,
)


def _resolve_step(contract, requested: Optional[str]) -> str:
    step = (requested or contract.wizard_step or 'parties').strip()
    allowed = display_step_keys(contract.contract_type)
    if step == 'review':
        return 'review'
    if step not in allowed:
        step = contract.wizard_step if contract.wizard_step in allowed else allowed[0]
    return step


def _wizard_data_snapshot(wizard: Dict[str, Any]) -> Dict[str, Any]:
    keys = PATCHABLE_WIZARD_STEPS | {
        'selected_clauses',
        'jv',
        'clause_optional',
        'custom_agreements',
    }
    out = {}
    for key in keys:
        if key in wizard:
            out[key] = wizard[key]
    return out


def _display_steps(contract_type: str) -> List[Dict[str, str]]:
    rows = WIZARD_DISPLAY_STEPS.get(contract_type) or WIZARD_DISPLAY_STEPS['lease']
    return [{'key': key, 'label': label} for key, label in rows]


def _penalty_inline_values(item: Dict[str, Any]) -> Dict[str, str]:
    amount = item.get('amount_per_day') or item.get('amount') or ''
    unit = item.get('unit', 'daily')
    return {
        'amount': str(amount),
        'penalty_amount': str(amount),
        'penalty_unit': unit,
        'unit': unit,
    }


def _enrich_clause_sections_rendered(
    contract_type: str,
    wizard: Dict[str, Any],
    sections: List[Dict[str, Any]],
    *,
    user=None,
) -> List[Dict[str, Any]]:
    from contracts.services.clause_ux import _library_clauses

    context_data = build_clause_context(wizard, contract_type)
    library = _library_clauses(contract_type, context_data, user=user)
    fin = wizard.get('financial') or {}
    penalties = fin.get('penalties') or {}
    penalty_fields = LEASE_PENALTY_FIELDS if contract_type == CONTRACT_TYPE_LEASE else SALE_PENALTY_FIELDS
    penalty_id_to_code = {row[0]: row[3] for row in penalty_fields}

    enriched_sections = []
    for section in sections:
        section = dict(section)
        cards_out = []
        for card in section.get('cards') or []:
            card = dict(card)
            code = card.get('clause_code')
            if not code and card.get('type') == 'penalty':
                code = penalty_id_to_code.get(card.get('id') or '')
            defn = library.get(code) if code else None
            template = (defn.body_template if defn else None) or card.get('clause_preview') or ''
            inline: Dict[str, str] = {}
            if card.get('type') == 'penalty':
                item = penalties.get(card.get('id') or '') or {}
                if item:
                    inline = _penalty_inline_values(item)
            if template and defn:
                card['clause_rendered'] = render_clause_body(defn, inline)
            elif template:
                card['clause_rendered'] = render_clause_body(
                    type('_Tmp', (), {'body_template': template})(),
                    inline,
                )
            cards_out.append(card)
        section['cards'] = cards_out
        enriched_sections.append(section)
    return enriched_sections


def _clause_ui(contract, wizard: Dict[str, Any]) -> Dict[str, Any]:
    context_data = build_clause_context(wizard, contract.contract_type)
    sections = build_clause_sections(
        contract.contract_type,
        wizard,
        user=contract.user,
        is_staff=False,
    )
    sections = _enrich_clause_sections_rendered(
        contract.contract_type,
        wizard,
        sections,
        user=contract.user,
    )
    return {
        'available_clauses': get_applicable_clauses(
            contract.contract_type, context_data, user=contract.user,
        ),
        'clause_sections': sections,
        'clause_step_warnings': clause_warnings(wizard, contract.contract_type),
    }


def _mobile_review_payload(contract, validation_errors: List[str]) -> Dict[str, Any]:
    from contracts.services.contract_renderer import render_contract_document
    from contracts.services.review_context import build_review_context

    review = build_review_context(contract, validation_errors=validation_errors)
    document_sections = render_contract_document(contract, contract.current_version)
    doc_out = []
    for sec in document_sections:
        if not isinstance(sec, dict):
            continue
        doc_out.append({
            'title': sec.get('title') or '',
            'body': sec.get('body') or '',
            'edit_step': sec.get('edit_step') or '',
            'nav_key': sec.get('nav_key') or '',
        })
    return {
        'readiness': review.get('readiness'),
        'readiness_message': review.get('readiness_message'),
        'readiness_detail': review.get('readiness_detail'),
        'issues': review.get('issues') or [],
        'blocking_count': review.get('blocking_count') or 0,
        'warning_count': review.get('warning_count') or 0,
        'contract_meta': review.get('contract_meta') or {},
        'financial_summary': review.get('financial_summary') or {},
        'important_dates': review.get('important_dates') or [],
        'custom_agreements': review.get('custom_agreements') or [],
        'completeness': review.get('completeness') or [],
        'nav_items': review.get('nav_items') or [],
        'send_disabled': review.get('send_disabled'),
        'send_disabled_reason': review.get('send_disabled_reason') or '',
        'document_sections': doc_out,
    }


def contract_wizard_get_payload(
    user,
    contract_id: int,
    *,
    step: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    assert_mobile_contract_license(user)
    contract = contract_for_mobile_user(user, contract_id)
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
        'can_edit': can_edit_contract_mobile(user, contract),
        'picker_enabled': contract.deal_id is None,
        'validation_errors': validation_errors,
        'validation_count': len(validation_errors),
        'choices': wizard_choices_payload(contract.contract_type),
        'workspace_paths': workspace_paths(contract),
        'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
    }
    if current in ('clauses', 'review') or wizard.get('selected_clauses') or wizard.get('clause_optional'):
        payload['clause_ui'] = _clause_ui(contract, wizard)
    if current == 'review':
        payload['review_context'] = _mobile_review_payload(contract, validation_errors)
        payload['pdf_available'] = bool(contract.current_version)
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
    contract = contract_for_mobile_user(user, contract_id)
    if not contract:
        raise ValueError('قرارداد یافت نشد.')
    if not can_edit_contract_mobile(user, contract):
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
