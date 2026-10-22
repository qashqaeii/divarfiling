"""لینک عمومی اشتراک‌گذاری فایل شخصی CRM."""
from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from django.utils import timezone

from workspace.constants import LISTING_CORE_AMENITIES, PROPERTY_AMENITY_CHECKBOX_GROUPS
from workspace.models import CRMProperty, CRMPropertyPublicShare
from workspace.services.crm import resolve_listing_for_property
from workspace.services.display import (
    format_field_rows,
    transaction_profile,
)
from workspace.services.features import extract_listing_features, parse_bool_feature
from workspace.services.listing_features import (
    build_listing_feature_profile,
    emoji_for_key,
    is_scalar_feature_key,
    _icon_for_key,
)
from workspace.services.listing_map import build_listing_map_marker
from workspace.services.listing_public_share import format_sections_public
from workspace.services.property_images import deduplicate_divar_image_urls, normalize_external_image_url
from workspace.services.public_share_common import (
    apply_public_approx_privacy,
    build_consultant_block,
    build_finance_summary,
    build_map_navigation,
    build_office_map_marker,
    filter_public_feature_highlights,
    prune_public_detail_sections,
    public_feature_details_flag,
    public_share_to_dict,
    resolve_public_location_accuracy,
    scrub_public_feature_profile,
    texts_are_equivalent,
    unique_share_token,
)


def get_or_create_property_share(user, prop: CRMProperty) -> CRMPropertyPublicShare:
    from django.core.exceptions import PermissionDenied

    from workspace.services.crm_matching_access import can_create_property_public_link

    if not can_create_property_public_link(user, prop):
        raise PermissionDenied('امکان ایجاد یا دریافت لینک عمومی برای این فایل وجود ندارد.')
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
    if 'approximate_location' in payload:
        share.approximate_location = bool(payload.get('approximate_location'))
    if 'approximate_location_radius_m' in payload:
        from workspace.services.public_share_common import clamp_approx_radius_m
        share.approximate_location_radius_m = clamp_approx_radius_m(
            payload.get('approximate_location_radius_m'),
        )
    if 'show_nearby_pois' in payload:
        share.show_nearby_pois = bool(payload.get('show_nearby_pois'))
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
    from workspace.services.features import format_floor_display

    if prop.floor is None:
        return ''
    return format_floor_display(prop.floor, prop.total_floors)


def _property_feat(prop: CRMProperty) -> Dict[str, Any]:
    return {
        'floor': _floor_display(prop),
        'build_year': str(prop.build_year) if prop.build_year else '',
        'rooms': prop.rooms or '',
    }


_CORE_AMENITY_KEYS = frozenset(spec['key'] for spec in LISTING_CORE_AMENITIES)

_EXPLICIT_BOOL_VALUES = frozenset({
    'دارد', 'ندارد', 'بله', 'خیر', 'yes', 'no', 'true', 'false',
    'هست', 'نیست', 'داره', 'نداره', 'می‌باشد', 'ميباشد', 'میباشد',
})


def _parse_amenity_token(token: str) -> tuple[str, Optional[bool], str]:
    """برچسب امکان، بولین (در صورت صریح بودن)، و مقدار نمایشی واقعی."""
    text = str(token or '').strip()
    if not text:
        return '', None, ''
    if ':' in text:
        label, value = text.split(':', 1)
        label, value = label.strip(), value.strip()
        if not label:
            return '', None, ''
        if not value:
            return label, True, 'دارد'
        value_l = value.lower()
        if value_l in _EXPLICIT_BOOL_VALUES or value in _EXPLICIT_BOOL_VALUES:
            parsed = parse_bool_feature(value)
            if parsed is True:
                return label, True, 'دارد'
            if parsed is False:
                return label, False, 'ندارد'
            return label, None, value
        # تعداد / مقادیر متنی یا عددی — خود مقدار نمایش داده شود
        if is_scalar_feature_key(label):
            return label, None, value
        parsed = parse_bool_feature(value)
        if parsed is not None and value_l in ('1', '0', '۱', '۰'):
            # فقط برای امکانات بولین مثل آسانسور: ۱/۰
            if label in _CORE_AMENITY_KEYS:
                return label, parsed, 'دارد' if parsed else 'ندارد'
            return label, None, value
        if parsed is not None and value_l in _EXPLICIT_BOOL_VALUES:
            return label, parsed, 'دارد' if parsed else 'ندارد'
        return label, None, value
    if text.endswith(' ندارد'):
        return text[:-len(' ندارد')].strip(), False, 'ندارد'
    if text.endswith(' دارد'):
        return text[:-len(' دارد')].strip(), True, 'دارد'
    return text, True, 'دارد'


def _parse_property_amenities_text(text: str) -> tuple[Dict[str, bool], List[Dict[str, Any]]]:
    """امکانات اصلی از متن + آیتم‌های تکمیلی غیرتکراری با مقدار واقعی."""
    core_states: Dict[str, bool] = {}
    extras: List[Dict[str, Any]] = []
    if not text or not str(text).strip():
        return core_states, extras
    for token in re.split(r'[\n،,|]+', str(text).strip()):
        label, has_val, display = _parse_amenity_token(token)
        if not label:
            continue
        if label in _CORE_AMENITY_KEYS:
            if has_val is not None:
                core_states[label] = has_val
            elif label not in core_states:
                # مقدار غیرصریح روی امکانات اصلی — غیرصفر را دارد بگیر
                core_states[label] = True
            continue
        if has_val is False:
            extras.append({
                'key': label,
                'label': label,
                'value': 'ندارد',
                'state': 'no',
                'icon': _icon_for_key(label),
                'chips': [],
                'is_chip': False,
            })
            continue
        state = 'yes' if has_val is True else 'neutral'
        value = display or ('دارد' if has_val is True else '')
        if not value:
            continue
        extras.append({
            'key': label,
            'label': label,
            'value': value,
            'state': state,
            'icon': _icon_for_key(label),
            'chips': [],
            'is_chip': False,
        })
    return core_states, extras


def property_amenity_checkbox_choices() -> List[tuple[str, str]]:
    """لیست (value, label) برای MultipleChoiceField امکانات ملک."""
    return [
        (label, label)
        for group in PROPERTY_AMENITY_CHECKBOX_GROUPS
        for label, _icon in group['items']
    ]


def property_amenity_checkbox_labels() -> frozenset[str]:
    from workspace.constants import PROPERTY_BOOL_AMENITY_LABELS
    return PROPERTY_BOOL_AMENITY_LABELS


def property_amenity_checkbox_order() -> List[str]:
    """ترتیب پایدار برچسب‌ها مطابق گروه‌بندی فرم."""
    from workspace.constants import PROPERTY_LUXURY_AMENITY_LABELS

    ordered = [label for label, _ in property_amenity_checkbox_choices()]
    for label in PROPERTY_LUXURY_AMENITY_LABELS:
        if label not in ordered:
            ordered.append(label)
    return ordered


def split_amenities_for_checkbox_form(
    amenities_text: str,
    *,
    has_parking: bool = False,
    has_storage: bool = False,
    has_elevator: bool = False,
) -> tuple[List[str], str]:
    """
    متن امکانات + فلگ‌های اصلی → لیست تیک‌خورده + متن آزاد باقی‌مانده.
    """
    known = property_amenity_checkbox_labels()
    selected: set[str] = set()
    leftovers: List[str] = []

    if has_parking:
        selected.add('پارکینگ')
    if has_storage:
        selected.add('انباری')
    if has_elevator:
        selected.add('آسانسور')

    for token in re.split(r'[\n،,|]+', str(amenities_text or '').strip()):
        raw = token.strip()
        if not raw:
            continue
        label, has_val, _display = _parse_amenity_token(raw)
        if not label:
            leftovers.append(raw)
            continue
        if label in known:
            if has_val is False:
                selected.discard(label)
            else:
                selected.add(label)
            continue
        leftovers.append(raw)

    ordered = [label for label in property_amenity_checkbox_order() if label in selected]
    return ordered, '، '.join(leftovers)


def serialize_amenity_checkboxes(
    selected_labels: List[str] | None,
    leftover_text: str = '',
) -> str:
    """
    تیک‌ها + متن آزاد → رشته amenities سازگار با پارس پرونده.
    امکانات اصلی فقط از فلگ‌های مدل می‌آیند و در متن تکرار نمی‌شوند.
    """
    known = property_amenity_checkbox_labels()
    cores = _CORE_AMENITY_KEYS
    selected = {str(x).strip() for x in (selected_labels or []) if str(x).strip()}
    parts: List[str] = []
    for label in property_amenity_checkbox_order():
        if label in selected and label in known and label not in cores:
            parts.append(label)
    leftover = str(leftover_text or '').strip()
    if leftover:
        # جلوگیری از تکرار برچسب‌های شناخته‌شده در متن آزاد
        leftover_parts: List[str] = []
        for token in re.split(r'[\n،,|]+', leftover):
            raw = token.strip()
            if not raw:
                continue
            label, _has_val, _display = _parse_amenity_token(raw)
            if label and label in known:
                continue
            leftover_parts.append(raw)
        parts.extend(leftover_parts)
    return '، '.join(parts)


def build_property_amenity_dossier_items(
    prop: CRMProperty,
    *,
    user=None,
    listing=None,
) -> List[Dict[str, Any]]:
    """
    آیتم‌های امکانات برای باکس پرونده، نوار hero و کارت لیست —
    امکانات اصلی + متن CRM + تمام گروه‌های ویژگی آگهی لینک‌شده (در صورت وجود).
    """
    items: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _add(label: str, value: str, state: str) -> None:
        key = (label or '').strip()
        if not key or key in seen or len(key) > 48:
            return
        seen.add(key)
        display = (value or '').strip() or ('دارد' if state == 'yes' else ('ندارد' if state == 'no' else '—'))
        items.append({
            'key': key,
            'label': key,
            'value': display,
            'state': state,
            'icon': _icon_for_key(key),
            'emoji': emoji_for_key(key),
            'tip': f'{key}: {display}',
            'is_core': key in _CORE_AMENITY_KEYS,
        })

    core_states, extras = _parse_property_amenities_text(prop.amenities or '')

    for spec in LISTING_CORE_AMENITIES:
        key = spec['key']
        if key in core_states:
            has_val = core_states[key]
        else:
            has_val = {
                'پارکینگ': prop.has_parking,
                'انباری': prop.has_storage,
                'آسانسور': prop.has_elevator,
            }.get(key, False)
        _add(key, 'دارد' if has_val else 'ندارد', 'yes' if has_val else 'no')

    for extra in extras:
        label = str(extra.get('label') or '')
        if label in _CORE_AMENITY_KEYS:
            continue
        _add(
            label,
            str(extra.get('value') or ''),
            str(extra.get('state') or 'neutral'),
        )

    # ادغام ویژگی‌های تفصیلی آگهی دیوار — همه دسته‌ها و زیردسته‌ها
    source = listing
    if source is None:
        owner = user or getattr(prop, 'user', None)
        if owner is not None:
            source = resolve_listing_for_property(owner, prop)
    if source is not None:
        try:
            feat = extract_listing_features(source)
            profile = build_listing_feature_profile(source, feat)
        except Exception:
            profile = None
        if profile:
            for group in profile.get('groups') or []:
                for item in group.get('items') or []:
                    key = str(item.get('label') or item.get('key') or '').strip()
                    if not key or key in _CORE_AMENITY_KEYS:
                        continue
                    _add(
                        key,
                        str(item.get('value') or ''),
                        str(item.get('state') or 'neutral'),
                    )

    return items


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
    from workspace.services.property_features import feature_profile_groups_from_data

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
    groups = feature_profile_groups_from_data(getattr(prop, 'feature_data', None) or {})
    if extra_items:
        groups.append({
            'id': 'amenities',
            'title': 'امکانات و توضیحات',
            'icon': 'fa-couch',
            'accent': 'emerald',
            'items': extra_items,
        })
    detail_count = sum(1 for c in core if c['known']) + sum(len(g.get('items') or []) for g in groups)
    return {
        'core': core,
        'groups': groups,
        'chip_items': [],
        'has_details': detail_count > 0,
        'detail_count': detail_count,
        'raw': dict(getattr(prop, 'feature_data', None) or {}),
        'source_label': 'ثبت‌شده در فایل شخصی',
    }


def _property_highlights(prop: CRMProperty) -> List[str]:
    items: List[str] = []
    parsed_core, extras = _parse_property_amenities_text(prop.amenities or '')
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
    for key, val in (getattr(prop, 'feature_data', None) or {}).items():
        text = str(val or '').strip()
        if not text:
            continue
        chip = f'{key}: {text}'
        if chip not in items:
            items.append(chip)
    for item in extras:
        if item.get('state') == 'no':
            continue
        if item.get('state') == 'neutral':
            chip = f"{item['label']}: {item['value']}"
        else:
            chip = item['label']
        if chip and chip not in items:
            items.append(chip)
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

    location_accuracy = resolve_public_location_accuracy(
        share,
        {'label': 'موقعیت دقیق', 'kind': 'exact', 'radius_m': 0},
    )
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
    listing_map_marker, map_navigation = apply_public_approx_privacy(
        latitude=prop.latitude,
        longitude=prop.longitude,
        location_accuracy=location_accuracy,
        marker=listing_map_marker,
        seed=str(getattr(share, 'share_token', '') or prop.pk),
    )

    consultant = build_consultant_block(user, share, title=prop.title or 'ملک')
    welcome_plain = consultant.get('welcome_message') or ''
    if description_text and texts_are_equivalent(description_text, welcome_plain):
        consultant['has_welcome'] = False
        consultant['welcome_message'] = ''
        consultant['welcome_message_html'] = ''

    from workspace.mixins import get_or_create_settings
    office_map_marker = build_office_map_marker(get_or_create_settings(user))

    from workspace.services.nearby_pois import build_public_nearby_pois_context
    public_nearby_pois = build_public_nearby_pois_context(prop, share)

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
        'office_map_marker': office_map_marker,
        'office_map_navigation': (consultant.get('agency') or {}).get('map_navigation'),
        'map_navigation': map_navigation,
        'public_nearby_pois': public_nearby_pois,
    }


def record_property_share_view(share: CRMPropertyPublicShare) -> None:
    from django.db.models import F
    CRMPropertyPublicShare.objects.filter(pk=share.pk).update(
        view_count=F('view_count') + 1,
        last_viewed_at=timezone.now(),
    )
