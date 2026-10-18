"""لینک عمومی اشتراک‌گذاری آگهی — ساخت کانتکست نمایش حرفه‌ای."""
from __future__ import annotations

import secrets
from typing import Any, Dict, Optional
from urllib.parse import quote

from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

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
from workspace.services.public_share_common import (
    apply_public_approx_privacy,
    build_consultant_block,
    build_finance_summary,
    build_map_navigation,
    build_office_map_marker,
    filter_public_feature_highlights,
    is_public_technical_key,
    prune_public_detail_sections,
    public_feature_details_flag,
    remap_public_section_labels,
    resolve_public_location_accuracy,
    scrub_public_feature_profile,
    strip_duplicate_section_fields,
    texts_are_equivalent,
)
from workspace.services.property_images import deduplicate_divar_image_urls, normalize_external_image_url

_PUBLIC_HIDDEN_SECTIONS = frozenset({'تماس'})


class ListingShareTemplateStub:
    """مقادیر پیش‌فرض مودال اشتراک وقتی هنوز share ساخته نشده."""

    welcome_message = ''
    view_count = 0
    is_active = True
    show_divar_link = False
    approximate_location = False
    approximate_location_radius_m = 500
    show_full_address = False
    show_internal_notes = False
    show_nearby_pois = False
    consultant_name = ''
    consultant_phone = ''
    share_token = ''


def get_listing_share(user, listing: Listing) -> Optional[ListingPublicShare]:
    """فقط share موجود را برمی‌گرداند — بدون mutation."""
    if not listing or not listing.pk:
        return None
    return ListingPublicShare.objects.filter(
        listing_id=listing.pk, created_by=user, is_active=True,
    ).order_by('-created_at').first()


def listing_share_for_display(user, listing: Listing):
    """Share واقعی یا stub برای رندر template."""
    return get_listing_share(user, listing) or ListingShareTemplateStub()


def get_or_create_listing_share(user, listing: Listing) -> Optional[ListingPublicShare]:
    """Share را فقط هنگام درخواست صریح کاربر می‌سازد."""
    if not listing or not listing.pk:
        return None
    if not Listing.objects.filter(pk=listing.pk).exists():
        return None

    share = get_listing_share(user, listing)
    if share:
        return share

    token = _generate_share_token()
    while ListingPublicShare.objects.filter(share_token=token).exists():
        token = _generate_share_token()
    try:
        share = ListingPublicShare.objects.create(
            share_token=token,
            listing_id=listing.pk,
            created_by=user,
        )
        from workspace.services.listing_activity import touch_listing_activity

        touch_listing_activity(user, listing.token)
        return share
    except IntegrityError:
        existing = get_listing_share(user, listing)
        if existing:
            return existing
        if not Listing.objects.filter(pk=listing.pk).exists():
            return None
        raise


def _generate_share_token() -> str:
    return secrets.token_urlsafe(9)


def _is_public_hidden_key(key: str) -> bool:
    return is_public_technical_key(key)


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
    result = strip_duplicate_section_fields(result)
    return remap_public_section_labels(result)


def _consultant_name(user, settings: WorkspaceSettings, share: ListingPublicShare) -> str:
    from workspace.services.public_share_common import consultant_name as shared_consultant_name
    return shared_consultant_name(user, settings, share)


def _consultant_phone(user, share: ListingPublicShare) -> str:
    from workspace.services.public_share_common import consultant_phone as shared_consultant_phone
    return shared_consultant_phone(user, share)


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


def public_share_url(request, share: ListingPublicShare) -> str:
    if not share or not getattr(share, 'share_token', None):
        return ''
    path = reverse('listing_public:view', kwargs={'share_token': share.share_token})
    return request.build_absolute_uri(path)


def listing_public_share_to_dict(share: ListingPublicShare, request=None) -> Dict[str, Any]:
    """سریالایزر API موبایل / وب."""
    from workspace.services.public_share_common import public_share_to_dict
    data = public_share_to_dict(share, request, url_name='listing_public:view')
    if request:
        data['share_url'] = public_share_url(request, share)
    return data


def update_listing_public_share(share: ListingPublicShare, payload: dict) -> ListingPublicShare:
    from workspace.services.public_share_common import (
        normalize_consultant_fields_for_save,
        sanitize_welcome_html,
        save_share_profile_defaults,
        normalize_social_links,
    )

    if 'consultant_name' in payload or 'consultant_phone' in payload:
        name, phone = normalize_consultant_fields_for_save(
            share.created_by,
            payload.get('consultant_name', share.consultant_name),
            payload.get('consultant_phone', share.consultant_phone),
        )
        if 'consultant_name' in payload:
            share.consultant_name = name
        if 'consultant_phone' in payload:
            share.consultant_phone = phone
    if 'welcome_message' in payload:
        share.welcome_message = sanitize_welcome_html(str(payload.get('welcome_message') or ''))
    if 'show_divar_link' in payload:
        share.show_divar_link = bool(payload.get('show_divar_link'))
    if 'approximate_location' in payload:
        share.approximate_location = bool(payload.get('approximate_location'))
    if 'approximate_location_radius_m' in payload:
        from workspace.services.public_share_common import clamp_approx_radius_m
        share.approximate_location_radius_m = clamp_approx_radius_m(
            payload.get('approximate_location_radius_m'),
        )
    if 'is_active' in payload:
        share.is_active = bool(payload.get('is_active'))
    if payload.get('save_as_default_welcome'):
        save_share_profile_defaults(
            share.created_by,
            default_welcome_message=payload.get('welcome_message') or share.welcome_message,
            save_welcome=True,
        )
        share.welcome_message = ''
    if 'social_links' in payload:
        save_share_profile_defaults(
            share.created_by,
            social_links=normalize_social_links(payload.get('social_links') or {}),
            save_socials=True,
        )
    if payload.get('save_as_default_share_message') and 'default_share_message' in payload:
        save_share_profile_defaults(
            share.created_by,
            default_share_message=str(payload.get('default_share_message') or ''),
            save_share_message=True,
        )
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

    feat = extract_listing_features(listing)
    tx = transaction_profile(dataset.transaction_type)
    data = build_listing_display_data(listing, feat, transaction_type=dataset.transaction_type)
    desc = (listing.description or '').strip()
    if desc and not any('توضیح' in k or 'description' in k.lower() for k in data):
        data['توضیحات'] = desc

    sections = format_sections_public(data, tx, show_divar_link=share.show_divar_link)
    sections.pop('سایر', None)
    section_rows = {
        name: format_field_rows(fields, data) for name, fields in sections.items()
    }

    description_text = desc
    if not description_text:
        for key in ('توضیحات', 'description', 'متن آگهی'):
            val = (data.get(key) or '').strip()
            if val and val.lower() not in ('-', 'nan', 'none'):
                description_text = val
                break

    _supp_skip = (
        'ودیعه', 'اجاره', 'قیمت', 'متراژ', 'اتاق', 'طبقه', 'سال ساخت', 'ساخت',
        'توضیح', 'متن آگهی', 'متن کامل', 'شرح', 'description', 'amenities',
        'عرض', 'طول', 'مختصات', 'تصویر', 'ویدیو', 'تاریخ', 'نوع آگهی',
    )
    _supp_hidden_groups = frozenset({'زمان‌بندی', 'رسانه', 'شناسایی'})
    supplementary_fields = [
        row for row in format_supplementary_fields(data, tx, sections)
        if not _is_public_hidden_key(row.get('key', ''))
        and not any(m in row.get('key', '') for m in _supp_skip)
        and not (
            description_text
            and texts_are_equivalent(description_text, str(row.get('display') or row.get('raw') or ''))
        )
        and len(str(row.get('display') or row.get('raw') or '')) <= 180
    ]
    supplementary_groups = [
        {
            'name': g['name'],
            'fields': [
                f for f in g['fields']
                if not _is_public_hidden_key(f.get('key', ''))
                and not any(m in f.get('key', '') for m in _supp_skip)
                and not (
                    description_text
                    and texts_are_equivalent(description_text, str(f.get('display') or f.get('raw') or ''))
                )
                and len(str(f.get('display') or f.get('raw') or '')) <= 180
            ],
        }
        for g in format_supplementary_groups(data, tx, sections)
        if g['name'] not in _supp_hidden_groups
    ]
    supplementary_groups = [g for g in supplementary_groups if g['fields']]

    consultant = build_consultant_block(user, share, title=listing.title or 'ملک')

    category_parts = [p for p in (
        dataset.transaction_type,
        dataset.subcategory,
        listing.city or dataset.city,
        listing.neighborhood or dataset.district,
    ) if p]

    sections, section_rows = prune_public_detail_sections(
        sections,
        section_rows,
        has_description=bool(description_text),
        description_text=description_text,
        hide_hero_sections=True,
    )

    finance = build_finance_summary(listing, tx, data)
    primary_price = finance.get('primary') or ''

    feature_profile = scrub_public_feature_profile(build_listing_feature_profile(listing, feat))
    gallery_images = gallery_images_for_listing(listing)
    location_accuracy = resolve_public_location_accuracy(
        share,
        location_accuracy_for_map(data),
    )
    show_feature_details = public_feature_details_flag(feature_profile)

    listing_map_marker = build_listing_map_marker(
        listing,
        tx,
        feat,
        data=data,
        location_accuracy=location_accuracy,
        thumb=gallery_images[0] if gallery_images else '',
        show_divar_link=share.show_divar_link,
        public=True,
    )
    listing_map_marker, map_navigation = apply_public_approx_privacy(
        latitude=listing.latitude,
        longitude=listing.longitude,
        location_accuracy=location_accuracy,
        marker=listing_map_marker,
        seed=str(getattr(share, 'share_token', '') or listing.pk),
    )

    # اگر پیام مشاور همان متن توضیحات آگهی است، پیام را مخفی کن تا تکرار نشود
    welcome_plain = consultant.get('welcome_message') or ''
    if description_text and texts_are_equivalent(description_text, welcome_plain):
        consultant['has_welcome'] = False
        consultant['welcome_message'] = ''
        consultant['welcome_message_html'] = ''

    from workspace.mixins import get_or_create_settings
    office_map_marker = build_office_map_marker(get_or_create_settings(user))

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
        'show_feature_details': show_feature_details,
        'gallery_images': gallery_images,
        'description_text': description_text,
        'finance': finance,
        'primary_price_label': primary_price,
        'location_accuracy': location_accuracy,
        'listing_map_marker': listing_map_marker,
        'office_map_marker': office_map_marker,
        'office_map_navigation': (consultant.get('agency') or {}).get('map_navigation'),
        'consultant': consultant,
        'category_breadcrumb': category_parts,
        'show_divar_link': share.show_divar_link,
        'meta_description': _meta_description(listing, tx, category_parts),
        'map_navigation': map_navigation,
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
