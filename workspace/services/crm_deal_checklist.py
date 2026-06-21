"""چک‌لیست مدارک معامله — B8."""
from __future__ import annotations

import copy
from typing import Any, Dict, List

from workspace.constants import DEFAULT_DEAL_CHECKLIST
from workspace.models import CRMDeal


def default_checklist() -> List[Dict[str, Any]]:
    return [
        {
            'id': item['id'],
            'label': item['label'],
            'required': bool(item.get('required', False)),
            'done': False,
        }
        for item in DEFAULT_DEAL_CHECKLIST
    ]


def ensure_deal_checklist(deal: CRMDeal, *, save: bool = True) -> List[Dict[str, Any]]:
    if deal.checklist:
        return deal.checklist
    deal.checklist = default_checklist()
    if save:
        deal.save(update_fields=['checklist', 'updated_at'])
    return deal.checklist


def checklist_progress(checklist: list) -> Dict[str, Any]:
    items = checklist or []
    total = len(items)
    done = sum(1 for i in items if i.get('done'))
    required = [i for i in items if i.get('required')]
    required_done = sum(1 for i in required if i.get('done'))
    pct = round(done / total * 100) if total else 0
    return {
        'total': total,
        'done': done,
        'required_total': len(required),
        'required_done': required_done,
        'pct': pct,
        'complete': len(required) == 0 or required_done == len(required),
    }


def toggle_checklist_item(deal: CRMDeal, item_id: str, *, done: bool | None = None) -> Dict[str, Any]:
    items = ensure_deal_checklist(deal, save=False)
    found = False
    updated = copy.deepcopy(items)
    for item in updated:
        if item.get('id') == item_id:
            item['done'] = done if done is not None else not item.get('done', False)
            found = True
            break
    if not found:
        raise ValueError('آیتم چک‌لیست یافت نشد')
    deal.checklist = updated
    deal.save(update_fields=['checklist', 'updated_at'])
    return {
        'checklist': updated,
        'progress': checklist_progress(updated),
    }
