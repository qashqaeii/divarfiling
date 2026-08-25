"""محاسبه کمیسیون، تقسیم مشاور/املاک و داشبورد مالی معاملات."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import jdatetime
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from workspace.constants import (
    COMMISSION_MODE_FIXED,
    COMMISSION_MODE_LABELS,
    COMMISSION_MODE_PERCENT,
    DEAL_KIND_LABELS,
    DEAL_KIND_RENT,
    DEAL_KIND_SALE,
    DEAL_STAGE_WON,
    DEFAULT_DEAL_FINANCE,
    PAYOUT_PAID,
    PAYOUT_PARTIAL,
    PAYOUT_STATUS_LABELS,
    PAYOUT_UNPAID,
    PAYOUT_WAIVED,
)
from workspace.mixins import get_or_create_settings
from workspace.models import CRMDeal
from workspace.services.crm_scope import deals_qs
from workspace.services.jalali_input import jalali_month_bounds

JALALI_MONTHS_FA = (
    'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند',
)

FINANCE_PERIODS = (
    ('month', 'این ماه'),
    ('last_month', 'ماه گذشته'),
    ('year', 'امسال'),
    ('all', 'همه زمان‌ها'),
)

FINANCE_UPDATE_FIELDS = [
    'deal_kind', 'commission_mode',
    'buyer_commission_rate', 'seller_commission_rate',
    'buyer_commission_amount', 'seller_commission_amount',
    'advisor_share_percent', 'agency_share_percent',
    'advisor_commission', 'agency_commission',
    'commission_rate', 'commission_amount',
    'deal_costs', 'received_amount', 'payout_status', 'payout_notes',
    'updated_at',
]


def _as_float(value, default: float = 0.0) -> float:
    if value in (None, ''):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value, default: int = 0) -> int:
    if value in (None, ''):
        return default
    try:
        return int(round(float(str(value).replace(',', ''))))
    except (TypeError, ValueError):
        return default


def normalize_finance_defaults(raw: Optional[dict] = None) -> Dict[str, float]:
    src = dict(DEFAULT_DEAL_FINANCE)
    if isinstance(raw, dict):
        src.update({k: v for k, v in raw.items() if k in DEFAULT_DEAL_FINANCE})
    advisor = max(0.0, min(100.0, _as_float(src.get('advisor_share_percent'), 70.0)))
    agency = max(0.0, min(100.0, _as_float(src.get('agency_share_percent'), 30.0)))
    total = advisor + agency
    if total <= 0:
        advisor, agency = 70.0, 30.0
    elif abs(total - 100.0) > 0.01:
        advisor = round(advisor / total * 100.0, 2)
        agency = round(100.0 - advisor, 2)
    return {
        'sale_buyer_rate': max(0.0, _as_float(src.get('sale_buyer_rate'), 0.5)),
        'sale_seller_rate': max(0.0, _as_float(src.get('sale_seller_rate'), 0.5)),
        'rent_buyer_rate': max(0.0, _as_float(src.get('rent_buyer_rate'), 50.0)),
        'rent_seller_rate': max(0.0, _as_float(src.get('rent_seller_rate'), 50.0)),
        'advisor_share_percent': advisor,
        'agency_share_percent': agency,
    }


def get_finance_defaults(user) -> Dict[str, float]:
    settings = get_or_create_settings(user)
    return normalize_finance_defaults(settings.crm_finance_defaults)


def save_finance_defaults(user, payload: Optional[dict] = None) -> Dict[str, float]:
    merged = normalize_finance_defaults(payload or {})
    settings = get_or_create_settings(user)
    settings.crm_finance_defaults = merged
    settings.save(update_fields=['crm_finance_defaults'])
    return merged


def infer_deal_kind(deal: CRMDeal) -> str:
    kind = (getattr(deal, 'deal_kind', None) or '').strip()
    if kind in (DEAL_KIND_SALE, DEAL_KIND_RENT):
        return kind
    prop = getattr(deal, 'property', None)
    mode = (getattr(prop, 'deal_mode', None) or '') if prop else ''
    if 'اجاره' in mode:
        return DEAL_KIND_RENT
    return DEAL_KIND_SALE


def deal_basis_amount(deal: CRMDeal) -> int:
    return int(deal.contract_amount or deal.value or 0)


def _normalize_shares(advisor: float, agency: float) -> Tuple[float, float]:
    advisor = max(0.0, min(100.0, advisor))
    agency = max(0.0, min(100.0, agency))
    total = advisor + agency
    if total <= 0:
        return 70.0, 30.0
    if abs(total - 100.0) > 0.01:
        advisor = round(advisor / total * 100.0, 2)
        agency = round(100.0 - advisor, 2)
    return advisor, agency


def compute_deal_finance(deal: CRMDeal) -> Dict[str, Any]:
    basis = deal_basis_amount(deal)
    mode = (deal.commission_mode or COMMISSION_MODE_PERCENT).strip() or COMMISSION_MODE_PERCENT
    buyer_rate = max(0.0, _as_float(deal.buyer_commission_rate, 0.0))
    seller_rate = max(0.0, _as_float(deal.seller_commission_rate, 0.0))
    advisor_pct, agency_pct = _normalize_shares(
        _as_float(deal.advisor_share_percent, 70.0),
        _as_float(deal.agency_share_percent, 30.0),
    )
    costs = max(0, _as_int(deal.deal_costs, 0))
    received = max(0, _as_int(deal.received_amount, 0))

    if mode == COMMISSION_MODE_FIXED:
        buyer_amt = max(0, _as_int(deal.buyer_commission_amount, 0))
        seller_amt = max(0, _as_int(deal.seller_commission_amount, 0))
        total = buyer_amt + seller_amt
        rate_total = round(total / basis * 100.0, 4) if basis else 0.0
    else:
        buyer_amt = int(round(basis * buyer_rate / 100.0)) if basis else max(0, _as_int(deal.buyer_commission_amount, 0))
        seller_amt = int(round(basis * seller_rate / 100.0)) if basis else max(0, _as_int(deal.seller_commission_amount, 0))
        total = buyer_amt + seller_amt
        rate_total = round(buyer_rate + seller_rate, 4)

    advisor = int(round(total * advisor_pct / 100.0)) if total else 0
    agency = max(0, total - advisor)
    outstanding = max(0, total - received)
    net_advisor = advisor - costs
    advisor_received = int(round(received * advisor_pct / 100.0)) if received else 0
    agency_received = max(0, received - advisor_received)

    return {
        'basis': basis,
        'buyer_commission_rate': buyer_rate,
        'seller_commission_rate': seller_rate,
        'buyer_commission_amount': buyer_amt,
        'seller_commission_amount': seller_amt,
        'commission_amount': total,
        'commission_rate': rate_total,
        'advisor_share_percent': advisor_pct,
        'agency_share_percent': agency_pct,
        'advisor_commission': advisor,
        'agency_commission': agency,
        'deal_costs': costs,
        'received_amount': received,
        'outstanding': outstanding,
        'net_advisor': net_advisor,
        'advisor_received': advisor_received,
        'agency_received': agency_received,
    }


def apply_finance_defaults(deal: CRMDeal, user=None) -> CRMDeal:
    owner = user or deal.user
    defaults = get_finance_defaults(owner)
    kind = infer_deal_kind(deal)
    deal.deal_kind = kind
    if not (deal.commission_mode or '').strip():
        deal.commission_mode = COMMISSION_MODE_PERCENT
    if kind == DEAL_KIND_RENT:
        deal.buyer_commission_rate = defaults['rent_buyer_rate']
        deal.seller_commission_rate = defaults['rent_seller_rate']
    else:
        deal.buyer_commission_rate = defaults['sale_buyer_rate']
        deal.seller_commission_rate = defaults['sale_seller_rate']
    deal.advisor_share_percent = defaults['advisor_share_percent']
    deal.agency_share_percent = defaults['agency_share_percent']
    return deal


def _apply_payload(deal: CRMDeal, payload: dict) -> None:
    if 'deal_kind' in payload and payload.get('deal_kind') in (DEAL_KIND_SALE, DEAL_KIND_RENT):
        deal.deal_kind = payload['deal_kind']
    if 'commission_mode' in payload and payload.get('commission_mode') in (
        COMMISSION_MODE_PERCENT, COMMISSION_MODE_FIXED,
    ):
        deal.commission_mode = payload['commission_mode']
    if 'buyer_commission_rate' in payload:
        deal.buyer_commission_rate = max(0.0, _as_float(payload.get('buyer_commission_rate'), 0.0))
    if 'seller_commission_rate' in payload:
        deal.seller_commission_rate = max(0.0, _as_float(payload.get('seller_commission_rate'), 0.0))
    if 'buyer_commission_amount' in payload:
        deal.buyer_commission_amount = max(0, _as_int(payload.get('buyer_commission_amount'), 0))
    if 'seller_commission_amount' in payload:
        deal.seller_commission_amount = max(0, _as_int(payload.get('seller_commission_amount'), 0))
    if 'advisor_share_percent' in payload:
        deal.advisor_share_percent = max(0.0, _as_float(payload.get('advisor_share_percent'), 70.0))
    if 'agency_share_percent' in payload:
        deal.agency_share_percent = max(0.0, _as_float(payload.get('agency_share_percent'), 30.0))
    if 'deal_costs' in payload:
        deal.deal_costs = max(0, _as_int(payload.get('deal_costs'), 0))
    if 'received_amount' in payload:
        deal.received_amount = max(0, _as_int(payload.get('received_amount'), 0))
    if 'payout_status' in payload and payload.get('payout_status') in PAYOUT_STATUS_LABELS:
        deal.payout_status = payload['payout_status']
    if 'payout_notes' in payload:
        deal.payout_notes = (payload.get('payout_notes') or '')[:4000]
    if 'value' in payload and payload.get('value') not in (None, ''):
        deal.value = max(0, _as_int(payload.get('value'), 0)) or None
    if 'contract_amount' in payload and payload.get('contract_amount') not in (None, ''):
        deal.contract_amount = max(0, _as_int(payload.get('contract_amount'), 0)) or None


def _sync_payout_status(deal: CRMDeal, total: int) -> None:
    status = (deal.payout_status or PAYOUT_UNPAID).strip() or PAYOUT_UNPAID
    received = max(0, _as_int(deal.received_amount, 0))
    if status == PAYOUT_WAIVED:
        return
    if status == PAYOUT_PAID and received <= 0 and total > 0:
        deal.received_amount = total
        received = total
    if received <= 0:
        deal.payout_status = PAYOUT_UNPAID
    elif total > 0 and received >= total:
        deal.payout_status = PAYOUT_PAID
        deal.received_amount = min(received, total) if total else received
    else:
        deal.payout_status = PAYOUT_PARTIAL


def apply_deal_finance(
    deal: CRMDeal,
    payload: Optional[dict] = None,
    *,
    save: bool = True,
) -> Dict[str, Any]:
    if payload:
        _apply_payload(deal, payload)
    if not (deal.deal_kind or '').strip():
        deal.deal_kind = infer_deal_kind(deal)
    if not (deal.commission_mode or '').strip():
        deal.commission_mode = COMMISSION_MODE_PERCENT
    computed = compute_deal_finance(deal)
    deal.buyer_commission_rate = computed['buyer_commission_rate']
    deal.seller_commission_rate = computed['seller_commission_rate']
    deal.buyer_commission_amount = computed['buyer_commission_amount']
    deal.seller_commission_amount = computed['seller_commission_amount']
    deal.commission_amount = computed['commission_amount']
    deal.commission_rate = computed['commission_rate']
    deal.advisor_share_percent = computed['advisor_share_percent']
    deal.agency_share_percent = computed['agency_share_percent']
    deal.advisor_commission = computed['advisor_commission']
    deal.agency_commission = computed['agency_commission']
    deal.deal_costs = computed['deal_costs']
    deal.received_amount = computed['received_amount']
    _sync_payout_status(deal, computed['commission_amount'])
    computed = compute_deal_finance(deal)
    deal.advisor_commission = computed['advisor_commission']
    deal.agency_commission = computed['agency_commission']
    if save and deal.pk:
        deal.save(update_fields=FINANCE_UPDATE_FIELDS)
    return computed


def serialize_deal_finance(deal: CRMDeal) -> Dict[str, Any]:
    computed = compute_deal_finance(deal)
    kind = deal.deal_kind or infer_deal_kind(deal)
    mode = deal.commission_mode or COMMISSION_MODE_PERCENT
    status = deal.payout_status or PAYOUT_UNPAID
    return {
        'deal_kind': kind,
        'deal_kind_label': DEAL_KIND_LABELS.get(kind, kind),
        'commission_mode': mode,
        'commission_mode_label': COMMISSION_MODE_LABELS.get(mode, mode),
        'buyer_commission_rate': computed['buyer_commission_rate'],
        'seller_commission_rate': computed['seller_commission_rate'],
        'buyer_commission_amount': computed['buyer_commission_amount'],
        'seller_commission_amount': computed['seller_commission_amount'],
        'commission_rate': computed['commission_rate'],
        'commission_amount': computed['commission_amount'],
        'advisor_share_percent': computed['advisor_share_percent'],
        'agency_share_percent': computed['agency_share_percent'],
        'advisor_commission': computed['advisor_commission'],
        'agency_commission': computed['agency_commission'],
        'deal_costs': computed['deal_costs'],
        'received_amount': computed['received_amount'],
        'outstanding': computed['outstanding'],
        'net_advisor': computed['net_advisor'],
        'advisor_received': computed['advisor_received'],
        'agency_received': computed['agency_received'],
        'payout_status': status,
        'payout_status_label': PAYOUT_STATUS_LABELS.get(status, status),
        'payout_notes': deal.payout_notes or '',
        'basis': computed['basis'],
    }


def _period_bounds(period: str) -> Tuple[Optional[date], Optional[date], str]:
    labels = dict(FINANCE_PERIODS)
    period = (period or 'month').strip() or 'month'
    if period not in labels:
        period = 'month'
    today = timezone.localdate()
    if period == 'all':
        return None, None, labels[period]
    if period == 'year':
        jtoday = jdatetime.date.fromgregorian(date=today)
        esfand_days = 30 if jdatetime.date.isleap(jtoday.year) else 29
        start = jdatetime.date(jtoday.year, 1, 1).togregorian()
        end = jdatetime.date(jtoday.year, 12, esfand_days).togregorian()
        return start, end, f'{labels[period]} {jtoday.year}'
    if period == 'last_month':
        start, _ = jalali_month_bounds(today)
        prev = start - timedelta(days=1)
        pstart, pend = jalali_month_bounds(prev)
        jprev = jdatetime.date.fromgregorian(date=pstart)
        return pstart, pend, f'{JALALI_MONTHS_FA[jprev.month - 1]} {jprev.year}'
    start, end = jalali_month_bounds(today)
    jtoday = jdatetime.date.fromgregorian(date=today)
    return start, end, f'{JALALI_MONTHS_FA[jtoday.month - 1]} {jtoday.year}'


def _last_jalali_months(count: int = 6) -> List[dict]:
    j = jdatetime.date.today().replace(day=1)
    rows = []
    for _ in range(count):
        days = jdatetime.j_days_in_month[j.month - 1]
        if j.month == 12 and jdatetime.date.isleap(j.year):
            days = 30
        end = jdatetime.date(j.year, j.month, days)
        rows.append({
            'key': f'{j.year}-{j.month:02d}',
            'label': f'{JALALI_MONTHS_FA[j.month - 1]}',
            'year': j.year,
            'start': j.togregorian(),
            'end': end.togregorian(),
        })
        if j.month == 1:
            j = jdatetime.date(j.year - 1, 12, 1)
        else:
            j = jdatetime.date(j.year, j.month - 1, 1)
    rows.reverse()
    return rows


def _closed_qs(user, start: Optional[date] = None, end: Optional[date] = None):
    qs = deals_qs(user).filter(stage=DEAL_STAGE_WON)
    if start and end:
        qs = qs.annotate(close_day=TruncDate(Coalesce('closed_at', 'updated_at'))).filter(
            close_day__gte=start, close_day__lte=end,
        )
    return qs


def _sum(qs, field: str) -> int:
    return int(qs.aggregate(s=Sum(field))['s'] or 0)


def finance_dashboard(user, period: str = 'month') -> Dict[str, Any]:
    start, end, period_label = _period_bounds(period)
    closed = _closed_qs(user, start, end).select_related('customer', 'property')
    closed_n = closed.count()
    volume = _sum(closed, 'value')
    commission_total = _sum(closed, 'commission_amount')
    advisor_income = _sum(closed, 'advisor_commission')
    agency_income = _sum(closed, 'agency_commission')
    costs = _sum(closed, 'deal_costs')
    received = _sum(closed, 'received_amount')
    outstanding = max(0, commission_total - received)
    net_income = advisor_income - costs
    avg_deal = int(volume / closed_n) if closed_n else 0
    avg_commission = int(commission_total / closed_n) if closed_n else 0
    avg_advisor = int(advisor_income / closed_n) if closed_n else 0

    payout_rows = []
    payout_counts = dict(
        closed.values_list('payout_status').annotate(c=Count('id')).values_list('payout_status', 'c')
    )
    for key, label in PAYOUT_STATUS_LABELS.items():
        subset = closed.filter(payout_status=key)
        payout_rows.append({
            'status': key,
            'label': label,
            'count': int(payout_counts.get(key) or 0),
            'amount': _sum(subset, 'commission_amount'),
            'received': _sum(subset, 'received_amount'),
        })

    month_rows = []
    max_month = 1
    for bucket in _last_jalali_months(6):
        mqs = _closed_qs(user, bucket['start'], bucket['end'])
        row = {
            'key': bucket['key'],
            'label': bucket['label'],
            'year': bucket['year'],
            'count': mqs.count(),
            'volume': _sum(mqs, 'value'),
            'commission': _sum(mqs, 'commission_amount'),
            'advisor': _sum(mqs, 'advisor_commission'),
        }
        max_month = max(max_month, row['commission'], row['advisor'], 1)
        month_rows.append(row)
    for row in month_rows:
        row['commission_pct'] = round(row['commission'] / max_month * 100)
        row['advisor_pct'] = round(row['advisor'] / max_month * 100)

    from workspace.services.crm_deal_stages import active_stages_for_user
    from workspace.services.crm_deals import get_deal_stats
    stats = get_deal_stats(user)
    active = deals_qs(user).filter(stage__in=active_stages_for_user(user))
    weighted_volume = 0
    weighted_commission = 0
    weighted_advisor = 0
    for deal in active.only(
        'value', 'probability', 'commission_amount', 'advisor_commission',
        'buyer_commission_rate', 'seller_commission_rate', 'advisor_share_percent',
        'agency_share_percent', 'commission_mode', 'contract_amount',
        'buyer_commission_amount', 'seller_commission_amount', 'deal_costs',
        'received_amount',
    ):
        p = (deal.probability or 0) / 100.0
        if deal.value:
            weighted_volume += int(deal.value * p)
        computed = compute_deal_finance(deal)
        weighted_commission += int(computed['commission_amount'] * p)
        weighted_advisor += int(computed['advisor_commission'] * p)

    deal_rows = []
    for deal in closed.order_by('-closed_at', '-updated_at')[:40]:
        fin = serialize_deal_finance(deal)
        closed_at = deal.closed_at or deal.updated_at
        deal_rows.append({
            'id': deal.pk,
            'title': deal.title,
            'customer_name': deal.customer.name if deal.customer_id else '',
            'stage': deal.stage,
            'value': deal.value or 0,
            'closed_at': closed_at.isoformat() if closed_at else None,
            **fin,
        })

    defaults = get_finance_defaults(user)
    split_total = advisor_income + agency_income
    return {
        'period': period if period in dict(FINANCE_PERIODS) else 'month',
        'period_label': period_label,
        'periods': [{'id': k, 'label': v} for k, v in FINANCE_PERIODS],
        'kpis': {
            'closed_count': closed_n,
            'volume': volume,
            'commission_total': commission_total,
            'advisor_income': advisor_income,
            'agency_income': agency_income,
            'costs': costs,
            'net_income': net_income,
            'received': received,
            'outstanding': outstanding,
            'avg_deal': avg_deal,
            'avg_commission': avg_commission,
            'avg_advisor': avg_advisor,
        },
        'split': {
            'advisor': advisor_income,
            'agency': agency_income,
            'advisor_percent': round(advisor_income / split_total * 100) if split_total else int(defaults['advisor_share_percent']),
            'agency_percent': round(agency_income / split_total * 100) if split_total else int(defaults['agency_share_percent']),
        },
        'payout': payout_rows,
        'monthly': month_rows,
        'deals': deal_rows,
        'forecast': {
            'active_count': active.count(),
            'weighted_volume': weighted_volume,
            'weighted_commission': weighted_commission,
            'weighted_advisor': weighted_advisor,
        },
        'defaults': defaults,
        'stats': {
            'active': stats.get('active', 0),
            'closed': stats.get('closed', 0),
            'win_rate': stats.get('win_rate', 0),
            'pipeline_value': stats.get('pipeline_value', 0),
        },
        'kind_labels': DEAL_KIND_LABELS,
        'mode_labels': COMMISSION_MODE_LABELS,
        'payout_labels': PAYOUT_STATUS_LABELS,
    }
