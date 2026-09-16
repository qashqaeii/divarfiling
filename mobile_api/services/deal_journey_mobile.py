"""Deal Journey contextual payload for mobile."""
from __future__ import annotations

from typing import Any, Dict, Optional

from contracts.services.routing import contract_create_url, contract_manage_url, contract_wizard_url
from contracts.services.scope import contract_for_deal
from workspace.services.crm_deal_checklist import checklist_progress, ensure_deal_checklist
from workspace.services.crm_deal_followup import serialize_next_action
from workspace.services.crm_scope import deal_for_user
from workspace.services.deal_journey import build_deal_journey_context


def _mobile_action(primary: dict, *, contracts: list) -> str:
    action = (primary.get('action') or '').strip()
    if action == 'create_contract':
        return 'CREATE_CONTRACT'
    if action == 'complete_next_action':
        return 'COMPLETE_NEXT_ACTION'
    if action == 'drawer-next-action':
        return 'OPEN_NEXT_ACTION'
    if action == 'drawer-followup':
        return 'OPEN_FOLLOW_UP'
    if action == 'drawer-finance':
        return 'TAB_FINANCE'
    if action == 'call':
        return 'CALL_CUSTOMER'
    url = (primary.get('url') or '').strip()
    if 'tab=contracts' in url:
        return 'TAB_CONTRACTS'
    if 'tab=finance' in url:
        return 'TAB_FINANCE'
    if 'tab=activity' in url:
        return 'TAB_ACTIVITY'
    if 'tab=documents' in url:
        return 'TAB_CHECKLIST'
    if url and contracts:
        c = contracts[0]
        if c.status == 'draft':
            return 'CONTINUE_CONTRACT'
        if c.status in ('sent', 'viewed', 'partially_accepted', 'fully_accepted', 'ready'):
            return 'VIEW_SIGNATURE'
        if c.status == 'finalized':
            return 'VIEW_CONTRACT'
        return 'VIEW_CONTRACT'
    return 'OPEN_NEXT_ACTION'


def _serialize_cta(primary: dict, *, contracts: list) -> Dict[str, Any]:
    action = _mobile_action(primary, contracts=contracts)
    web_path = ''
    raw_url = (primary.get('url') or '').strip()
    if raw_url.startswith('/'):
        web_path = raw_url
    elif action in ('CONTINUE_CONTRACT', 'VIEW_CONTRACT', 'VIEW_SIGNATURE') and contracts:
        c = contracts[0]
        if c.status == 'draft':
            web_path = contract_wizard_url(c)
        else:
            web_path = contract_manage_url(c)
    elif action == 'CREATE_CONTRACT' and contracts is not None:
        pass
    return {
        'label': primary.get('label') or '',
        'description': primary.get('desc') or '',
        'kind': primary.get('kind') or 'primary',
        'action': action,
        'web_path': web_path,
    }


def deal_journey_payload(user, deal_id: int) -> Optional[Dict[str, Any]]:
    deal = (
        deal_for_user(user, deal_id)
    )
    if not deal:
        return None
    ensure_deal_checklist(deal)
    contracts = list(contract_for_deal(user, deal_id))
    next_action = serialize_next_action(deal)
    progress = checklist_progress(deal.checklist or [])
    journey = build_deal_journey_context(
        deal,
        user=user,
        next_action=next_action,
        checklist_progress=progress,
        contracts=contracts,
        contracts_count=len(contracts),
    )
    primary = journey.get('primary') or {}
    secondary = []
    for item in journey.get('secondary') or []:
        sec_primary = dict(item)
        secondary.append({
            'label': sec_primary.get('label') or '',
            'action': _mobile_action(sec_primary, contracts=contracts),
            'web_path': sec_primary.get('url') if str(sec_primary.get('url', '')).startswith('/') else '',
            'warn': bool(sec_primary.get('warn')),
        })
    create_path = contract_create_url(deal.pk)
    return {
        'headline': journey.get('headline') or '',
        'subline': journey.get('subline') or '',
        'stage_kind': journey.get('stage_kind') or '',
        'is_stale': bool(journey.get('is_stale')),
        'primary': _serialize_cta(primary, contracts=contracts),
        'secondary': secondary,
        'create_contract_path': create_path,
    }
