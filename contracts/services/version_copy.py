"""کپی عمیق داده نسخه — تضمین snapshot integrity."""
from __future__ import annotations

import copy

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


def copy_version_entities(
    source: ContractVersion,
    target: ContractVersion,
    contract: Contract,
) -> None:
    """کپی تمام entityهای نسخه به نسخه جدید — بدون acceptance/invitation."""
    target.financial_data = copy.deepcopy(source.financial_data or {})
    target.jv_data = copy.deepcopy(source.jv_data or {})
    target.save(update_fields=['financial_data', 'jv_data'])

    for p in source.parties.all():
        ContractParty.objects.create(
            contract=contract,
            version=target,
            customer_id=p.customer_id,
            role=p.role,
            person_type=p.person_type,
            first_name=p.first_name,
            last_name=p.last_name,
            father_name=p.father_name,
            national_id=p.national_id,
            birth_date=p.birth_date,
            mobile=p.mobile,
            address=p.address,
            postal_code=p.postal_code,
            position_title=p.position_title,
            company_name=p.company_name,
            company_national_id=p.company_national_id,
            company_registration_no=p.company_registration_no,
            representative_name=p.representative_name,
            representative_national_id=p.representative_national_id,
            representative_mobile=p.representative_mobile,
            sort_order=p.sort_order,
            ownership_share=p.ownership_share,
        )

    for w in source.witnesses.all():
        ContractWitness.objects.create(
            contract=contract,
            version=target,
            witness_number=w.witness_number,
            witness_role=w.witness_role,
            first_name=w.first_name,
            last_name=w.last_name,
            national_id=w.national_id,
            mobile=w.mobile,
        )

    src_prop = getattr(source, 'property_snapshot', None)
    if src_prop:
        ContractPropertySnapshot.objects.create(
            version=target,
            data=copy.deepcopy(src_prop.data),
            declared_by_parties=src_prop.declared_by_parties,
        )

    for c in source.clauses.all():
        ContractClause.objects.create(
            version=target,
            definition_id=c.definition_id,
            code=c.code,
            title=c.title,
            category=c.category,
            body_text=c.body_text,
            plain_explanation=c.plain_explanation,
            is_custom=c.is_custom,
            is_active=c.is_active,
            inline_values=copy.deepcopy(c.inline_values or {}),
            sort_order=c.sort_order,
            definition_version=c.definition_version,
        )

    for sched in source.payment_schedules.all():
        new_sched = ContractPaymentSchedule.objects.create(
            version=target,
            title=sched.title,
            total_amount=sched.total_amount,
            notes=sched.notes,
        )
        for pay in sched.payments.all():
            ContractPayment.objects.create(
                schedule=new_sched,
                label=pay.label,
                amount=pay.amount,
                due_date=pay.due_date,
                payment_method=pay.payment_method,
                notes=pay.notes,
                sort_order=pay.sort_order,
            )


def version_display_snapshot(version: ContractVersion) -> dict:
    """داده نمایش — از snapshot_json برای نسخه published استفاده کن."""
    if version.is_published and version.snapshot_json:
        return version.snapshot_json
    from contracts.services.hashing import build_version_snapshot
    return build_version_snapshot(version)
