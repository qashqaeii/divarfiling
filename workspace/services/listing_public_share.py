"""لینک عمومی اشتراک‌گذاری آگهی — ساخت کانتکست نمایش حرفه‌ای."""
from __future__ import annotations

import secrets
from typing import Any, Dict, Optional
from urllib.parse import quote

from django.urls import reverse
from django.utils import timezone

from workspace.mixins import get_or_create_settings
from workspace.models import Listing, ListingPublicShare, WorkspaceSettings
from workspace.services.display import (
    build_listing_display_data,
    format_field_rows,
    format_sections,
    format_supplementary_fields,
    format_supplementary_groups,
    location_accuracy_for_map,
    transaction_profile,
)
from workspace.services.listing_map import build_listing_map_marker
from workspace.services.features import extract_listing_features
from workspace.services.listing_features import (
    build_listing_feature_profile,
    feature_highlights_for_listing,
)
from workspace.services.public_share_common import filter_public_feature_highlights, build_map_navigation
from workspace.services.property_images import deduplicate_divar_image_urls, normalize_external_image_url

_PUBLIC_HIDDEN_SECTIONS = frozenset({'تماس'})
_PUBLIC_HIDDEN_KEY_MARKERS = (
    'شناسه', 'token', 'لینک', 'link', 'share_link', 'url',
    'تماس', 'phone', 'تلفن', 'موبایل', 'شماره تماس', 'contact_uuid',
    'contact', 'chat', 'چت',
)


def _generate_share_token() -> str:
    return secrets.token_urlsafe(9)


def _is_public_hidden_key(key: str) -> bool:
    kl = str(key or '').lower()
    return any(m in key or m in kl for m in _PUBLIC_HIDDEN_KEY_MARKERS)


def _filter_section_fields(fields: Dict[str, str], *, show_divar_link: bool) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, val in (fields or {}).items():
        if _is_public_hidden_key(key):
            continue
        if not show_divar_link and any(m in key.lower() for m in ('لینک', 'link', 'url')):
            continue
        out[key] = val
    return out


def format_sections_public(
    data: dict,
    profile: Dict,
    *,
    show_divar_link: bool = False,
) -> Dict[str, Dict[str, str]]:
    sections = format_sections(data, profile)
    result: Dict[str, Dict[str, str]] = {}
    for name, fields in sections.items():
        if name in _PUBLIC_HIDDEN_SECTIONS:
            continue
        filtered = _filter_section_fields(fields, show_divar_link=show_divar_link)
        if filtered:
            result[name] = filtered
    return result


def _consultant_name(user, settings: WorkspaceSettings, share: ListingPublicShare) -> str:
    if share.consultant_name.strip():
        return share.consultant_name.strip()
    if settings.agency_name.strip():
        return settings.agency_name.strip()
    full = (user.get_full_name() or '').strip()
    if full:
        return full
    return 'مشاور املاک'


def _consultant_phone(user, share: ListingPublicShare) -> str:
    if share.consultant_phone.strip():
        return share.consultant_phone.strip()
    return (user.phone or '').strip()


def _phone_whatsapp_digits(phone: str) -> str:
    digits = ''.join(c for c in (phone or '') if c.isdigit())
    if digits.startswith('98'):
        digits = digits[2:]
    elif digits.startswith('0'):
        digits = digits[1:]
    return digits


def consultant_contact_urls(phone: str, message: str = '') -> Dict[str, str]:
    wa_digits = _phone_whatsapp_digits(phone)
    tel = phone.strip() if phone else ''
    urls = {
        'tel_url': f'tel:{tel}' if tel else '',
        'whatsapp_url': '',
    }
    if wa_digits:
        base = f'https://wa.me/98{wa_digits}'
        urls['whatsapp_url'] = f'{base}?text={quote(message)}' if message else base
    return urls


def get_or_create_listing_share(user, listing: Listing) -> ListingPublicShare:
    share = ListingPublicShare.objects.filter(
        listing=listing, created_by=user, is_active=True,
    ).order_by('-created_at').first()
    if share:
        return share
    token = _generate_share_token()
    while ListingPublicShare.objects.filter(share_token=token).exists():
        token = _generate_share_token()
    return ListingPublicShare.objects.create(
        share_token=token,
        listing=listing,
        created_by=user,
    )


def public_share_url(request, share: ListingPublicShare) -> str:
    path = reverse('listing_public:view', kwargs={'share_token': share.share_token})
    return request.build_absolute_uri(path)


def listing_public_share_to_dict(share: ListingPublicShare, request=None) -> Dict[str, Any]:
    """سریالایزر API موبایل / وب."""
    return {
        'share_url': public_share_url(request, share) if request else '',
        'share_token': share.share_token,
        'view_count': share.view_count,
        'is_active': share.is_active,
        'consultant_name': share.consultant_name,
        'consultant_phone': share.consultant_phone,
        'welcome_message': share.welcome_message,
        'show_divar_link': share.show_divar_link,
    }


def update_listing_public_share(share: ListingPublicShare, payload: dict) -> ListingPublicShare:
    if 'consultant_name' in payload:
        share.consultant_name = str(payload.get('consultant_name') or '').strip()[:200]
    if 'consultant_phone' in payload:
        share.consultant_phone = str(payload.get('consultant_phone') or '').strip()[:20]
    if 'welcome_message' in payload:
        share.welcome_message = str(payload.get('welcome_message') or '').strip()
    if 'show_divar_link' in payload:
        share.show_divar_link = bool(payload.get('show_divar_link'))
    if 'is_active' in payload:
        share.is_active = bool(payload.get('is_active'))
    share.save()
    return share


def gallery_images_for_listing(listing: Listing) -> list:
    return deduplicate_divar_image_urls(
        [normalize_external_image_url(img) for img in (listing.images or []) if img],
    )


def build_public_listing_context(share: ListingPublicShare, request=None) -> Dict[str, Any]:
    listing = share.listing
    dataset = listing.dataset
    user = share.created_by
    settings = get_or_create_settings(user)

    feat = extract_listing_features(listing)
    tx = transaction_profile(dataset.transaction_type)
    data = build_listing_display_data(listing, feat)
    desc = (listing.description or '').strip()
    if desc and not any('توضیح' in k or 'description' in k.lower() for k in data):
        data['توضیحات'] = desc

    sections = format_sections_public(data, tx, show_divar_link=share.show_divar_link)
    sections.pop('سایر', None)
    section_rows = {
        name: format_field_rows(fields, data) for name, fields in sections.items()
    }
    supplementary_fields = [
        row for row in format_supplementary_fields(data, tx, sections)
        if not _is_public_hidden_key(row.get('key', ''))
    ]
    supplementary_groups = [
        {
            'name': g['name'],
            'fields': [f for f in g['fields'] if not _is_public_hidden_key(f.get('key', ''))],
        }
        for g in format_supplementary_groups(data, tx, sections)
    ]
    supplementary_groups = [g for g in supplementary_groups if g['fields']]

    consultant_name = _consultant_name(user, settings, share)
    consultant_phone = _consultant_phone(user, share)
    wa_message = f'سلام {consultant_name}، درباره آگهی «{listing.title or "ملک"}» اطلاعات بیشتری می‌خواهم.'
    contact = consultant_contact_urls(consultant_phone, wa_message)

    category_parts = [p for p in (
        dataset.transaction_type,
        dataset.subcategory,
        listing.city or dataset.city,
        listing.neighborhood or dataset.district,
    ) if p]

    description_text = desc
    if not description_text:
        for key in ('توضیحات', 'description', 'متن آگهی'):
            val = (data.get(key) or '').strip()
            if val and val.lower() not in ('-', 'nan', 'none'):
                description_text = val
                break

    primary_price = ''
    if tx.get('show_price') and listing.price:
        from workspace.services.formatting import format_toman
        primary_price = format_toman(listing.price)
    elif tx.get('show_rent') and listing.rent:
        from workspace.services.formatting import format_toman
        primary_price = f'اجاره {format_toman(listing.rent)}'
    elif tx.get('show_deposit') and listing.deposit:
        from workspace.services.formatting import format_toman
        primary_price = f'ودیعه {format_toman(listing.deposit)}'

    feature_profile = build_listing_feature_profile(listing, feat)
    gallery_images = gallery_images_for_listing(listing)
    location_accuracy = location_accuracy_for_map(data)
    return {
        'share': share,
        'listing': listing,
        'dataset': dataset,
        'feat': feat,
        'tx': tx,
        'sections': sections,
        'section_rows': section_rows,
        'supplementary_fields': supplementary_fields,
        'supplementary_groups': supplementary_groups,
        'feature_profile': feature_profile,
        'feature_highlights': filter_public_feature_highlights(
            feature_profile,
            feature_highlights_for_listing(listing, limit=8),
        ),
        'gallery_images': gallery_images,
        'description_text': description_text,
        'primary_price_label': primary_price,
        'location_accuracy': location_accuracy,
        'listing_map_marker': build_listing_map_marker(
            listing,
            tx,
            feat,
            data=data,
            location_accuracy=location_accuracy,
            thumb=gallery_images[0] if gallery_images else '',
            show_divar_link=share.show_divar_link,
            public=True,
        ),
        'consultant': {
            'name': consultant_name,
            'phone': consultant_phone,
            'phone_display': consultant_phone,
            'has_phone': bool(consultant_phone),
            'agency_name': settings.agency_name.strip(),
            'agency_logo': settings.agency_logo,
            'welcome_message': share.welcome_message.strip(),
            **contact,
        },
        'category_breadcrumb': category_parts,
        'show_divar_link': share.show_divar_link,
        'meta_description': _meta_description(listing, tx, category_parts),
        'map_navigation': build_map_navigation(listing.latitude, listing.longitude),
    }


def _meta_description(listing, tx, category_parts) -> str:
    parts = [listing.title or 'ملک']
    if listing.area:
        parts.append(f'{int(listing.area)} متر')
    if tx.get('show_price') and listing.price:
        parts.append('فروش')
    elif tx.get('show_rent') and listing.rent:
        parts.append('اجاره')
    if category_parts:
        parts.append(' · '.join(category_parts[:2]))
    return ' — '.join(parts)[:300]


def record_share_view(share: ListingPublicShare) -> None:
    from django.db.models import F
    ListingPublicShare.objects.filter(pk=share.pk).update(
        view_count=F('view_count') + 1,
        last_viewed_at=timezone.now(),
    )
