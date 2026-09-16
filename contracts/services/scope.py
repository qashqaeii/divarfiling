"""محدوده دسترسی قرارداد — هم‌راستا با CRM scope."""
from __future__ import annotations

from django.db.models import Prefetch, Q, QuerySet

from contracts.models import Contract, ContractParty, ContractVersion, ContractWitness
from workspace.services.crm_scope import deals_qs, get_membership


def contracts_qs(user) -> QuerySet:
    """قراردادهای قابل مشاهده کاربر — هم‌راستا با deals_qs و مالکیت ایجادکننده.

    داشبورد «قراردادها» فقط برای کاربر جاری است:
    - قراردادهای معاملاتی که معامله‌شان در deals_qs کاربر باشد (خود + اشتراک)
    - قراردادهای مستقل (بدون معامله) که خود کاربر ایجاد کرده باشد

    مشاهدهٔ قراردادهای دیگر اعضای آژانس از مسیر Agency Hub / get_member_contracts_qs است.
    """
    if not user or not user.is_authenticated:
        return Contract.objects.none()
    deal_ids = deals_qs(user).values_list('pk', flat=True)
    scope = Q(deal_id__in=deal_ids)
    if get_membership(user):
        scope |= Q(user=user, deal__isnull=True)
    else:
        scope |= Q(user=user, agency__isnull=True)
    version_qs = ContractVersion.objects.select_related('property_snapshot').prefetch_related(
        Prefetch('parties', queryset=ContractParty.objects.order_by('sort_order', 'pk')),
        Prefetch('witnesses', queryset=ContractWitness.objects.order_by('witness_number')),
        'clauses',
    )
    return (
        Contract.objects.filter(scope)
        .distinct()
        .select_related('deal', 'deal__customer', 'deal__property', 'current_version', 'agency', 'user')
        .prefetch_related(
            Prefetch('versions', queryset=version_qs),
            'handovers',
        )
    )


def contract_for_user(user, contract_id: int) -> Contract | None:
    return contracts_qs(user).filter(pk=contract_id).first()


def can_edit_contract(user, contract: Contract) -> bool:
    if not contract_for_user(user, contract.pk):
        return False
    return contract.is_editable


def contract_for_deal(user, deal_id: int) -> QuerySet:
    return contracts_qs(user).filter(deal_id=deal_id).order_by('-updated_at')
