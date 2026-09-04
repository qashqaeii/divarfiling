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
    next_action_type: str = '',
    next_action_at=None,
    next_action_note: str = '',
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

    from workspace.services.crm_scope import get_agency

    agency = get_agency(user)

    now = timezone.now()
    deal = CRMDeal(
        user=user,
        agency=agency,
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
    if next_action_type or next_action_at:
        from workspace.services.crm_deal_followup import set_next_action
        set_next_action(
            deal,
            action_type=next_action_type,
            action_at=next_action_at,
            note=next_action_note,
            save=True,
        )
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


def infer_deal_kind_from_property(prop) -> str:
    """نوع معامله CRM از deal_mode ملک."""
    mode = (getattr(prop, 'deal_mode', None) or '').strip()
    if 'اجاره' in mode or mode == 'رهن و اجاره':
        return 'rent'
    return 'sale'


def deal_kind_label_for_property(prop, deal_kind: str) -> str:
    kind = (deal_kind or '').strip() or infer_deal_kind_from_property(prop)
    mode = (getattr(prop, 'deal_mode', None) or '').strip()
    if kind == 'rent' and mode == 'رهن و اجاره':
        return 'رهن و اجاره'
    if kind == 'rent':
        return 'اجاره'
    return 'فروش'


def default_deal_value_for_property(prop, deal_kind: str = 'sale') -> Optional[int]:
    kind = deal_kind or infer_deal_kind_from_property(prop)
    if kind == 'rent':
        return getattr(prop, 'monthly_rent', None) or None
    return getattr(prop, 'sale_price', None) or None


def suggest_deal_title(property_obj, customer=None, deal_kind: str = 'sale') -> str:
    kind = deal_kind or infer_deal_kind_from_property(property_obj)
    label = deal_kind_label_for_property(property_obj, kind)
    base = (getattr(property_obj, 'title', None) or '').strip()
    if not base:
        parts = [
            getattr(property_obj, 'property_type', '') or 'ملک',
            getattr(property_obj, 'district', '') or getattr(property_obj, 'neighborhood', '') or '',
        ]
        base = ' '.join(p for p in parts if p).strip() or 'ملک'
    title = f'{label} {base}'.strip()
    if customer and getattr(customer, 'name', None):
        return f'{title} به {customer.name}'
    return title


def property_deals_qs(user, property_obj):
    return deals_qs(user).filter(property=property_obj).select_related('customer')


def get_property_active_deals(user, property_obj):
    return property_deals_qs(user, property_obj).filter(
        stage__in=active_stages_for_user(user),
    )


def find_duplicate_active_deal(user, property_obj, customer):
    if not customer:
        return None
    return get_property_active_deals(user, property_obj).filter(customer=customer).first()


def customer_role_for_deal_kind(deal_kind: str) -> str:
    return 'مستاجر' if deal_kind == 'rent' else 'خریدار'


def customer_type_for_deal_kind(deal_kind: str) -> str:
    return 'مستاجر' if deal_kind == 'rent' else 'خریدار'


def deal_type_for_property_contact(property_obj, deal_kind: str) -> str:
    mode = (getattr(property_obj, 'deal_mode', None) or '').strip()
    if deal_kind == 'rent':
        return mode if mode in ('رهن و اجاره', 'اجاره') else 'رهن و اجاره'
    if mode == 'پیش‌فروش':
        return 'پیش‌فروش'
    return 'فروش'


def _mask_phone_display(phone: str) -> str:
    raw = (phone or '').strip()
    if len(raw) < 8:
        return raw or ''
    return f'{raw[:4]}***{raw[-4:]}'


def serialize_property_deal_customer(customer, *, related: bool = False, role: str = '') -> Dict[str, Any]:
    name = customer.name or ''
    if customer.is_legal_entity and customer.company_name:
        name = customer.company_name
        if customer.name:
            name = f'{customer.company_name} — {customer.name}'
    return {
        'id': customer.pk,
        'name': name,
        'phone': _mask_phone_display(customer.phone or ''),
        'phone_raw': customer.phone or '',
        'type': customer.customer_type or '',
        'role': role,
        'related': related,
        'is_legal': bool(customer.is_legal_entity),
        'company_name': customer.company_name or '',
    }


def search_customers_for_property_deal(user, property_obj, query: str = '', limit: int = 12):
    """مخاطبین مرتبط با ملک + جستجوی سراسری scoped."""
    from django.db.models import Q
    from workspace.services.crm_scope import customers_qs

    q = (query or '').strip()
    related: List[Dict[str, Any]] = []
    seen = set()
    for link in property_obj.contact_links.select_related('customer').order_by('-is_primary', '-updated_at'):
        c = link.customer
        if c.pk in seen:
            continue
        seen.add(c.pk)
        if q:
            hay = ' '.join(filter(None, [c.name, c.phone, c.company_name, c.national_id, link.role]))
            if q not in hay and q.lower() not in hay.lower():
                continue
        related.append(serialize_property_deal_customer(c, related=True, role=link.role or ''))
        if len(related) >= limit:
            break

    results: List[Dict[str, Any]] = list(related)
    remaining = max(0, limit - len(results))
    if remaining and q and len(q) >= 2:
        qs = customers_qs(user).filter(
            Q(name__icontains=q) | Q(phone__icontains=q) | Q(company_name__icontains=q)
            | Q(national_id__icontains=q),
        ).exclude(pk__in=seen).order_by('-updated_at')[:remaining]
        for c in qs:
            results.append(serialize_property_deal_customer(c))
    return results


def create_deal_from_property(
    user,
    property_obj,
    customer: Customer,
    *,
    deal_kind: str = '',
    title: str = '',
    stage: str = '',
    value: Optional[int] = None,
    probability: Optional[int] = None,
    expected_close_date: Optional[date] = None,
    notes: str = '',
    next_action_type: str = '',
    next_action_at=None,
    next_action_note: str = '',
    link_contact: bool = True,
) -> CRMDeal:
    """ایجاد معامله از صفحه فایل شخصی — reuse create_deal."""
    from workspace.models import PropertyContact
    from workspace.services.crm import link_customer_property

    kind = (deal_kind or infer_deal_kind_from_property(property_obj)).strip()
    if kind not in ('sale', 'rent'):
        kind = infer_deal_kind_from_property(property_obj)

    stages = get_user_deal_stages(user)
    stage_name = (stage or '').strip() or (stages[0] if stages else 'سرنخ')
    if stage_name not in stages:
        stage_name = stages[0]

    if value is None:
        value = default_deal_value_for_property(property_obj, kind)

    deal_title = (title or '').strip() or suggest_deal_title(property_obj, customer, kind)

    deal = create_deal(
        user,
        customer,
        title=deal_title,
        property_obj=property_obj,
        stage=stage_name,
        value=value,
        probability=probability,
        expected_close_date=expected_close_date,
        notes=notes,
        next_action_type=next_action_type,
        next_action_at=next_action_at,
        next_action_note=next_action_note,
    )
    if deal.deal_kind != kind:
        deal.deal_kind = kind
        from workspace.services.crm_deal_finance import apply_deal_finance
        apply_deal_finance(deal, save=True)

    log_activity(
        customer,
        'املاک',
        content='معامله از فایل شخصی ایجاد شد.',
        title='ثبت معامله',
        property_obj=property_obj,
        metadata={'deal_id': deal.pk, 'stage': deal.stage, 'source': 'property_detail'},
    )

    if link_contact:
        role = customer_role_for_deal_kind(kind)
        exists = PropertyContact.objects.filter(
            customer=customer, property=property_obj,
        ).exists()
        if not exists:
            link_customer_property(
                customer,
                property_obj,
                role,
                deal_type_for_property_contact(property_obj, kind),
                log=True,
            )

    return deal


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
        active_qs = (
            qs.filter(stage__in=active_stages_for_user(user))
            .select_related(None)
            .only('id', 'stage', 'stage_changed_at', 'updated_at', 'created_at', 'user_id')
        )
        for deal in active_qs:
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
