"""سرویس معاملات CRM برای API موبایل."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.core.paginator import Paginator

from mobile_api.serializers import deal_to_dict
from workspace.models import CRMDeal, CRMProperty, Customer
from workspace.services.crm_deals import (
    create_deal,
    filter_deals,
    get_deal_pipeline,
    get_deal_stats,
    update_deal_stage,
)
from workspace.services.crm_deal_stages import get_user_deal_stages
from workspace.services.crm_scope import deal_for_user, deals_qs, get_agency, property_for_user


def list_deals_paginated(
    user,
    *,
    page: int = 1,
    page_size: int = 20,
    query: Optional[Dict[str, Any]] = None,
) -> Tuple[List[dict], dict]:
    params = dict(query or {})
    qs = filter_deals(user, params)
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    items = [deal_to_dict(d) for d in page_obj.object_list]
    meta = {'page': page, 'page_size': page_size, 'total': paginator.count}
    return items, meta


def get_deal_detail(user, deal_id: int) -> Optional[dict]:
    from workspace.services.crm_deal_checklist import ensure_deal_checklist

    deal = (
        deals_qs(user)
        .filter(pk=deal_id)
        .select_related('customer', 'property')
        .first()
    )
    if not deal:
        return None
    ensure_deal_checklist(deal)
    return deal_to_dict(deal, detailed=True)


def create_deal_from_mobile(user, data: Dict[str, Any]) -> CRMDeal:
    customer_id = int(data.get('customer_id') or 0)
    customer = Customer.objects.filter(pk=customer_id, user=user).first()
    if not customer:
        from workspace.services.crm_scope import customers_qs
        customer = customers_qs(user).filter(pk=customer_id).first()
    if not customer:
        raise ValueError('مخاطب یافت نشد.')

    property_obj = None
    property_id = data.get('property_id')
    if property_id:
        property_obj = property_for_user(user, int(property_id))

    value = data.get('amount') if 'amount' in data else data.get('value')
    if value is not None and value != '':
        value = int(value)
    else:
        value = None

    return create_deal(
        user,
        customer,
        title=(data.get('title') or '').strip(),
        property_obj=property_obj,
        listing_token=(data.get('listing_token') or '')[:100],
        stage=(data.get('stage') or 'سرنخ').strip(),
        value=value,
        probability=int(data.get('probability') or 50),
        commission_rate=float(data.get('commission_rate') or 1.0),
        notes=(data.get('notes') or '').strip(),
    )


def update_deal_from_mobile(user, deal_id: int, data: Dict[str, Any]) -> Optional[CRMDeal]:
    deal = deal_for_user(user, deal_id)
    if not deal:
        return None

    if 'title' in data:
        deal.title = (data.get('title') or deal.title).strip()
    if 'amount' in data or 'value' in data:
        raw = data.get('amount', data.get('value'))
        deal.value = int(raw) if raw not in (None, '') else None
    if 'probability' in data:
        deal.probability = int(data.get('probability') or deal.probability)
    if 'notes' in data:
        deal.notes = data.get('notes') or ''
    if 'commission_rate' in data:
        deal.commission_rate = float(data.get('commission_rate') or deal.commission_rate)
    if 'listing_token' in data:
        deal.listing_token = (data.get('listing_token') or '')[:100]

    property_id = data.get('property_id')
    if property_id is not None:
        if property_id:
            deal.property = property_for_user(user, int(property_id))
        else:
            deal.property = None

    deal.save()
    return deal


def change_deal_stage(user, deal_id: int, stage: str, *, lost_reason: str = '') -> Optional[CRMDeal]:
    deal = deal_for_user(user, deal_id)
    if not deal:
        return None
    update_deal_stage(deal, stage, lost_reason=lost_reason)
    return deal


def pipeline_payload(user) -> Dict[str, Any]:
    stages = get_user_deal_stages(user)
    columns = []
    for row in get_deal_pipeline(user, per_column=15):
        columns.append({
            'stage': row['stage'],
            'count': row['count'],
            'total_value': row['total_value'],
            'deals': [deal_to_dict(d) for d in row['deals']],
        })
    return {
        'stages': stages,
        'columns': columns,
        'stats': get_deal_stats(user),
    }


def stages_payload(user) -> List[str]:
    return get_user_deal_stages(user)


def toggle_deal_checklist_item(user, deal_id: int, item_id: str, *, done=None) -> Optional[dict]:
    from workspace.services.crm_deal_checklist import toggle_checklist_item

    deal = deal_for_user(user, deal_id)
    if not deal:
        return None
    try:
        return toggle_checklist_item(deal, item_id, done=done)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc


def delete_deal(user, deal_id: int) -> bool:
    deal = deal_for_user(user, deal_id)
    if not deal:
        return False
    deal.delete()
    return True
