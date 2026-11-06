"""آمار و فیلتر داشبورد قراردادها."""
from __future__ import annotations

from typing import Any, Dict, List

from django.db.models import Count, Q, QuerySet

from contracts.constants import (
    CONTRACT_STATUS_DRAFT,
    CONTRACT_STATUS_FINALIZED,
    CONTRACT_STATUS_PARTIALLY_ACCEPTED,
    CONTRACT_STATUS_READY,
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

ACTIVE_STATUSES = frozenset({
    CONTRACT_STATUS_DRAFT,
    CONTRACT_STATUS_READY,
}) | ACTION_STATUSES


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
    focus = (params.get('focus') or '').strip()
    if status:
        qs = qs.filter(status=status)
    elif focus == 'needs':
        qs = qs.filter(status__in=ACTION_STATUSES)
    elif focus == 'active':
        qs = qs.filter(status__in=ACTIVE_STATUSES)
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


def build_contracts_kpi_stats(user) -> Dict[str, Any]:
    """
    KPI تصمیم‌ساز داشبورد قراردادها برای مشاور (fl-kpi-pro).

    کارت‌ها: کل · نیازمند اقدام · پیش‌نویس · نهایی‌شده
    """
    stats = contract_dashboard_stats(user)
    total = int(stats['total'] or 0)
    draft = int(stats['draft'] or 0)
    pending = int(stats['pending'] or 0)
    finalized = int(stats['finalized'] or 0)
    needs_action = int(stats['needs_action'] or 0)
    other = max(total - draft - pending - finalized, 0)

    def _share(part: int) -> int:
        if not total:
            return 0
        return int(round((part / total) * 100))

    mix_segments: List[Dict[str, Any]] = []
    for key, label, count in (
        ('draft', 'پیش‌نویس', draft),
        ('pending', 'در انتظار تأیید', pending),
        ('finalized', 'نهایی‌شده', finalized),
        ('other', 'سایر', other),
    ):
        if count <= 0:
            continue
        mix_segments.append({
            'key': key,
            'label': label,
            'count': count,
            'pct': _share(count),
        })

    hero_bits = []
    if draft:
        hero_bits.append(f'{draft} پیش‌نویس')
    if pending:
        hero_bits.append(f'{pending} در انتظار')
    if finalized:
        hero_bits.append(f'{finalized} نهایی')
    hero_meta = ' · '.join(hero_bits) if hero_bits else (
        'قراردادی ثبت نشده' if total == 0 else 'وضعیت‌ها آماده است'
    )

    if needs_action:
        needs_action_meta = f'{_share(needs_action)}٪ از کل در مسیر تأیید'
    elif total:
        needs_action_meta = 'الان اقدام معلقی نیست'
    else:
        needs_action_meta = 'هنوز قراردادی نیست'

    if draft:
        draft_meta = f'{_share(draft)}٪ از قراردادها'
    elif total:
        draft_meta = 'پیش‌نویسی ندارید'
    else:
        draft_meta = 'هنوز قراردادی نیست'

    if finalized:
        finalized_meta = f'{_share(finalized)}٪ نهایی شده‌اند'
    elif total:
        finalized_meta = 'هنوز نهایی‌شده‌ای نیست'
    else:
        finalized_meta = 'هنوز قراردادی نیست'

    stats.update({
        'mix_segments': mix_segments,
        'hero_meta': hero_meta,
        'needs_action_share': _share(needs_action),
        'needs_action_meta': needs_action_meta,
        'draft_share': _share(draft),
        'draft_meta': draft_meta,
        'finalized_share': _share(finalized),
        'finalized_meta': finalized_meta,
        'pending_share': _share(pending),
    })
    return stats


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
