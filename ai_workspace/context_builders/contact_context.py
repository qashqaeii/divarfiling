"""Context Builder — مخاطب CRM."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.models import Customer, CustomerActivity
from workspace.services.crm_matching import get_customer_matches
from workspace.services.formatting import format_toman

from ai_workspace.context_builders.base import mask_phone, truncate


def _budget_range(customer: Customer) -> str:
    if customer.budget_min or customer.budget_max:
        lo = format_toman(customer.budget_min) if customer.budget_min else '—'
        hi = format_toman(customer.budget_max) if customer.budget_max else '—'
        return f'{lo} تا {hi}'
    if customer.deposit_min or customer.deposit_max or customer.rent_min or customer.rent_max:
        parts = []
        if customer.deposit_min or customer.deposit_max:
            parts.append(
                f'رهن {format_toman(customer.deposit_min) if customer.deposit_min else "—"}'
                f' تا {format_toman(customer.deposit_max) if customer.deposit_max else "—"}'
            )
        if customer.rent_min or customer.rent_max:
            parts.append(
                f'اجاره {format_toman(customer.rent_min) if customer.rent_min else "—"}'
                f' تا {format_toman(customer.rent_max) if customer.rent_max else "—"}'
            )
        return ' · '.join(parts)
    return ''


def _top_matches_text(matches: List[Dict[str, Any]], limit: int = 2) -> str:
    lines = []
    for m in matches[:limit]:
        title = m.get('title') or 'ملک'
        score = m.get('score')
        price = m.get('price_label') or ''
        hood = m.get('neighborhood') or m.get('city') or ''
        bit = f'- {title}'
        if price:
            bit += f' ({price})'
        if hood:
            bit += f' — {hood}'
        if score is not None:
            bit += f' [امتیاز سیستم: {score}%]'
        lines.append(bit)
    return '\n'.join(lines)


def build(
    customer: Customer,
    user,
    *,
    channel: str = 'واتساپ',
    tone: str = 'رسمی',
    include_matches: bool = True,
) -> Dict[str, Any]:
    activities = list(
        CustomerActivity.objects.filter(customer=customer)
        .order_by('-created_at')[:2]
    )
    activity_lines = []
    for act in activities:
        activity_lines.append(
            f'{act.activity_type}: {truncate(mask_phone(act.content or act.title or ""), 120)}'
        )

    top_matches: List[Dict[str, Any]] = []
    top_matches_text = ''
    if include_matches:
        try:
            match_data = get_customer_matches(customer, user, divar_enabled=True)
            for key in ('crm_matches', 'divar_matches'):
                top_matches.extend((match_data.get(key) or [])[:2])
            top_matches = sorted(top_matches, key=lambda m: m.get('score', 0), reverse=True)[:2]
            top_matches_text = _top_matches_text(top_matches)
        except Exception:
            top_matches_text = ''

    return {
        'name': customer.name or '',
        'customer_type': customer.customer_type or '',
        'status': customer.status or '',
        'areas': customer.areas or customer.district or '',
        'property_type': customer.property_type or '',
        'budget_range': _budget_range(customer),
        'channel': channel,
        'tone': tone,
        'recent_activities': '\n'.join(activity_lines) if activity_lines else '—',
        'top_matches_text': top_matches_text,
        'content_version': f'{customer.id}:{customer.updated_at.isoformat() if customer.updated_at else ""}',
        '_customer': customer,
    }
