"""Context Builder — مخاطب CRM."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.models import Customer, CustomerActivity, Listing
from workspace.services.crm_matching import get_customer_matches
from workspace.services.crm_scope import properties_qs
from workspace.services.formatting import format_toman
from workspace.services.listing_public_share import get_or_create_listing_share
from workspace.services.property_public_share import get_or_create_property_share
from workspace.services.public_share_common import absolute_public_share_url

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


def _resolve_match_public_url(user, match: Dict[str, Any]) -> str:
    try:
        if match.get('source') == 'divar' and match.get('listing_id'):
            listing = Listing.objects.filter(
                pk=match['listing_id'],
                dataset__user=user,
            ).first()
            if listing:
                share = get_or_create_listing_share(user, listing)
                return absolute_public_share_url(
                    'listing_public:view',
                    share_token=share.share_token,
                )
        if match.get('source') == 'crm' and match.get('property_id'):
            prop = properties_qs(user).filter(pk=match['property_id']).first()
            if prop:
                share = get_or_create_property_share(user, prop)
                return absolute_public_share_url(
                    'listing_public:property_view',
                    share_token=share.share_token,
                )
    except Exception:
        return ''
    return ''


def _enrich_matches(user, matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for match in matches:
        row = dict(match)
        row['public_url'] = _resolve_match_public_url(user, match)
        enriched.append(row)
    return enriched


def _format_match_line(index: int, match: Dict[str, Any]) -> str:
    title = match.get('title') or 'ملک'
    price = match.get('price_label') or ''
    hood = match.get('neighborhood') or match.get('city') or ''
    score = match.get('score')
    deal = match.get('deal_mode') or ''
    public_url = match.get('public_url') or ''

    parts = [f'{index}. {title}']
    if deal:
        parts.append(f'({deal})')
    if price:
        parts.append(f'— {price}')
    if hood:
        parts.append(f'— {hood}')
    if score is not None:
        parts.append(f'[امتیاز سیستم: {int(round(float(score)))}%]')
    line = ' '.join(parts)
    if public_url:
        line += f'\n   لینک صفحه عمومی: {public_url}'
    return line


def _top_matches_text(matches: List[Dict[str, Any]], limit: int = 2) -> str:
    lines = [_format_match_line(i, m) for i, m in enumerate(matches[:limit], start=1)]
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
            combined: List[Dict[str, Any]] = []
            for key in ('crm_matches', 'divar_matches'):
                combined.extend((match_data.get(key) or [])[:2])
            combined = sorted(combined, key=lambda m: m.get('score', 0), reverse=True)[:2]
            top_matches = _enrich_matches(user, combined)
            top_matches_text = _top_matches_text(top_matches)
        except Exception:
            top_matches = []
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
        'top_matches': top_matches,
        'top_matches_text': top_matches_text,
        'content_version': f'{customer.id}:{customer.updated_at.isoformat() if customer.updated_at else ""}',
        '_customer': customer,
        '_user': user,
    }
