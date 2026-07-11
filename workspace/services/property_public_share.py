"""لینک عمومی اشتراک‌گذاری فایل شخصی CRM."""
from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from django.utils import timezone

from workspace.constants import LISTING_CORE_AMENITIES
from workspace.models import CRMProperty, CRMPropertyPublicShare
from workspace.services.crm import resolve_listing_for_property
from workspace.services.display import (
    format_field_rows,
    transaction_profile,
)
from workspace.services.features import extract_listing_features, parse_bool_feature
from workspace.services.listing_features import build_listing_feature_profile, _icon_for_key
from workspace.services.listing_map import build_listing_map_marker
from workspace.services.listing_public_share import format_sections_public
from workspace.services.property_images import deduplicate_divar_image_urls, normalize_external_image_url
from workspace.services.public_share_common import (
    build_consultant_block,
    build_finance_summary,
    build_map_navigation,
    filter_public_feature_highlights,
    prune_public_detail_sections,
    public_feature_details_flag,
    public_share_to_dict,
    scrub_public_feature_profile,
    texts_are_equivalent,
    unique_share_token,
)


def get_or_create_property_share(user, prop: CRMProperty) -> CRMPropertyPublicShare:
    share = CRMPropertyPublicShare.objects.filter(
        property=prop, created_by=user, is_active=True,
    ).order_by('-created_at').first()
    if share:
        return share
    return CRMPropertyPublicShare.objects.create(
        share_token=unique_share_token(CRMPropertyPublicShare),
        property=prop,
        created_by=user,
    )


def property_public_share_url(request, share: CRMPropertyPublicShare) -> str:
    return public_share_to_dict(share, request, url_name='listing_public:property_view')['share_url']


def property_public_share_to_dict(share: CRMPropertyPublicShare, request=None) -> Dict[str, Any]:
    return public_share_to_dict(share, request, url_name='listing_public:property_view')


def update_property_public_share(share: CRMPropertyPublicShare, payload: dict) -> CRMPropertyPublicShare:
    from workspace.services.public_share_common import (
        normalize_consultant_fields_for_save,
        normalize_social_links,
        sanitize_welcome_html,
        save_share_profile_defaults,
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
    if 'show_full_address' in payload:
        share.show_full_address = bool(payload.get('show_full_address'))
    if 'show_internal_notes' in payload:
        share.show_internal_notes = bool(payload.get('show_internal_notes'))
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


def _floor_display(prop: CRMProperty) -> str:
    if prop.floor is not None and prop.total_floors:
        return f'{prop.floor} از {prop.total_floors}'
    if prop.floor is not None:
        return str(prop.floor)
    return ''


def _property_feat(prop: CRMProperty) -> Dict[str, Any]:
    return {
        'floor': _floor_display(prop),
        'build_year': str(prop.build_year) if prop.build_year else '',
        'rooms': prop.rooms or '',
    }


_CORE_AMENITY_KEYS = frozenset(spec['key'] for spec in LISTING_CORE_AMENITIES)


def _parse_amenity_token(token: str) -> tuple[str, Optional[bool]]:
    """برچسب امکان و مقدار بولین (در صورت مشخص بودن)."""
    text = str(token or '').strip()
    if not text:
        return '', None
    if ':' in text:
        label, value = text.split(':', 1)
        label, value = label.strip(), value.strip()
        if not label:
            return '', None
        parsed = parse_bool_feature(value)
        if parsed is not None:
            return label, parsed
        return label, True
    if text.endswith(' ندارد'):
        return text[:-len(' ندارد')].strip(), False
    if text.endswith(' دارد'):
        return text[:-len(' دارد')].strip(), True
    return text, True


def _parse_property_amenities_text(text: str) -> tuple[Dict[str, bool], List[Dict[str, Any]]]:
    """امکانات اصلی از متن + آیتم‌های تکمیلی غیرتکراری."""
    core_states: Dict[str, bool] = {}
    extras: List[Dict[str, Any]] = []
    if not text or not str(text).strip():
        return core_states, extras
    for token in re.split(r'[\n،,|]+', str(text).strip()):
        label, has_val = _parse_amenity_token(token)
        if not label:
            continue
        if label in _CORE_AMENITY_KEYS:
            if has_val is not None:
                core_states[label] = has_val
            elif label not in core_states:
                core_states[label] = True
            continue
        if has_val is False:
            continue
        extras.append({
            'key': label,
            'label': label,
            'value': 'دارد',
            'state': 'yes',
            'icon': _icon_for_key(label),
            'chips': [],
            'is_chip': False,
        })
    return core_states, extras


def _resolve_core_amenity_state(prop: CRMProperty, key: str, parsed_core: Dict[str, bool]) -> bool:
    """اولویت: متن امکانات، سپس چک‌باکس CRM."""
    if key in parsed_core:
        return parsed_core[key]
    bool_map = {
        'پارکینگ': prop.has_parking,
        'انباری': prop.has_storage,
        'آسانسور': prop.has_elevator,
    }
    return bool(bool_map.get(key))


def _property_feature_profile(user, prop: CRMProperty, feat: Dict[str, Any]) -> Dict[str, Any]:
    source = resolve_listing_for_property(user, prop)
    if source:
        profile = build_listing_feature_profile(source, extract_listing_features(source))
        profile['source_label'] = 'ثبت‌شده از دیوار'
        return profile

    parsed_core, extra_items = _parse_property_amenities_text(prop.amenities or '')
    core: List[Dict[str, Any]] = []
    for spec in LISTING_CORE_AMENITIES:
        key = spec['key']
        val = _resolve_core_amenity_state(prop, key, parsed_core)
        core.append({
            'key': key,
            'label': key,
            'value': 'دارد' if val else 'ندارد',
            'state': 'yes' if val else 'no',
            'icon': spec['icon'],
            'known': True,
        })
    groups = []
    if extra_items:
        groups.append({
            'id': 'amenities',
            'title': 'امکانات و توضیحات',
            'icon': 'fa-couch',
            'accent': 'emerald',
            'items': extra_items,
        })
    detail_count = sum(1 for c in core if c['known']) + len(extra_items)
    return {
        'core': core,
        'groups': groups,
        'chip_items': [],
        'has_details': detail_count > 0,
        'detail_count': detail_count,
        'raw': {},
        'source_label': 'ثبت‌شده در فایل شخصی',
    }


def _property_highlights(prop: CRMProperty) -> List[str]:
    items: List[str] = []
    parsed_core, _ = _parse_property_amenities_text(prop.amenities or '')
    for key, has_val in parsed_core.items():
        if has_val and key not in items:
            items.append(key)
    if prop.has_parking and 'پارکینگ' not in items:
        items.append('پارکینگ')
    if prop.has_storage and 'انباری' not in items:
        items.append('انباری')
    if prop.has_elevator and 'آسانسور' not in items:
        items.append('آسانسور')
    if prop.property_type:
        items.append(prop.property_type)
    if prop.amenities:
        for part in re.split(r'[،,|]\s*', prop.amenities.strip())[:4]:
            if part.strip() and part.strip() not in items:
                items.append(part.strip())
    return items[:8]


def _property_display_data(prop: CRMProperty, share: CRMPropertyPublicShare) -> dict:
    data: Dict[str, Any] = {
        'عنوان': prop.title,
        'نوع ملک': prop.property_type,
        'نوع معامله': prop.deal_mode,
        'وضعیت معامله': prop.transaction_status,
    }
    if prop.sale_price:
        data['قیمت'] = prop.sale_price
    if prop.deposit:
        data['ودیعه'] = prop.deposit
    if prop.monthly_rent:
        data['اجاره'] = prop.monthly_rent
        data['اجاره ماهانه'] = prop.monthly_rent
    if prop.area:
        data['متراژ'] = prop.area
    if prop.rooms:
        data['اتاق'] = prop.rooms
    floor = _floor_display(prop)
    if floor:
        data['طبقه'] = floor
    if prop.build_year:
        data['سال ساخت'] = prop.build_year
    if prop.city:
        data['شهر'] = prop.city
    if prop.district:
        data['منطقه'] = prop.district
    if prop.neighborhood:
        data['محله'] = prop.neighborhood
    if share.show_full_address and prop.address:
        data['آدرس'] = prop.address
    if share.show_divar_link and prop.link:
        data['لینک'] = prop.link
    if prop.amenities:
        data['امکانات'] = prop.amenities
    return data


def _listing_like(prop: CRMProperty, feat: Dict[str, Any]) -> Dict[str, Any]:
    price_per_sqm = None
    if prop.sale_price and prop.area and prop.area > 0:
        price_per_sqm = int(prop.sale_price / prop.area)
    return {
        'title': prop.title,
        'price': prop.sale_price,
        'deposit': prop.deposit,
        'rent': prop.monthly_rent,
        'area': prop.area,
        'rooms': prop.rooms,
        'neighborhood': prop.neighborhood or prop.district,
        'city': prop.city,
        'latitude': prop.latitude,
        'longitude': prop.longitude,
        'link': prop.link,
        'is_expired': False,
        'price_per_sqm': price_per_sqm,
    }


def build_public_property_context(share: CRMPropertyPublicShare, request=None) -> Dict[str, Any]:
    prop = share.property
    user = share.created_by
    feat = _property_feat(prop)
    tx = transaction_profile(prop.deal_mode or 'فروش')
    data = _property_display_data(prop, share)

    sections = format_sections_public(data, tx, show_divar_link=share.show_divar_link)
    sections.pop('سایر', None)
    section_rows = {
        name: format_field_rows(fields, data) for name, fields in sections.items()
    }

    feature_profile = scrub_public_feature_profile(_property_feature_profile(user, prop, feat))

    # امکانات فقط در بلوک امکانات؛ توضیح آزاد فقط یادداشت (در صورت اجازه)
    description_parts = []
    if share.show_internal_notes and prop.notes:
        description_parts.append(prop.notes.strip())
    if prop.amenities and not feature_profile.get('groups') and not any(
        c.get('known') for c in (feature_profile.get('core') or [])
    ):
        description_parts.append(prop.amenities.strip())
    description_text = '\n\n'.join(p for p in description_parts if p)

    sections, section_rows = prune_public_detail_sections(
        sections,
        section_rows,
        has_description=bool(description_text) or bool(prop.amenities),
        description_text=description_text,
        hide_hero_sections=True,
    )

    listing = _listing_like(prop, feat)
    finance = build_finance_summary(listing, tx, data)
    primary_price = finance.get('primary') or ''

    category_parts = [p for p in (prop.deal_mode, prop.property_type, prop.city, prop.neighborhood or prop.district) if p]

    images = deduplicate_divar_image_urls(
        [normalize_external_image_url(img) for img in (prop.images or []) if img],
    )

    meta_parts = [prop.title or 'فایل شخصی']
    if prop.area:
        meta_parts.append(f'{int(prop.area)} متر')
    if category_parts:
        meta_parts.append(' · '.join(category_parts[:2]))

    location_accuracy = {'label': 'موقعیت دقیق', 'kind': 'exact', 'radius_m': 0}
    marker_listing = SimpleNamespace(
        latitude=prop.latitude,
        longitude=prop.longitude,
        title=prop.title or '',
        area=prop.area,
        rooms=prop.rooms,
        price_per_sqm=listing.get('price_per_sqm'),
        price=prop.sale_price,
        deposit=prop.deposit,
        rent=prop.monthly_rent,
        neighborhood=prop.neighborhood or prop.district or '',
        city=prop.city or '',
        business_type='',
        token='',
        link=prop.link if share.show_divar_link else '',
        published_at=None,
        data={},
        transaction_type=prop.deal_mode or '',
    )
    listing_map_marker = build_listing_map_marker(
        marker_listing,
        tx,
        feat,
        data={},
        location_accuracy=location_accuracy,
        thumb=images[0] if images else '',
        show_divar_link=share.show_divar_link,
        public=True,
    )

    consultant = build_consultant_block(user, share, title=prop.title or 'ملک')
    welcome_plain = consultant.get('welcome_message') or ''
    if description_text and texts_are_equivalent(description_text, welcome_plain):
        consultant['has_welcome'] = False
        consultant['welcome_message'] = ''
        consultant['welcome_message_html'] = ''

    return {
        'share': share,
        'listing': listing,
        'property': prop,
        'is_personal_file': True,
        'feat': feat,
        'tx': tx,
        'sections': sections,
        'section_rows': section_rows,
        'supplementary_fields': [],
        'supplementary_groups': [],
        'feature_profile': feature_profile,
        'feature_highlights': filter_public_feature_highlights(
            feature_profile,
            _property_highlights(prop),
        ),
        'show_feature_details': public_feature_details_flag(feature_profile),
        'gallery_images': images,
        'description_text': description_text,
        'finance': finance,
        'primary_price_label': primary_price,
        'consultant': consultant,
        'category_breadcrumb': category_parts,
        'show_divar_link': share.show_divar_link and bool(prop.link),
        'meta_description': ' — '.join(meta_parts)[:300],
        'dossier_badge': 'فایل شخصی',
        'location_accuracy': location_accuracy,
        'listing_map_marker': listing_map_marker,
        'map_navigation': build_map_navigation(prop.latitude, prop.longitude),
    }


def record_property_share_view(share: CRMPropertyPublicShare) -> None:
    from django.db.models import F
    CRMPropertyPublicShare.objects.filter(pk=share.pk).update(
        view_count=F('view_count') + 1,
        last_viewed_at=timezone.now(),
    )
