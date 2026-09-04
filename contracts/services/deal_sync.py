"""همگام‌سازی یک‌طرفه فیلدهای legacy CRMDeal از قرارداد نهایی."""
from __future__ import annotations

from django.utils import timezone

from contracts.models import Contract


def sync_deal_legacy_fields(contract: Contract) -> None:
    """
    Source of truth: Contract (finalized).
    CRMDeal.contract_* فقط denormalized summary است — هرگز به قرارداد sync نمی‌شود.
    """
    if contract.status != 'finalized':
        return
    deal = contract.deal
    version = contract.current_version
    if not deal or not version:
        return
    fin = version.financial_data or {}
    amount = fin.get('total_price') or fin.get('monthly_rent') or fin.get('deposit')
    deal.contract_number = contract.internal_number
    if amount is not None:
        deal.contract_amount = int(amount)
    deal.contract_date = timezone.localdate()
    deal.save(update_fields=['contract_number', 'contract_amount', 'contract_date', 'updated_at'])
