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
from workspace.services.crm_deal_stages import (
    apply_stage_preset,
    get_user_deal_stage_defs,
    get_user_deal_stages,
    reset_user_deal_stages,
    save_user_deal_stage_defs,
    serialize_stages_payload,
    stage_meta_map,
)
from workspace.services.crm_scope import (
    can_create_property_deal,
    can_edit_customer,
    can_edit_deal,
    customer_for_user,
    deal_for_user,
    deals_qs,
    get_agency,
    property_for_user,
)


def _parse_mobile_date(value):
    """ISO یا شمسی را به date تبدیل می‌کند."""
    from datetime import date as date_cls

    from workspace.services.jalali_input import parse_jalali_date_string

    if value in (None, ''):
        return None
    if hasattr(value, 'year') and not hasattr(value, 'hour'):
        return value
    parsed = parse_jalali_date_string(str(value))
    if parsed:
        return parsed
    try:
        return date_cls.fromisoformat(str(value)[:10])
    except ValueError:
        return None


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
    meta_map = stage_meta_map(user)
    items = [deal_to_dict(d, stage_meta=meta_map.get(d.stage) or {}) for d in page_obj.object_list]
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
        from workspace.services.agency_data_scope import deal_for_agency_viewer

        deal = deal_for_agency_viewer(user, deal_id)
        if deal:
            deal = (
                CRMDeal.objects.filter(pk=deal.pk)
                .select_related('customer', 'property')
                .first()
            )
    if not deal:
        return None
    ensure_deal_checklist(deal)
    meta = stage_meta_map(user).get(deal.stage) or {}
    return deal_to_dict(deal, detailed=True, stage_meta=meta)


def create_deal_from_mobile(user, data: Dict[str, Any]) -> CRMDeal:
    customer_id = int(data.get('customer_id') or 0)
    customer = customer_for_user(user, customer_id)
    if not customer:
        raise ValueError('مخاطب یافت نشد.')
    if not can_edit_customer(user, customer):
        raise PermissionError('امکان ثبت معامله برای این مخاطب را ندارید')

    property_obj = None
    property_id = data.get('property_id')
    if property_id:
        property_obj = property_for_user(user, int(property_id))
        if not property_obj:
            raise ValueError('ملک یافت نشد.')
        if not can_create_property_deal(user, property_obj):
            raise PermissionError('امکان ثبت معامله برای این ملک را ندارید')

    value = data.get('amount') if 'amount' in data else data.get('value')
    if value is not None and value != '':
        value = int(value)
    else:
        value = None

    probability = None
    if 'probability' in data and data.get('probability') not in (None, ''):
        probability = int(data.get('probability'))

    expected_close = data.get('expected_close_date') or None
    if expected_close:
        expected_close = _parse_mobile_date(expected_close)

    from workspace.services.crm_deal_followup import parse_next_action_payload
    na = parse_next_action_payload(data.get('next_action') or data)

    deal = create_deal(
        user,
        customer,
        title=(data.get('title') or '').strip(),
        property_obj=property_obj,
        listing_token=(data.get('listing_token') or '')[:100],
        stage=(data.get('stage') or 'سرنخ').strip(),
        value=value,
        probability=probability,
        expected_close_date=expected_close,
        commission_rate=float(data.get('commission_rate') or 1.0),
        notes=(data.get('notes') or '').strip(),
        next_action_type=na.get('action_type', ''),
        next_action_at=na.get('action_at'),
        next_action_note=na.get('note', ''),
    )
    return deal


def update_deal_from_mobile(user, deal_id: int, data: Dict[str, Any]) -> Optional[CRMDeal]:
    deal = deal_for_user(user, deal_id)
    if not deal:
        return None
    if not can_edit_deal(user, deal):
        raise PermissionError('امکان ویرایش این معامله را ندارید')

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
        new_rate = float(data.get('commission_rate') or deal.commission_rate)
        if abs(new_rate - (deal.commission_rate or 0)) > 0.05:
            deal.buyer_commission_rate = new_rate / 2.0
            deal.seller_commission_rate = new_rate / 2.0
        deal.commission_rate = new_rate
    if 'listing_token' in data:
        deal.listing_token = (data.get('listing_token') or '')[:100]
    if 'expected_close_date' in data:
        raw = data.get('expected_close_date')
        if not raw:
            deal.expected_close_date = None
        else:
            deal.expected_close_date = _parse_mobile_date(raw) or deal.expected_close_date
    if 'contract_number' in data:
        deal.contract_number = (data.get('contract_number') or '')[:100]
    if 'contract_amount' in data:
        raw = data.get('contract_amount')
        deal.contract_amount = int(raw) if raw not in (None, '') else None
    if 'contract_date' in data:
        raw = data.get('contract_date')
        deal.contract_date = _parse_mobile_date(raw) if raw else None

    property_id = data.get('property_id')
    if property_id is not None:
        if property_id:
            deal.property = property_for_user(user, int(property_id))
        else:
            deal.property = None

    from workspace.services.crm_deal_finance import apply_deal_finance

    apply_deal_finance(deal, save=False)
    deal.save()
    stage = (data.get('stage') or '').strip()
    if stage and stage != deal.stage:
        update_deal_stage(deal, stage, lost_reason=(data.get('lost_reason') or ''))
    return deal


def change_deal_stage(user, deal_id: int, stage: str, *, lost_reason: str = '') -> Optional[CRMDeal]:
    deal = deal_for_user(user, deal_id)
    if not deal:
        return None
    update_deal_stage(deal, stage, lost_reason=lost_reason)
    return deal


def pipeline_payload(user) -> Dict[str, Any]:
    stages = get_user_deal_stages(user)
    meta_map = stage_meta_map(user)
    columns = []
    for row in get_deal_pipeline(user, per_column=15):
        columns.append({
            'stage': row['stage'],
            'count': row['count'],
            'stale_count': row.get('stale_count') or 0,
            'total_value': row['total_value'],
            'color': row.get('color') or '',
            'bg': row.get('bg') or '',
            'icon': row.get('icon') or '',
            'probability': row.get('probability'),
            'definition': row.get('definition') or {},
            'deals': [
                deal_to_dict(d, stage_meta=meta_map.get(d.stage) or {})
                for d in row['deals']
            ],
        })
    return {
        'stages': stages,
        'definitions': get_user_deal_stage_defs(user),
        'columns': columns,
        'stats': get_deal_stats(user),
    }


def stages_payload(user) -> dict:
    return serialize_stages_payload(user)


def save_stages_from_mobile(user, data: Dict[str, Any]) -> dict:
    if data.get('reset'):
        reset_user_deal_stages(user)
        return serialize_stages_payload(user)
    preset = (data.get('preset') or '').strip()
    if preset:
        apply_stage_preset(user, preset)
        return serialize_stages_payload(user)
    raw = data.get('definitions')
    if raw is None:
        raw = data.get('stages') or []
    save_user_deal_stage_defs(user, raw)
    return serialize_stages_payload(user)


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


def finance_dashboard_payload(user, period: str = 'month') -> dict:
    from workspace.services.crm_deal_finance import finance_dashboard

    return finance_dashboard(user, period)


def finance_settings_payload(user) -> dict:
    from workspace.services.crm_deal_finance import get_finance_defaults

    return {'defaults': get_finance_defaults(user)}


def save_finance_settings_from_mobile(user, data: Dict[str, Any]) -> dict:
    from workspace.services.crm_deal_finance import save_finance_defaults

    payload = data.get('defaults') if isinstance(data.get('defaults'), dict) else data
    return {'defaults': save_finance_defaults(user, payload)}


def update_deal_finance_from_mobile(user, deal_id: int, data: Dict[str, Any]) -> Optional[CRMDeal]:
    from workspace.services.crm_deal_finance import apply_deal_finance

    deal = deal_for_user(user, deal_id)
    if not deal:
        return None
    apply_deal_finance(deal, data, save=True)
    return deal


def create_follow_up_from_mobile(user, deal_id: int, data: Dict[str, Any]) -> Optional[dict]:
    from workspace.services.crm_deal_followup import (
        clear_next_action, create_follow_up, get_deal_timeline,
        parse_next_action_payload, serialize_next_action,
    )

    deal = deal_for_user(user, deal_id)
    if not deal:
        return None
    follow_type = (data.get('type') or data.get('follow_up_type') or '').strip()
    note = (data.get('note') or data.get('result') or '').strip()
    if not follow_type:
        raise ValueError('نوع پیگیری الزامی است.')
    from workspace.services.crm_deal_followup import (
        _follow_up_next_action_payload, clear_next_action, create_follow_up, get_deal_timeline,
        parse_next_action_payload, serialize_next_action,
    )

    na = parse_next_action_payload(_follow_up_next_action_payload(data))
    create_follow_up(
        deal,
        user,
        follow_up_type=follow_type,
        note=note,
        next_action_type='' if na.get('clear') else na.get('action_type', ''),
        next_action_at=None if na.get('clear') else na.get('action_at'),
        next_action_note='' if na.get('clear') else na.get('note', ''),
    )
    if na.get('clear'):
        clear_next_action(deal, save=True)
    return {
        'next_action': serialize_next_action(deal),
        'timeline_preview': get_deal_timeline(deal, limit=8, offset=0)['items'],
    }


def update_next_action_from_mobile(user, deal_id: int, data: Dict[str, Any]) -> Optional[dict]:
    from workspace.services.crm_deal_followup import (
        clear_next_action, parse_next_action_payload, serialize_next_action, set_next_action,
    )

    deal = deal_for_user(user, deal_id)
    if not deal:
        return None
    na = parse_next_action_payload(data)
    if na.get('clear') or (not na.get('action_type') and not na.get('action_at')):
        clear_next_action(deal, save=True)
    else:
        set_next_action(
            deal,
            action_type=na.get('action_type', ''),
            action_at=na.get('action_at'),
            note=na.get('note', ''),
            save=True,
        )
    return {'next_action': serialize_next_action(deal)}


def complete_next_action_from_mobile(user, deal_id: int, data: Dict[str, Any]) -> Optional[dict]:
    from workspace.services.crm_deal_followup import (
        complete_next_action, get_deal_timeline, serialize_next_action,
    )

    deal = deal_for_user(user, deal_id)
    if not deal:
        return None
    note = (data.get('note') or data.get('result') or '').strip()
    follow_up = complete_next_action(deal, user, result_note=note)
    if not follow_up:
        raise ValueError('اقدام بعدی تعیین نشده.')
    return {
        'next_action': serialize_next_action(deal),
        'timeline_preview': get_deal_timeline(deal, limit=8, offset=0)['items'],
    }


def timeline_payload(user, deal_id: int, *, limit: int = 30, offset: int = 0) -> Optional[dict]:
    from workspace.services.crm_deal_followup import get_deal_timeline

    deal = deal_for_user(user, deal_id)
    if not deal:
        return None
    return get_deal_timeline(deal, limit=limit, offset=offset)
