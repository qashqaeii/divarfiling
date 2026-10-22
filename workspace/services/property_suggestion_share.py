"""لینک عمومی و متن اشتراک پیشنهاد ملک — بدون لینک دیوار."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote

from django.conf import settings
from django.urls import reverse

from workspace.models import CRMProperty, Customer, Listing
from workspace.services.formatting import format_toman
from workspace.services.listing_public_share import get_or_create_listing_share
from workspace.services.crm_matching_access import can_create_property_public_link, mask_crm_match_for_viewer
from workspace.services.crm_property_share import build_property_share_context
from workspace.services.crm_scope import properties_qs
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
    if not share:
        return ''
    path = reverse('listing_public:view', kwargs={'share_token': share.share_token})
    return absolute_uri(request, path)


def _internal_url_for_property(request, prop: CRMProperty) -> str:
    path = reverse('workspace:crm_property_detail', kwargs={'property_id': prop.pk})
    return absolute_uri(request, path)


def _internal_url_for_listing(request, listing: Listing) -> str:
    path = reverse(
        'workspace:listing_detail',
        kwargs={'dataset_id': listing.dataset_id, 'listing_id': listing.pk},
    )
    return absolute_uri(request, path)


def enrich_match_with_public_url(user, request, match: Dict[str, Any]) -> Dict[str, Any]:
    """سازگاری با نام قبلی — لینک عمومی + داخلی + دیوار را پر می‌کند."""
    return enrich_match_with_links(user, request, match)


def enrich_match_with_links(user, request, match: Dict[str, Any]) -> Dict[str, Any]:
    """افزودن لینک داخلی سیستم، لینک عمومی و حفظ لینک دیوار."""
    out = dict(match)
    public_url = (out.get('public_share_url') or '').strip()
    internal_url = (out.get('internal_url') or '').strip()

    if match.get('source') == 'crm' and match.get('property_id'):
        prop = properties_qs(user).filter(pk=match['property_id']).first()
        if prop:
            share_ctx = build_property_share_context(user, prop)
            if share_ctx.mask_sensitive:
                out = mask_crm_match_for_viewer(user, prop, out)
            elif can_create_property_public_link(user, prop):
                if not public_url:
                    try:
                        public_url = public_share_url_for_property(user, request, prop)
                    except Exception:
                        public_url = ''
            else:
                public_url = ''
            if not share_ctx.mask_sensitive and not internal_url:
                internal_url = _internal_url_for_property(request, prop)
            if (
                not share_ctx.mask_sensitive
                and not (out.get('link') or '').strip()
                and prop.link
            ):
                out['link'] = prop.link
    elif match.get('source') == 'divar':
        listing = None
        listing_id = match.get('listing_id')
        token = match.get('token')
        qs = Listing.objects.filter(dataset__user=user).select_related('dataset')
        if listing_id:
            listing = qs.filter(pk=listing_id).first()
        if listing is None and token:
            listing = qs.filter(token=token).first()
        if listing:
            if not public_url:
                try:
                    public_url = public_share_url_for_listing(user, request, listing)
                except Exception:
                    public_url = ''
            if not internal_url:
                internal_url = _internal_url_for_listing(request, listing)
            if not (out.get('link') or '').strip() and listing.link:
                out['link'] = listing.link

    out['public_share_url'] = public_url
    out['internal_url'] = internal_url
    return out


def enrich_matches_with_public_urls(
    user,
    request,
    matches: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [enrich_match_with_links(user, request, m) for m in matches]


def enrich_match_data_links(user, request, data: Dict[str, Any]) -> Dict[str, Any]:
    """پر کردن لینک‌ها برای کل payload پیشنهاد هوشمند."""
    out = dict(data)
    out['crm_matches'] = enrich_matches_with_public_urls(user, request, data.get('crm_matches') or [])
    out['divar_matches'] = enrich_matches_with_public_urls(user, request, data.get('divar_matches') or [])
    groups = []
    for group in data.get('match_groups') or []:
        item = dict(group)
        item['crm_matches'] = enrich_matches_with_public_urls(user, request, group.get('crm_matches') or [])
        item['divar_matches'] = enrich_matches_with_public_urls(user, request, group.get('divar_matches') or [])
        groups.append(item)
    out['match_groups'] = groups
    return out


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
            link = customer.property_links.filter(
                property_id=pid,
                property__user=user,
            ).select_related('property').first()
            if not link:
                continue
            prop = link.property
            matches.append({
                'source': 'crm',
                'property_id': prop.pk,
                'title': item.get('title') or prop.title,
                'price_label': item.get('price_label') or _crm_price_label(prop),
                'area': prop.area,
                'neighborhood': prop.neighborhood or prop.district or '',
                'city': prop.city or '',
                'role': (item.get('role') or link.role or '').strip(),
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
                'role': (item.get('role') or cl.role or '').strip(),
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
