"""قراردادهای دیجیتال معامله — API موبایل."""
from __future__ import annotations

from typing import Any, Dict, Optional

from contracts.constants import CONTRACT_STATUS_FINALIZED
from contracts.services.license_gate import user_has_contract_license
from contracts.services.scope import contract_for_deal
from mobile_api.services.contracts_mobile import create_contract_mobile, serialize_contract
from workspace.services.crm_deals import infer_recommended_contract_type
from workspace.services.crm_scope import deal_for_user


def deal_contracts_payload(user, deal_id: int) -> Optional[Dict[str, Any]]:
    deal = deal_for_user(user, deal_id)
    if not deal:
        return None
    locked = not user_has_contract_license(user)
    qs = list(contract_for_deal(user, deal_id)[:20])
    has_finalized = any(c.status == CONTRACT_STATUS_FINALIZED for c in qs)
    return {
        'deal_id': deal.pk,
        'locked': locked,
        'recommended_type': infer_recommended_contract_type(deal) or 'sale',
        'count': len(qs),
        'has_finalized_digital': has_finalized,
        'contract_metadata_locked': has_finalized,
        'items': [serialize_contract(c) for c in qs],
    }


def create_deal_contract(user, deal_id: int, *, contract_type: str = '') -> Dict[str, Any]:
    deal = deal_for_user(user, deal_id)
    if not deal:
        raise ValueError('معامله یافت نشد.')
    ctype = (contract_type or infer_recommended_contract_type(deal) or 'sale').strip()
    return create_contract_mobile(user, contract_type=ctype, deal_id=deal_id)
