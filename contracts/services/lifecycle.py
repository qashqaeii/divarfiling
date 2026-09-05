"""چرخه عمر قرارداد: ایجاد، نسخه‌گذاری، انتشار، نهایی‌سازی."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from contracts.constants import (
    CONTRACT_STATUS_CANCELLED,
    CONTRACT_STATUS_DRAFT,
    CONTRACT_STATUS_FINALIZED,
    CONTRACT_STATUS_FULLY_ACCEPTED,
    CONTRACT_STATUS_PARTIALLY_ACCEPTED,
    CONTRACT_STATUS_READY,
    CONTRACT_STATUS_SENT,
    CONTRACT_STATUS_VIEWED,
    CONTRACT_TYPE_JV,
    CONTRACT_TYPE_LEASE,
    CONTRACT_TYPE_SALE,
)
from contracts.models import (
    Contract,
    ContractClause,
    ContractParty,
    ContractPayment,
    ContractPaymentSchedule,
    ContractPropertySnapshot,
    ContractVersion,
    ContractWitness,
)
from contracts.services.audit import log_audit_event
from contracts.services.clauses import get_applicable_clauses, render_clause_body
from contracts.services.deal_sync import sync_deal_legacy_fields
from contracts.services.hashing import build_version_snapshot, compute_content_hash
from contracts.services.immutability import VersionImmutableError, assert_version_mutable
from contracts.services.numbering import generate_internal_number
from contracts.services.party_sanitize import sanitize_party_payload, sanitize_witness_payload
from contracts.services.prefill import (
    prefill_financial_from_deal,
    prefill_parties_from_deal,
    prefill_property_from_deal,
)
from contracts.services.scope import can_edit_contract
from contracts.services.state_machine import InvalidStateTransition, transition_contract
from contracts.services.tokens import generate_bearer_token
from contracts.services.version_copy import copy_version_entities
from workspace.services.crm_scope import deal_for_user, get_agency


class ContractError(Exception):
    pass


@transaction.atomic
def create_contract(
    user,
    deal_id: int,
    contract_type: str,
    *,
    request=None,
) -> Contract:
    deal = deal_for_user(user, deal_id)
    if not deal:
        raise ContractError('معامله یافت نشد.')
    agency = get_agency(user)
    internal_number = generate_internal_number(contract_type)
    _, verify_hash = generate_bearer_token()
    contract = Contract.objects.create(
        user=user,
        agency=agency,
        deal=deal,
        contract_type=contract_type,
        internal_number=internal_number,
        title='',
        verification_token_hash=verify_hash,
        wizard_step='parties',
        wizard_data={
            'parties': prefill_parties_from_deal(deal, contract_type),
            'property': prefill_property_from_deal(deal),
            'financial': prefill_financial_from_deal(deal, contract_type),
            'jv': {} if contract_type == CONTRACT_TYPE_JV else None,
            'witnesses': [],
            'selected_clauses': [],
            'clause_optional': [],
            'custom_agreements': [],
        },
    )
    version = _create_version(contract, user, version_number=1)
    contract.current_version = version
    contract.save(update_fields=['current_version', 'updated_at'])
    contract.title = f'قرارداد {contract.get_contract_type_display()}'
    contract.save(update_fields=['title', 'updated_at'])
    _sync_version_from_wizard(contract, version)
    log_audit_event(contract, 'CONTRACT_CREATED', version=version, actor_user=user, request=request)
    log_audit_event(contract, 'VERSION_CREATED', version=version, actor_user=user, request=request)
    return contract


def _create_version(contract: Contract, user, version_number: int) -> ContractVersion:
    return ContractVersion.objects.create(
        contract=contract,
        version_number=version_number,
        created_by=user,
    )


@transaction.atomic
def save_wizard_step(
    contract: Contract,
    step: str,
    data: Any,
    *,
    user=None,
    request=None,
) -> Contract:
    if user and not can_edit_contract(user, contract):
        raise ContractError('این قرارداد قابل ویرایش نیست.')
    version = contract.current_version
    if version:
        assert_version_mutable(version)

    wizard = dict(contract.wizard_data or {})
    if step == 'jv' or (step == 'financial' and contract.contract_type == CONTRACT_TYPE_JV):
        wizard['jv'] = data
    elif step == 'clauses':
        from contracts.services.clause_ux import apply_clauses_step
        wizard = apply_clauses_step(
            wizard, data, contract.contract_type, user=user,
        )
    else:
        wizard[step] = data

    contract.wizard_data = wizard
    contract.wizard_step = step
    contract.save(update_fields=['wizard_data', 'wizard_step', 'updated_at'])
    if version:
        _sync_version_from_wizard(contract, version)
        if step == 'financial' and contract.contract_type == CONTRACT_TYPE_SALE:
            _sync_payments_from_financial(version, wizard.get('financial') or {})
        if step == 'jv' or (contract.contract_type == CONTRACT_TYPE_JV and step == 'financial'):
            version.jv_data = wizard.get('jv') or {}
            version.save(update_fields=['jv_data'])
    log_audit_event(
        contract, 'CONTRACT_UPDATED', version=version,
        actor_user=user, metadata={'step': step}, request=request,
    )
    return contract


def _sync_payments_from_financial(version: ContractVersion, fin: dict) -> None:
    assert_version_mutable(version)
    version.payment_schedules.all().delete()
    payments = fin.get('payments') or []
    if not payments:
        return
    sched = ContractPaymentSchedule.objects.create(
        version=version, title='برنامه پرداخت', total_amount=fin.get('total_price'),
    )
    for idx, p in enumerate(payments):
        amt = p.get('amount')
        ContractPayment.objects.create(
            schedule=sched,
            label=p.get('label', f'قسط {idx + 1}'),
            amount=int(amt) if amt not in (None, '') else 0,
            due_date=None,
            payment_method=p.get('payment_method', ''),
            sort_order=idx,
        )


def _apply_lease_duration(fin: dict) -> None:
    """محاسبه duration_days از تاریخ شروع/پایان."""
    if not fin:
        return
    start, end = fin.get('lease_start'), fin.get('lease_end')
    if not start or not end:
        return
    try:
        from workspace.services.jalali_input import parse_jalali_date_string
        d1, d2 = parse_jalali_date_string(start), parse_jalali_date_string(end)
        if d1 and d2:
            fin['duration_days'] = (d2 - d1).days
    except Exception:
        pass


def _sync_version_from_wizard(contract: Contract, version: ContractVersion) -> None:
    assert_version_mutable(version)
    wizard = contract.wizard_data or {}
    version.parties.all().delete()
    for idx, p in enumerate(wizard.get('parties') or []):
        p = sanitize_party_payload(p)
        ContractParty.objects.create(
            contract=contract,
            version=version,
            customer_id=p.get('customer_id'),
            role=p.get('role', ''),
            person_type=p.get('person_type', 'natural'),
            first_name=p.get('first_name', ''),
            last_name=p.get('last_name', ''),
            father_name=p.get('father_name', ''),
            national_id=p.get('national_id', ''),
            mobile=p.get('mobile', ''),
            address=p.get('address', ''),
            postal_code=p.get('postal_code', ''),
            position_title=p.get('position_title', ''),
            company_name=p.get('company_name', ''),
            company_national_id=p.get('company_national_id', ''),
            company_registration_no=p.get('company_registration_no', ''),
            representative_name=p.get('representative_name', ''),
            representative_national_id=p.get('representative_national_id', ''),
            representative_mobile=p.get('representative_mobile', ''),
            sort_order=idx,
            ownership_share=p.get('ownership_share', ''),
        )
    prop_data = wizard.get('property') or {}
    ContractPropertySnapshot.objects.update_or_create(
        version=version,
        defaults={'data': copy.deepcopy(prop_data), 'declared_by_parties': True},
    )
    version.financial_data = copy.deepcopy(wizard.get('financial') or {})
    _apply_lease_duration(version.financial_data)
    version.jv_data = copy.deepcopy(wizard.get('jv') or {})
    version.save(update_fields=['financial_data', 'jv_data'])

    version.witnesses.all().delete()
    for w in wizard.get('witnesses') or []:
        w = sanitize_witness_payload(w)
        ContractWitness.objects.create(
            contract=contract,
            version=version,
            witness_number=w.get('witness_number', 1),
            witness_role=w.get('witness_role', ''),
            first_name=w.get('first_name', ''),
            last_name=w.get('last_name', ''),
            national_id=w.get('national_id', ''),
            mobile=w.get('mobile', ''),
        )


@transaction.atomic
def sync_clauses_from_selection(contract: Contract, version: ContractVersion) -> None:
    assert_version_mutable(version)
    wizard = contract.wizard_data or {}
    selected = wizard.get('selected_clauses') or []
    version.clauses.all().delete()
    sort = 0
    for item in selected:
        if item.get('is_custom'):
            ContractClause.objects.create(
                version=version,
                title=item.get('title', 'شرط اختصاصی'),
                body_text=item.get('body_text', ''),
                is_custom=True,
                sort_order=sort,
            )
            sort += 1
            continue
        code = item.get('code')
        if code:
            from contracts.models import ContractClauseDefinition
            defn = ContractClauseDefinition.objects.filter(
                code=code, is_active=True,
            ).order_by('-version').first()
            if defn:
                wizard = contract.wizard_data or {}
                fin = wizard.get('financial') or {}
                if contract.contract_type == CONTRACT_TYPE_LEASE:
                    from contracts.services.lease_clause_bank import render_lease_clause_body
                    body = render_lease_clause_body(
                        defn.code, defn.body_template,
                        fin=fin, inline_values=item.get('inline_values'),
                    )
                elif contract.contract_type == CONTRACT_TYPE_SALE:
                    from contracts.services.sale_clause_bank import render_sale_clause_body
                    prop = wizard.get('property') or {}
                    body = render_sale_clause_body(
                        defn.code, defn.body_template,
                        fin=fin, prop=prop, inline_values=item.get('inline_values'),
                    )
                else:
                    body = render_clause_body(defn, item.get('inline_values'))
                ContractClause.objects.create(
                    version=version,
                    definition=defn,
                    code=defn.code,
                    title=defn.title,
                    category=defn.category,
                    body_text=body,
                    plain_explanation=defn.plain_explanation,
                    inline_values=item.get('inline_values') or {},
                    definition_version=defn.version,
                    sort_order=sort,
                )
                sort += 1


@transaction.atomic
def prepare_for_send(contract: Contract, *, user=None, request=None) -> ContractVersion:
    if not can_edit_contract(user, contract):
        raise ContractError('قرارداد قابل ارسال نیست.')
    version = contract.current_version
    if not version:
        raise ContractError('نسخه‌ای وجود ندارد.')
    errors = validate_contract_ready(contract, version)
    if errors:
        raise ContractError('؛ '.join(errors))
    sync_clauses_from_selection(contract, version)
    if contract.contract_type == CONTRACT_TYPE_SALE:
        _sync_payments_from_financial(version, version.financial_data or {})
    snapshot = build_version_snapshot(version)
    version.snapshot_json = snapshot
    version.content_hash = compute_content_hash(version)
    version.is_published = True
    version.is_locked = True
    version.published_at = timezone.now()
    version.disclaimer_acknowledged_at = timezone.now()
    version.creator_acknowledged_at = timezone.now()
    version.save()
    try:
        transition_contract(contract, CONTRACT_STATUS_READY)
    except InvalidStateTransition as exc:
        raise ContractError(str(exc)) from exc
    log_audit_event(contract, 'VERSION_PUBLISHED', version=version, actor_user=user, request=request)
    return version


def validate_contract_ready(contract: Contract, version: ContractVersion) -> List[str]:
    errors = []
    if not version.parties.exists():
        errors.append('حداقل یک طرف قرارداد لازم است.')
    if contract.contract_type == CONTRACT_TYPE_LEASE:
        fin = version.financial_data or {}
        if not fin.get('monthly_rent'):
            errors.append('مبلغ اجاره ماهانه الزامی است.')
        if fin.get('deposit') is None or fin.get('deposit') == '':
            errors.append('مبلغ قرض‌الحسنه/ودیعه الزامی است.')
        if not fin.get('lease_start') or not fin.get('lease_end'):
            errors.append('مدت اجاره (تاریخ شروع و پایان) الزامی است.')
        if fin.get('deposit_mode') == 'retained':
            prev_ref = (
                fin.get('previous_contract_ref')
                or fin.get('previous_contract_reference')
                or ''
            ).strip()
            if not prev_ref:
                errors.append(
                    'برای باقی‌ماندن ودیعه قرارداد قبلی، مشخصات قرارداد قبلی را وارد کنید.',
                )
            try:
                prev_amt = int(fin.get('previous_deposit_amount') or fin.get('deposit') or 0)
            except (TypeError, ValueError):
                prev_amt = 0
            if prev_amt <= 0:
                errors.append(
                    'برای باقی‌ماندن ودیعه قرارداد قبلی، مبلغ ودیعه قبلی را وارد کنید.',
                )
        if version.witnesses.count() < 2:
            errors.append('دو شاهد برای قرارداد اجاره الزامی است.')
    if contract.contract_type == CONTRACT_TYPE_SALE:
        fin = version.financial_data or {}
        total = fin.get('total_price')
        payments = fin.get('payments') or []
        if payments and total:
            try:
                pay_sum = sum(int(p.get('amount') or 0) for p in payments)
                if pay_sum != int(total):
                    errors.append(
                        f'مجموع پرداخت‌ها ({pay_sum}) با مبلغ کل ({total}) برابر نیست.',
                    )
            except (TypeError, ValueError):
                errors.append('مبالغ پرداخت نامعتبر است.')
    if contract.contract_type == CONTRACT_TYPE_JV:
        jv = version.jv_data or {}
        try:
            owner_pct = int(jv.get('owner_percent') or 0)
            builder_pct = int(jv.get('builder_percent') or 0)
            if owner_pct + builder_pct != 100:
                errors.append('مجموع درصد مشارکت باید ۱۰۰٪ باشد.')
        except (TypeError, ValueError):
            errors.append('درصد مشارکت نامعتبر است.')
    wizard_clauses = (contract.wizard_data or {}).get('selected_clauses') or []
    if not version.clauses.filter(is_active=True).exists() and not wizard_clauses:
        errors.append('حداقل یک بند قرارداد لازم است.')
    return errors


@transaction.atomic
def create_new_version(contract: Contract, *, user=None, request=None) -> ContractVersion:
    old_version = contract.current_version
    if not old_version:
        raise ContractError('نسخه‌ای وجود ندارد.')
    if not old_version.is_published and not old_version.has_acceptances:
        raise ContractError('فقط پس از انتشار یا تأیید می‌توان نسخه جدید ساخت.')

    new_num = old_version.version_number + 1
    new_version = _create_version(contract, user, version_number=new_num)
    copy_version_entities(old_version, new_version, contract)

    wizard_from_snapshot = {
        'parties': old_version.snapshot_json.get('parties') if old_version.snapshot_json else [],
        'property': old_version.snapshot_json.get('property') if old_version.snapshot_json else {},
        'financial': copy.deepcopy(old_version.financial_data or {}),
        'jv': copy.deepcopy(old_version.jv_data or {}),
        'witnesses': old_version.snapshot_json.get('witnesses') if old_version.snapshot_json else [],
        'selected_clauses': [],
    }
    contract.current_version = new_version
    contract.wizard_data = wizard_from_snapshot
    contract.save(update_fields=['current_version', 'wizard_data', 'updated_at'])
    try:
        transition_contract(contract, CONTRACT_STATUS_DRAFT)
    except InvalidStateTransition:
        contract.status = CONTRACT_STATUS_DRAFT
        contract.save(update_fields=['status', 'updated_at'])

    log_audit_event(contract, 'VERSION_CREATED', version=new_version, actor_user=user, request=request)
    return new_version


@transaction.atomic
def cancel_contract(contract: Contract, reason: str = '', *, user=None, request=None) -> Contract:
    if contract.status == CONTRACT_STATUS_FINALIZED:
        raise ContractError('قرارداد نهایی‌شده قابل لغو مستقیم نیست.')
    try:
        transition_contract(contract, CONTRACT_STATUS_CANCELLED)
    except InvalidStateTransition as exc:
        raise ContractError(str(exc)) from exc
    contract.cancel_reason = reason
    contract.cancelled_at = timezone.now()
    contract.save(update_fields=['cancel_reason', 'cancelled_at', 'updated_at'])
    log_audit_event(contract, 'CONTRACT_CANCELLED', actor_user=user,
                    metadata={'reason': reason}, request=request)
    return contract


@transaction.atomic
def copy_contract(contract: Contract, *, user=None, request=None) -> Contract:
    new_contract = create_contract(user, contract.deal_id, contract.contract_type, request=request)
    src = contract.wizard_data or {}
    new_contract.wizard_data = {
        k: copy.deepcopy(v) for k, v in src.items()
        if k not in ('acceptances', 'signatures', 'audit') and v is not None
    }
    new_contract.save(update_fields=['wizard_data', 'updated_at'])
    if contract.current_version:
        _sync_version_from_wizard(new_contract, new_contract.current_version)
        sync_clauses_from_selection(new_contract, new_contract.current_version)
    new_contract.copied_from = contract
    new_contract.save(update_fields=['copied_from', 'updated_at'])
    return new_contract


def update_acceptance_status(contract: Contract) -> None:
    version = contract.current_version
    if not version or not version.is_published:
        return
    required = version.parties.count() + version.witnesses.count()
    accepted = version.acceptances.count()
    if accepted == 0:
        return
    if accepted < required:
        if contract.status in (CONTRACT_STATUS_SENT, CONTRACT_STATUS_VIEWED):
            try:
                transition_contract(contract, CONTRACT_STATUS_PARTIALLY_ACCEPTED)
            except InvalidStateTransition:
                pass
    elif accepted >= required:
        try:
            transition_contract(contract, CONTRACT_STATUS_FULLY_ACCEPTED)
        except InvalidStateTransition:
            pass
        else:
            log_audit_event(contract, 'CONTRACT_FULLY_ACCEPTED', version=version)


@transaction.atomic
def finalize_contract(contract: Contract, *, request=None) -> Contract:
    contract = Contract.objects.select_for_update().get(pk=contract.pk)
    if contract.status == CONTRACT_STATUS_FINALIZED:
        return contract

    version = contract.current_version
    if not version:
        raise ContractError('نسخه‌ای وجود ندارد.')

    required = version.parties.count() + version.witnesses.count()
    if version.acceptances.count() < required:
        raise ContractError('همه طرفین و شاهدان تأیید نکرده‌اند.')

    for acc in version.acceptances.all():
        if not acc.is_hash_valid():
            raise ContractError('هش تأیید یکی از طرفین با نسخه مطابقت ندارد.')

    version.content_hash = compute_content_hash(version)
    version.snapshot_json = build_version_snapshot(version)
    version.is_locked = True
    version.save(update_fields=['content_hash', 'snapshot_json', 'is_locked'])

    transition_contract(contract, CONTRACT_STATUS_FINALIZED)
    contract.finalized_at = timezone.now()
    from contracts.services.tokens import generate_bearer_token
    verify_raw, verify_hash = generate_bearer_token()
    contract.verification_token_hash = verify_hash
    contract.save(update_fields=['finalized_at', 'verification_token_hash', 'updated_at'])

    log_audit_event(contract, 'CONTRACT_FINALIZED', version=version, request=request)
    from contracts.services.reminders import sync_contract_reminders
    from contracts.services.pdf import generate_contract_pdf
    generate_contract_pdf(version, verify_raw_token=verify_raw, request=request)
    sync_contract_reminders(contract)
    sync_deal_legacy_fields(contract)
    return contract
