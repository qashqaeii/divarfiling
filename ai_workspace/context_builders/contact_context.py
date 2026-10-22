"""Context Builder — مخاطب CRM."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ai_workspace.constants import crm_tone_meta, normalize_crm_tone
from workspace.models import Customer, CustomerActivity, Listing
from workspace.services.crm_matching import get_customer_matches
from workspace.services.crm_matching_access import can_create_property_public_link
from workspace.services.crm_scope import properties_qs
from workspace.services.formatting import format_toman
from workspace.services.listing_public_share import get_or_create_listing_share
from workspace.services.property_public_share import get_or_create_property_share
from workspace.services.public_share_common import absolute_public_share_url

from django.utils import timezone

from ai_workspace.context_builders.base import truncate


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
                if not share:
                    return ''
                return absolute_public_share_url(
                    'listing_public:view',
                    share_token=share.share_token,
                )
        if match.get('source') == 'crm' and match.get('property_id'):
            prop = properties_qs(user).filter(pk=match['property_id']).first()
            if prop and can_create_property_public_link(user, prop):
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


def _activity_when_label(created_at) -> str:
    if not created_at:
        return 'نامشخص'
    now = timezone.localtime(timezone.now())
    act_dt = timezone.localtime(created_at)
    days = (now.date() - act_dt.date()).days
    if days <= 0:
        return 'امروز'
    if days == 1:
        return 'دیروز'
    return f'{days} روز پیش'


def _recent_activity_summaries(activities, limit: int = 2) -> str:
    """فقط نوع فعالیت + زمان — بدون متن خام (PII)."""
    lines = []
    for act in activities[:limit]:
        when = _activity_when_label(act.created_at)
        kind = (act.activity_type or 'فعالیت').strip()
        lines.append(f'{kind}: {when}')
    return '\n'.join(lines) if lines else '—'


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
    recent_activities = _recent_activity_summaries(activities)

    top_matches_text = ''
    if include_matches:
        try:
            match_data = get_customer_matches(customer, user, divar_enabled=True)
            combined: List[Dict[str, Any]] = []
            for key in ('crm_matches', 'divar_matches'):
                combined.extend((match_data.get(key) or [])[:2])
            combined = sorted(combined, key=lambda m: m.get('score', 0), reverse=True)[:2]
            enriched = _enrich_matches(user, combined)
            top_matches_text = _top_matches_text(enriched)
        except Exception:
            top_matches_text = ''

    tone_key = normalize_crm_tone(tone)
    tone_info = crm_tone_meta(tone_key)

    return {
        'name': customer.name or '',
        'customer_type': customer.customer_type or '',
        'status': customer.status or '',
        'areas': customer.areas or customer.district or '',
        'property_type': customer.property_type or '',
        'budget_range': _budget_range(customer),
        'channel': channel,
        'tone': tone_key,
        'tone_guide': tone_info['guide'],
        'emoji_rule': 'بدون ایموجی بنویسید.',
        'recent_activities': recent_activities,
        'top_matches_text': top_matches_text,
        'content_version': f'{customer.id}:{customer.updated_at.isoformat() if customer.updated_at else ""}',
        '_customer': customer,
        '_user': user,
    }
