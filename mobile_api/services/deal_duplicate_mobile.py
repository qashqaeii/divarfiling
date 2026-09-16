"""بررسی معامله تکراری برای موبایل."""
from __future__ import annotations

from typing import Any, Dict, Optional

from mobile_api.serializers import deal_to_dict
from workspace.services.crm_deals import find_duplicate_active_deal
from workspace.services.crm_scope import customers_qs, property_for_user
from workspace.services.crm_deal_followup import last_follow_up_summary


def duplicate_deal_payload(user, *, property_id: int, customer_id: int) -> Dict[str, Any]:
    prop = property_for_user(user, int(property_id))
    if not prop:
        raise ValueError('ملک یافت نشد.')
    customer = customers_qs(user).filter(pk=int(customer_id)).first()
    if not customer:
        raise ValueError('مخاطب یافت نشد.')
    dup = find_duplicate_active_deal(user, prop, customer)
    if not dup:
        return {'duplicate': False, 'deal': None}
    last = last_follow_up_summary(dup)
    deal_data = deal_to_dict(dup)
    deal_data['last_follow_up'] = last
    return {
        'duplicate': True,
        'deal': deal_data,
    }
