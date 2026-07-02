"""لینک عمومی و متن اشتراک پیشنهاد ملک — بدون لینک دیوار."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote

from django.conf import settings
from django.urls import reverse

from workspace.models import CRMProperty, Customer, Listing
from workspace.services.formatting import format_toman
from workspace.services.listing_public_share import get_or_create_listing_share
from workspace.services.property_public_share import get_or_create_property_share


def absolute_uri(request, path: str) -> str:
    if request:
        return request.build_absolute_uri(path)
    site = getattr(settings, 'SITE_URL', '').rstrip('/')
    if site:
        return f'{site}{path}'
    return path


def _crm_price_label(prop: CRMProperty) -> str:
    if prop.deal_mode == 'فروش' and prop.sale_price:
        return format_toman(prop.sale_price)
    parts = []
    if prop.deposit:
        parts.append(f'رهن {format_toman(prop.deposit)}')
    if prop.monthly_rent:
        parts.append(f'اجاره {format_toman(prop.monthly_rent)}')
    return ' · '.join(parts)


def public_share_url_for_property(user, request, prop: CRMProperty) -> str:
    share = get_or_create_property_share(user, prop)
    path = reverse('listing_public:property_view', kwargs={'share_token': share.share_token})
    return absolute_uri(request, path)


def public_share_url_for_listing(user, request, listing: Listing) -> str:
    share = get_or_create_listing_share(user, listing)
    path = reverse('listing_public:view', kwargs={'share_token': share.share_token})
    return absolute_uri(request, path)


def enrich_match_with_public_url(user, request, match: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(match)
    url = ''
    if match.get('source') == 'crm' and match.get('property_id'):
        prop = CRMProperty.objects.filter(pk=match['property_id'], user=user).first()
        if prop:
            url = public_share_url_for_property(user, request, prop)
    elif match.get('source') == 'divar' and match.get('token'):
        listing = Listing.objects.filter(
            token=match['token'],
            dataset__user=user,
        ).select_related('dataset').first()
        if listing:
            url = public_share_url_for_listing(user, request, listing)
    out['public_share_url'] = url
    return out


def enrich_matches_with_public_urls(
    user,
    request,
    matches: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [enrich_match_with_public_url(user, request, m) for m in matches]


def sharing_link_for_match(match: Dict[str, Any]) -> str:
    """لینک قابل ارسال در پیام — فقط عمومی، نه دیوار."""
    url = (match.get('public_share_url') or match.get('share_url') or '').strip()
    if url:
        return url
    raw = (match.get('link') or '').strip()
    if raw and 'divar.ir' not in raw.lower():
        return raw
    return ''


def resolve_portfolio_share_items(
    user,
    customer: Customer,
    items: List[Dict[str, Any]],
    request,
) -> List[Dict[str, Any]]:
    """تبدیل انتخاب تب املاک به payload اشتراک با لینک عمومی."""
    matches: List[Dict[str, Any]] = []
    for item in items:
        source = item.get('source')
        if source == 'crm':
            pid = item.get('property_id')
            if not pid:
                continue
            if not customer.property_links.filter(
                property_id=pid,
                property__user=user,
            ).exists():
                continue
            prop = CRMProperty.objects.filter(pk=pid, user=user).first()
            if not prop:
                continue
            matches.append({
                'source': 'crm',
                'property_id': prop.pk,
                'title': item.get('title') or prop.title,
                'price_label': item.get('price_label') or _crm_price_label(prop),
                'area': prop.area,
                'neighborhood': prop.neighborhood or prop.district or '',
                'city': prop.city or '',
            })
        elif source == 'divar':
            listing_id = item.get('listing_id')
            token = item.get('token')
            cl_qs = customer.linked_listings.all()
            if listing_id:
                cl = cl_qs.filter(pk=listing_id).first()
            elif token:
                cl = cl_qs.filter(token=token).first()
            else:
                continue
            if not cl:
                continue
            listing = Listing.objects.filter(
                token=cl.token,
                dataset__user=user,
            ).select_related('dataset').first()
            matches.append({
                'source': 'divar',
                'token': cl.token,
                'listing_id': listing.pk if listing else None,
                'title': item.get('title') or cl.title or cl.token,
                'price_label': item.get('price_label') or cl.price or '',
                'area': cl.area or (listing.area if listing else ''),
                'neighborhood': listing.neighborhood if listing else '',
                'city': listing.city if listing else '',
            })
    return enrich_matches_with_public_urls(user, request, matches)


def whatsapp_url_for_customer(customer: Customer, text: str) -> str:
    phone = (customer.phone or '').strip()
    if not phone:
        return ''
    digits = phone[1:] if phone.startswith('0') else phone
    if digits.startswith('98'):
        digits = digits[2:]
    return f'https://wa.me/98{digits}?text={quote(text)}'
