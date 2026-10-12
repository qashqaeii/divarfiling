"""قراردادهای سطح آژانس — لیست مدیریتی برای اپ موبایل."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.core.paginator import Paginator
from django.db.models import Count, Q, QuerySet

from contracts.constants import CONTRACT_STATUS_DRAFT, CONTRACT_STATUS_FINALIZED
from contracts.services.dashboard import ACTION_STATUSES
from mobile_api.services.contracts_mobile import _apply_mobile_filters, serialize_contract
from mobile_api.services.team_mobile import member_to_dict
from workspace.services.agency_data_scope import (
    AgencyDataScopeError,
    get_agency_contracts_qs,
    get_member_contracts_qs,
    list_visible_advisor_members,
    resolve_visible_agency_member,
)
from workspace.services.crm_agency import member_display
from workspace.services.crm_scope import can_manage_team, get_membership


def _advisor_lookup(user) -> Dict[int, Dict[str, Any]]:
    from workspace.services.agency_entitlement import can_view_agency_member

    lookup: Dict[int, Dict[str, Any]] = {}
    for member in list_visible_advisor_members(user):
        if not can_view_agency_member(user, member):
            continue
        label = (member_display(member) or member.user.get_full_name() or '').strip()
        lookup[member.user_id] = {
            'advisor_member_id': member.pk,
            'advisor_name': label or 'مشاور',
        }
    return lookup


def _apply_list_filters(qs: QuerySet, params: Dict[str, Any]) -> QuerySet:
    q = (params.get('q') or params.get('search') or '').strip()
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
    ctype = (params.get('type') or params.get('contract_type') or '').strip()
    if ctype:
        qs = qs.filter(contract_type=ctype)
    deal_id = params.get('deal') or params.get('deal_id')
    if deal_id:
        try:
            qs = qs.filter(deal_id=int(deal_id))
        except (TypeError, ValueError):
            pass
    return _apply_mobile_filters(qs, params)


def _stats_for_qs(qs: QuerySet) -> Dict[str, int]:
    agg = qs.aggregate(
        total=Count('pk'),
        draft=Count('pk', filter=Q(status=CONTRACT_STATUS_DRAFT)),
        pending=Count('pk', filter=Q(status__in=ACTION_STATUSES)),
        finalized=Count('pk', filter=Q(status=CONTRACT_STATUS_FINALIZED)),
        needs_action=Count('pk', filter=Q(status__in=ACTION_STATUSES)),
    )
    return {
        'all': agg['total'] or 0,
        'draft': agg['draft'] or 0,
        'needs_action': agg['needs_action'] or 0,
        'awaiting_acceptance': agg['pending'] or 0,
        'finalized': agg['finalized'] or 0,
    }


def _serialize_agency_item(contract: Contract, lookup: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    row = serialize_contract(contract)
    advisor = lookup.get(contract.user_id) or {}
    row['advisor_member_id'] = advisor.get('advisor_member_id')
    row['advisor_name'] = advisor.get('advisor_name') or ''
    return row


def agency_contracts_for_user(
    user,
    *,
    page: int = 1,
    page_size: int = 20,
    query: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    membership = get_membership(user)
    if not membership:
        return None
    if not can_manage_team(user):
        raise AgencyDataScopeError('دسترسی به قراردادهای تیم مجاز نیست')

    params = dict(query or {})
    advisor_raw = params.get('advisor') or params.get('advisor_member_id') or ''
    advisor_member_id: int | None = None
    if advisor_raw:
        try:
            advisor_member_id = int(advisor_raw)
        except (TypeError, ValueError):
            advisor_member_id = None

    if advisor_member_id:
        member = resolve_visible_agency_member(user, advisor_member_id)
        qs = get_member_contracts_qs(user, member)
    else:
        qs = get_agency_contracts_qs(user)

    base_qs = qs
    filtered_qs = _apply_list_filters(qs, params)
    stats = _stats_for_qs(base_qs)
    lookup = _advisor_lookup(user)
    advisors: List[Dict[str, Any]] = [member_to_dict(m) for m in list_visible_advisor_members(user)]

    paginator = Paginator(filtered_qs.order_by('-updated_at'), page_size)
    page_obj = paginator.get_page(page)
    items = [_serialize_agency_item(c, lookup) for c in page_obj.object_list]

    return {
        'items': items,
        'stats': stats,
        'advisors': advisors,
        'can_filter_advisor': True,
        'meta': {
            'page': page_obj.number,
            'page_size': page_size,
            'total': paginator.count,
        },
    }
