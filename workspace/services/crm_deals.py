"""سرویس معاملات CRM — pipeline، کمیسیون، آمار."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from django.db.models import Count, Q, Sum
from django.utils import timezone

from workspace.constants import DEAL_STAGE_LOST, DEAL_STAGE_WON, DEFAULT_COMMISSION_RATE
from workspace.models import CRMDeal, Customer
from workspace.services.crm_scope import deals_qs
from workspace.services.crm import log_activity
from workspace.services.crm_deal_checklist import ensure_deal_checklist
from workspace.services.crm_deal_stages import (
    active_stages_for_user, get_user_deal_stage_defs, get_user_deal_stages,
    is_lost_stage, is_terminal_stage, is_valid_deal_stage,
    probability_for_stage, stage_def_for, stage_meta_map,
)


def calculate_commission(value: Optional[int], rate: float) -> Optional[int]:
    if not value or rate <= 0:
        return None
    return int(value * rate / 100)


def apply_deal_commission(deal: CRMDeal, *, save: bool = True) -> CRMDeal:
    from workspace.services.crm_deal_finance import apply_deal_finance

    apply_deal_finance(deal, save=save)
    return deal


def deal_stage_age_days(deal: CRMDeal) -> int:
    ts = deal.stage_changed_at or deal.updated_at or deal.created_at
    if not ts:
        return 0
    if timezone.is_naive(ts):
        ts = timezone.make_aware(ts)
    return max(0, (timezone.now() - ts).days)


def is_deal_stale(deal: CRMDeal, stage_def: Optional[dict] = None) -> bool:
    if is_terminal_stage(deal.stage):
        return False
    meta = stage_def if stage_def is not None else stage_def_for(deal.user, deal.stage)
    rot = int((meta or {}).get('rot_days') or 0)
    if rot <= 0:
        return False
    return deal_stage_age_days(deal) >= rot


def create_deal(
    user,
    customer: Customer,
    *,
    title: str = '',
    property_obj=None,
    listing_token: str = '',
    stage: str = 'سرنخ',
    value: Optional[int] = None,
    probability: Optional[int] = None,
    expected_close_date: Optional[date] = None,
    commission_rate: float = DEFAULT_COMMISSION_RATE,
    notes: str = '',
) -> CRMDeal:
    stages = get_user_deal_stages(user)
    if stage not in stages:
        stage = stages[0]

    if not title:
        title = f'معامله — {customer.name}'
        if property_obj:
            title = f'{property_obj.title} — {customer.name}'

    if probability is None:
        probability = probability_for_stage(user, stage)

    now = timezone.now()
    deal = CRMDeal(
        user=user,
        customer=customer,
        property=property_obj,
        listing_token=listing_token or (property_obj.token if property_obj else ''),
        title=title,
        stage=stage,
        value=value,
        probability=probability,
        expected_close_date=expected_close_date,
        commission_rate=commission_rate,
        notes=notes,
        stage_changed_at=now,
    )
    if property_obj:
        if property_obj.sale_price and not value:
            deal.value = property_obj.sale_price
        elif property_obj.monthly_rent and not value:
            deal.value = property_obj.monthly_rent
    from workspace.services.crm_deal_finance import apply_deal_finance, apply_finance_defaults

    apply_finance_defaults(deal, user)
    sides = (deal.buyer_commission_rate or 0) + (deal.seller_commission_rate or 0)
    if deal.deal_kind != 'rent' and abs((commission_rate or 0) - sides) > 0.05:
        deal.buyer_commission_rate = (commission_rate or 0) / 2.0
        deal.seller_commission_rate = (commission_rate or 0) / 2.0
    apply_deal_finance(deal, save=False)
    deal.save()
    ensure_deal_checklist(deal)
    log_activity(
        customer,
        'املاک',
        content=f'معامله جدید: {deal.title} — مرحله {deal.stage}',
        title='ثبت معامله',
        property_obj=property_obj,
        metadata={'deal_id': deal.pk, 'stage': deal.stage},
    )
    return deal


def update_deal_stage(deal: CRMDeal, new_stage: str, *, lost_reason: str = '') -> CRMDeal:
    if not is_valid_deal_stage(deal.user, new_stage):
        raise ValueError('مرحله نامعتبر')

    old_stage = deal.stage
    deal.stage = new_stage
    update_fields = ['stage', 'updated_at']
    if old_stage != new_stage:
        deal.stage_changed_at = timezone.now()
        update_fields.append('stage_changed_at')
        deal.probability = probability_for_stage(deal.user, new_stage)
        update_fields.append('probability')
    if is_lost_stage(new_stage) and lost_reason:
        deal.lost_reason = lost_reason
        update_fields.append('lost_reason')
    if is_terminal_stage(new_stage) and not deal.closed_at:
        deal.closed_at = timezone.now()
        update_fields.append('closed_at')
    elif not is_terminal_stage(new_stage) and deal.closed_at:
        deal.closed_at = None
        update_fields.append('closed_at')
    deal.save(update_fields=update_fields)
    if old_stage != new_stage:
        log_activity(
            deal.customer,
            'تغییر وضعیت',
            content=f'معامله «{deal.title}»: {old_stage} → {new_stage}',
            property_obj=deal.property,
            metadata={'deal_id': deal.pk, 'old_stage': old_stage, 'new_stage': new_stage},
        )
    return deal


def get_deal_pipeline(user, per_column: int = 20) -> List[Dict[str, Any]]:
    rows = []
    for stage_def in get_user_deal_stage_defs(user):
        stage = stage_def['name']
        qs = deals_qs(user).filter(stage=stage).select_related('customer', 'property')
        deals = list(qs.order_by('-updated_at')[:per_column])
        stale_n = sum(1 for d in deals if is_deal_stale(d, stage_def))
        rows.append({
            'stage': stage,
            'definition': stage_def,
            'count': qs.count(),
            'stale_count': stale_n,
            'total_value': qs.aggregate(s=Sum('value'))['s'] or 0,
            'deals': deals,
            'color': stage_def.get('color') or '#94a3b8',
            'bg': stage_def.get('bg'),
            'icon': stage_def.get('icon'),
            'probability': stage_def.get('probability'),
        })
    return rows


def get_deal_stats(user) -> Dict[str, Any]:
    qs = deals_qs(user)
    active_names = active_stages_for_user(user)
    active = qs.filter(stage__in=active_names)
    weighted = 0
    for d in active.only('value', 'probability'):
        if d.value:
            weighted += int(d.value * (d.probability or 0) / 100)

    closed = qs.filter(stage=DEAL_STAGE_WON)
    lost = qs.filter(stage=DEAL_STAGE_LOST)
    commission_total = closed.aggregate(s=Sum('commission_amount'))['s'] or 0
    advisor_income = closed.aggregate(s=Sum('advisor_commission'))['s'] or 0
    agency_income = closed.aggregate(s=Sum('agency_commission'))['s'] or 0
    commission_received = closed.aggregate(s=Sum('received_amount'))['s'] or 0
    closed_n = closed.count()
    lost_n = lost.count()
    win_rate = round(closed_n / max(closed_n + lost_n, 1) * 100)

    stale_n = 0
    meta_map = stage_meta_map(user)
    for deal in active.only('stage', 'stage_changed_at', 'updated_at', 'created_at', 'user_id'):
        if is_deal_stale(deal, meta_map.get(deal.stage)):
            stale_n += 1

    return {
        'total': qs.count(),
        'active': active.count(),
        'closed': closed_n,
        'lost': lost_n,
        'stale': stale_n,
        'pipeline_value': active.aggregate(s=Sum('value'))['s'] or 0,
        'weighted_forecast': weighted,
        'commission_total': commission_total,
        'advisor_income': advisor_income,
        'agency_income': agency_income,
        'commission_received': commission_received,
        'win_rate': win_rate,
        'by_stage': dict(qs.values('stage').annotate(c=Count('id')).values_list('stage', 'c')),
    }


def filter_deals(user, params: dict):
    qs = deals_qs(user).select_related('customer', 'property')
    q = params.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(customer__name__icontains=q)
            | Q(listing_token__icontains=q) | Q(property__title__icontains=q),
        )
    stage = params.get('stage', '').strip()
    if stage:
        qs = qs.filter(stage=stage)
    bucket = params.get('bucket', '').strip()
    if bucket == 'active':
        qs = qs.filter(stage__in=active_stages_for_user(user))
    elif bucket == 'closed':
        qs = qs.filter(stage=DEAL_STAGE_WON)
    elif bucket == 'lost':
        qs = qs.filter(stage=DEAL_STAGE_LOST)
    elif bucket == 'stale':
        stale_ids = []
        meta_map = stage_meta_map(user)
        active_qs = qs.filter(stage__in=active_stages_for_user(user))
        for deal in active_qs.only('id', 'stage', 'stage_changed_at', 'updated_at', 'created_at', 'user_id'):
            if is_deal_stale(deal, meta_map.get(deal.stage)):
                stale_ids.append(deal.pk)
        qs = qs.filter(pk__in=stale_ids)
    customer_id = params.get('customer_id', '').strip()
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    sort = params.get('sort', '-updated_at')
    allowed = {
        'title', '-title', 'updated_at', '-updated_at', 'value', '-value',
        'expected_close_date', '-expected_close_date', 'probability', '-probability',
    }
    qs = qs.order_by(sort if sort in allowed else '-updated_at')
    return qs
