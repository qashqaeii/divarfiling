"""آمار و فیلتر داشبورد قراردادها."""
from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from contracts.constants import (
    CONTRACT_STATUS_DRAFT,
    CONTRACT_STATUS_FINALIZED,
    CONTRACT_STATUS_PARTIALLY_ACCEPTED,
    CONTRACT_STATUS_SENT,
    CONTRACT_STATUS_VIEWED,
    CONTRACT_STATUS_FULLY_ACCEPTED,
)
from contracts.models import Contract
from contracts.services.scope import contracts_qs


ACTION_STATUSES = frozenset({
    CONTRACT_STATUS_SENT,
    CONTRACT_STATUS_VIEWED,
    CONTRACT_STATUS_PARTIALLY_ACCEPTED,
    CONTRACT_STATUS_FULLY_ACCEPTED,
})


def filter_contracts(user, params) -> QuerySet:
    qs = contracts_qs(user)
    q = (params.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(internal_number__icontains=q)
            | Q(title__icontains=q)
            | Q(deal__title__icontains=q)
            | Q(deal__customer__name__icontains=q)
        )
    status = (params.get('status') or '').strip()
    if status:
        qs = qs.filter(status=status)
    ctype = (params.get('type') or '').strip()
    if ctype:
        qs = qs.filter(contract_type=ctype)
    deal_id = params.get('deal')
    if deal_id:
        try:
            qs = qs.filter(deal_id=int(deal_id))
        except (TypeError, ValueError):
            pass
    return qs.order_by('-updated_at')


def contract_dashboard_stats(user) -> dict:
    qs = contracts_qs(user)
    agg = qs.aggregate(
        total=Count('pk'),
        draft=Count('pk', filter=Q(status=CONTRACT_STATUS_DRAFT)),
        pending=Count('pk', filter=Q(status__in=ACTION_STATUSES)),
        finalized=Count('pk', filter=Q(status=CONTRACT_STATUS_FINALIZED)),
        needs_action=Count('pk', filter=Q(status__in=ACTION_STATUSES)),
    )
    return {
        'total': agg['total'] or 0,
        'draft': agg['draft'] or 0,
        'pending': agg['pending'] or 0,
        'finalized': agg['finalized'] or 0,
        'needs_action': agg['needs_action'] or 0,
    }


def contract_acceptance_progress(contract) -> dict:
    version = contract.current_version
    if not version:
        wizard = contract.wizard_data or {}
        parties = wizard.get('parties') or []
        witnesses = wizard.get('witnesses') or []
        total = len(parties) + len(witnesses)
        return {'total': total, 'accepted': 0, 'pct': 0}
    parties = version.parties.count()
    witnesses = version.witnesses.count()
    total = parties + witnesses
    if not total:
        return {'total': 0, 'accepted': 0, 'pct': 0}
    accepted = version.acceptances.count()
    pct = min(100, int(accepted * 100 / total))
    return {'total': total, 'accepted': accepted, 'pct': pct}
