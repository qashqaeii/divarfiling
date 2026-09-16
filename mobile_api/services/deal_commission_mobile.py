"""تقسیم کمیسیون معامله — API موبایل."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.models import CRMDealCommissionSplit
from workspace.services.crm_agency import (
    can_manage_team,
    get_membership,
    member_display,
    set_commission_splits,
)
from workspace.services.crm_scope import agency_members
from workspace.services.crm_scope import deal_for_user


def _serialize_split(row: CRMDealCommissionSplit) -> dict:
    member = row.member
    return {
        'member_id': member.pk,
        'name': member_display(member),
        'role': member.role,
        'percent': float(row.percent or 0),
        'amount': row.amount,
    }


def commission_splits_payload(user, deal_id: int) -> Optional[Dict[str, Any]]:
    deal = deal_for_user(user, deal_id)
    if not deal:
        return None
    membership = get_membership(user)
    members = []
    if membership:
        for m in agency_members(membership.agency):
            members.append({
                'member_id': m.pk,
                'name': member_display(m),
                'role': m.role,
            })
    rows = list(
        deal.commission_splits.select_related('member__user').order_by('-percent', 'pk'),
    )
    allocated = sum(float(r.percent or 0) for r in rows)
    total = int(deal.commission_amount or 0)
    return {
        'deal_id': deal.pk,
        'total_commission': total,
        'allocated_percent': round(allocated, 2),
        'is_complete': abs(allocated - 100) <= 0.01 if rows else True,
        'can_edit': can_manage_team(user),
        'splits': [_serialize_split(r) for r in rows],
        'available_members': members,
    }


def save_commission_splits(user, deal_id: int, splits: List[Dict[str, Any]]) -> Dict[str, Any]:
    deal = deal_for_user(user, deal_id)
    if not deal:
        raise ValueError('معامله یافت نشد.')
    set_commission_splits(user, deal, splits)
    payload = commission_splits_payload(user, deal_id)
    if not payload:
        raise ValueError('معامله یافت نشد.')
    return payload
