"""سرویس املاک CRM برای API موبایل."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.utils import timezone

from mobile_api.serializers import property_detail_to_dict, property_to_dict
from workspace.constants import CRM_PROPERTIES, PROPERTY_DEAL_MODES, PROPERTY_TX_STATUSES
from workspace.models import CRMProperty, CRMPropertyFolderItem, Customer, CustomerActivity, CustomerDocument, PropertyContact
from workspace.services.crm import filter_properties, link_customer_property, resolve_listing_for_property, update_property_transaction_status, upsert_property_owner, upsert_property_tenant
from workspace.services.crm_property_share import build_property_share_context
from workspace.services.crm_scope import can_edit_property, customers_qs, get_agency, properties_qs, property_for_user
from workspace.services.features import extract_listing_features
from workspace.services.listing_features import build_listing_feature_profile


def list_properties_paginated(
    user,
    *,
    page: int = 1,
    page_size: int = 20,
    query: Optional[Dict[str, Any]] = None,
    request=None,
) -> Tuple[List[dict], dict]:
    params = {k: str(v) for k, v in (query or {}).items() if v is not None and str(v).strip()}
    qs = filter_properties(user, params).prefetch_related(
        Prefetch(
            'folder_items',
            queryset=CRMPropertyFolderItem.objects.select_related('folder'),
        ),
    )
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    items = [property_to_dict(p, request=request) for p in page_obj.object_list]
    meta = {'page': page, 'page_size': page_size, 'total': paginator.count}
    return items, meta


def get_property_detail(user, property_id: int, *, request=None) -> Optional[dict]:
    prop = properties_qs(user).filter(pk=property_id).first()
    if not prop:
        return None

    share_ctx = build_property_share_context(user, prop)
    contacts = list(
        prop.contact_links.select_related('customer').all()
    ) if not share_ctx.mask_sensitive else []
    activities = list(
        CustomerActivity.objects.filter(property=prop)
        .select_related('customer')
        .order_by('-created_at')[:30]
    ) if not share_ctx.mask_sensitive else []
    documents = list(
        CustomerDocument.objects.filter(user=user, property=prop).order_by('-uploaded_at')
    ) if not share_ctx.mask_sensitive else []

    feature_profile = {'has_details': False, 'core': [], 'groups': []}
    listing_highlights: List[str] = []
    source_listing = resolve_listing_for_property(user, prop)
    if source_listing:
        feat = extract_listing_features(source_listing)
        feature_profile = build_listing_feature_profile(source_listing, feat)
        listing_highlights = feat.get('highlights') or []

    payload = property_detail_to_dict(
        prop,
        contacts=contacts,
        activities=activities,
        documents=documents,
        feature_profile=feature_profile,
        listing_highlights=listing_highlights,
        can_edit=can_edit_property(user, prop),
        mask_sensitive=share_ctx.mask_sensitive,
        request=request,
    )
    if source_listing:
        _enrich_property_dict_from_listing(payload['property'], source_listing)
    # تضمین URL مطلق تصاویر برای کلاینت موبایل
    from mobile_api.serializers import _property_image_urls
    normalized = _property_image_urls(payload['property'].get('images') or [], request=request)
    payload['property']['images'] = normalized
    payload['property']['thumbnail_url'] = normalized[0] if normalized else ''
    from workspace.services.crm_property_folders import list_property_folders, serialize_folder
    payload['available_folders'] = [serialize_folder(f) for f in list_property_folders(user)]
    from workspace.services.crm_scope import is_property_owner
    if is_property_owner(user, prop) and prop.deleted_at is None:
        from workspace.services.property_public_share import (
            get_or_create_property_share,
            property_public_share_to_dict,
        )
        share = get_or_create_property_share(user, prop)
        payload['public_share'] = property_public_share_to_dict(share, request)
    return payload


def _parse_int(value) -> Optional[int]:
    if value in (None, ''):
        return None
    return int(value)


def _parse_float(value) -> Optional[float]:
    if value in (None, ''):
        return None
    return float(value)


def _merge_mobile_feature_data(prop: CRMProperty, incoming: Optional[dict]) -> None:
    from workspace.services.property_features import (
        CRM_FEATURE_FORM_KEYS,
        FIELDS,
        normalize_feature_date_value,
        profile_keys,
        resolve_feature_profile,
        _normalize_toggle,
    )

    if not isinstance(incoming, dict):
        return
    profile_id = resolve_feature_profile(prop.deal_mode, prop.property_type)
    active_keys = profile_keys(profile_id)
    out = {k: v for k, v in (prop.feature_data or {}).items() if k not in active_keys}
    for key, val in incoming.items():
        feat_key = str(key or '').strip()
        if feat_key not in CRM_FEATURE_FORM_KEYS:
            continue
        text = str(val or '').strip()
        meta = FIELDS.get(feat_key) or {}
        if meta.get('widget') == 'date' and text:
            text = normalize_feature_date_value(text)
        elif meta.get('widget') == 'toggle' and text:
            text = _normalize_toggle(text)
        if text:
            out[feat_key] = text
        elif feat_key in active_keys:
            out.pop(feat_key, None)
    prop.feature_data = out


def _apply_mobile_extended_fields(prop: CRMProperty, data: Dict[str, Any]) -> None:
    from workspace.constants import PROPERTY_PUBLISH_STATUSES

    if 'publish_status' in data and data.get('publish_status') is not None:
        ps = str(data.get('publish_status') or '').strip()
        if ps in PROPERTY_PUBLISH_STATUSES:
            prop.publish_status = ps[:30]
    if 'latitude' in data:
        prop.latitude = _parse_float(data.get('latitude'))
    if 'longitude' in data:
        prop.longitude = _parse_float(data.get('longitude'))
    if 'amenities' in data and data.get('amenities') is not None:
        prop.amenities = str(data.get('amenities') or '')
    if 'business_type' in data and data.get('business_type') is not None:
        prop.business_type = str(data.get('business_type') or '')[:50]
    if 'phone' in data and data.get('phone') is not None:
        prop.phone = str(data.get('phone') or '')[:20]
    elif 'owner_phone' in data and data.get('owner_phone') is not None:
        prop.phone = str(data.get('owner_phone') or '')[:20]
    if 'owner_name' in data and data.get('owner_name') is not None:
        prop.owner_name = str(data.get('owner_name') or '')[:200]
    if 'feature_data' in data:
        _merge_mobile_feature_data(prop, data.get('feature_data'))
    if 'vacancy_date' in data:
        from workspace.services.property_features import normalize_feature_date_value
        fd = dict(prop.feature_data or {})
        raw_vacancy = str(data.get('vacancy_date') or '').strip()
        if raw_vacancy:
            fd['تاریخ تخلیه'] = normalize_feature_date_value(raw_vacancy)
        else:
            fd.pop('تاریخ تخلیه', None)
        prop.feature_data = fd
    if 'images' in data and data.get('images') is not None:
        prop.images = list(data.get('images') or [])
    for bool_field in ('has_parking', 'has_storage', 'has_elevator', 'is_vacant'):
        if bool_field in data and data.get(bool_field) is not None:
            setattr(prop, bool_field, bool(data.get(bool_field)))
    if data.get('is_vacant'):
        prop.tenant_name = ''
        prop.tenant_phone = ''
    else:
        if 'tenant_name' in data and data.get('tenant_name') is not None:
            prop.tenant_name = str(data.get('tenant_name') or '')[:200]
        if 'tenant_phone' in data and data.get('tenant_phone') is not None:
            prop.tenant_phone = str(data.get('tenant_phone') or '')[:20]


def _apply_mobile_property_overrides(prop: CRMProperty, data: Dict[str, Any], *, title_required: bool = True) -> None:
    """اعمال فیلدهای ارسالی موبایل روی ملک ساخته‌شده از آگهی."""
    if (data.get('title') or '').strip():
        prop.title = str(data['title']).strip()[:200]
    elif title_required and not prop.title:
        raise ValueError('عنوان ملک الزامی است.')

    simple_fields = {
        'deal_mode': 'deal_mode',
        'transaction_status': 'transaction_status',
        'property_type': 'property_type',
        'city': 'city',
        'district': 'district',
        'neighborhood': 'neighborhood',
        'address': 'address',
        'rooms': 'rooms',
        'notes': 'notes',
        'link': 'link',
    }
    for api_key, model_field in simple_fields.items():
        if api_key in data and data.get(api_key) not in (None, ''):
            setattr(prop, model_field, str(data.get(api_key) or '')[:500])

    if 'area' in data:
        prop.area = _parse_float(data.get('area'))
    if 'sale_price' in data:
        prop.sale_price = _parse_int(data.get('sale_price'))
    if 'deposit' in data:
        prop.deposit = _parse_int(data.get('deposit'))
    if 'rent' in data or 'monthly_rent' in data:
        prop.monthly_rent = _parse_int(data.get('rent', data.get('monthly_rent')))
    if 'floor' in data:
        prop.floor = _parse_int(data.get('floor'))
    if 'total_floors' in data:
        prop.total_floors = _parse_int(data.get('total_floors'))
    if 'build_year' in data:
        prop.build_year = _parse_int(data.get('build_year'))
    for bool_field in ('has_parking', 'has_storage', 'has_elevator'):
        if bool_field in data:
            setattr(prop, bool_field, bool(data.get(bool_field)))
    if data.get('images'):
        prop.images = list(data.get('images') or [])
    _apply_mobile_extended_fields(prop, data)
    prop.save()


def _enrich_property_dict_from_listing(prop_dict: Dict[str, Any], listing) -> None:
    """تکمیل نمایش ملک از آگهی منبع — بدون تغییر دیتابیس."""
    from workspace.services.features import extract_listing_features

    feat = extract_listing_features(listing)
    parking_count = (listing.data or {}).get('تعداد پارکینگ')
    if not prop_dict.get('has_parking') and (feat.get('parking') or parking_count):
        prop_dict['has_parking'] = True
    if not prop_dict.get('has_storage') and feat.get('storage'):
        prop_dict['has_storage'] = True
    if not prop_dict.get('has_elevator') and feat.get('elevator'):
        prop_dict['has_elevator'] = True
    if not prop_dict.get('rooms') and listing.rooms:
        prop_dict['rooms'] = listing.rooms
    if prop_dict.get('floor') in (None, '') and feat.get('floor'):
        try:
            import re
            prop_dict['floor'] = int(re.search(r'\d+', str(feat.get('floor'))).group())
        except (AttributeError, ValueError, TypeError):
            pass
    if prop_dict.get('build_year') in (None, '') and feat.get('build_year'):
        prop_dict['build_year'] = feat.get('build_year')
    if not prop_dict.get('neighborhood') and listing.neighborhood:
        prop_dict['neighborhood'] = listing.neighborhood
    if not prop_dict.get('images') and listing.images:
        from mobile_api.serializers import _property_image_urls, _listing_image_urls
        # ترجیح تصاویر نرمال‌شده آگهی منبع
        prop_dict['images'] = _listing_image_urls(listing) or _property_image_urls(listing.images)
        if prop_dict['images']:
            prop_dict['thumbnail_url'] = prop_dict['images'][0]


def create_property_from_mobile(user, data: Dict[str, Any]) -> CRMProperty:
    title = (data.get('title') or '').strip()
    if not title:
        raise ValueError('عنوان ملک الزامی است.')

    token = (data.get('token') or '').strip()
    if token:
        from workspace.models import Listing
        from workspace.services.crm import add_listing_to_personal_files

        listing = (
            Listing.objects.filter(token=token, dataset__user=user)
            .order_by('-published_at', '-id')
            .first()
        )
        if listing:
            prop, _created = add_listing_to_personal_files(user, listing)
            _apply_mobile_property_overrides(prop, data, title_required=False)
            return prop

    deal_mode = (data.get('deal_mode') or 'فروش').strip()
    if deal_mode not in PROPERTY_DEAL_MODES:
        deal_mode = 'فروش'

    property_type = (data.get('property_type') or 'آپارتمان').strip()
    if property_type not in CRM_PROPERTIES:
        property_type = 'آپارتمان'

    tx_status = (data.get('transaction_status') or 'فعال').strip()
    if tx_status not in PROPERTY_TX_STATUSES:
        tx_status = 'فعال'

    prop = CRMProperty(
        user=user,
        agency=get_agency(user),
        title=title,
        property_type=property_type,
        deal_mode=deal_mode,
        transaction_status=tx_status,
        city=(data.get('city') or '')[:100],
        district=(data.get('district') or '')[:100],
        neighborhood=(data.get('neighborhood') or '')[:200],
        address=(data.get('address') or ''),
        area=_parse_float(data.get('area')),
        rooms=(data.get('rooms') or '')[:20],
        floor=_parse_int(data.get('floor')),
        total_floors=_parse_int(data.get('total_floors')),
        build_year=_parse_int(data.get('build_year')),
        sale_price=_parse_int(data.get('sale_price')),
        deposit=_parse_int(data.get('deposit')),
        monthly_rent=_parse_int(data.get('rent') if 'rent' in data else data.get('monthly_rent')),
        token=(data.get('token') or '')[:100],
        link=(data.get('link') or '')[:500],
        notes=(data.get('notes') or ''),
        images=list(data.get('images') or []),
        phone=(data.get('phone') or data.get('owner_phone') or '')[:20],
        owner_name=(data.get('owner_name') or '')[:200],
        business_type=(data.get('business_type') or '')[:50],
        amenities=(data.get('amenities') or ''),
        latitude=_parse_float(data.get('latitude')),
        longitude=_parse_float(data.get('longitude')),
    )
    for bool_field in ('has_parking', 'has_storage', 'has_elevator', 'is_vacant'):
        if bool_field in data:
            setattr(prop, bool_field, bool(data.get(bool_field)))
    if data.get('tenant_name') is not None:
        prop.tenant_name = (data.get('tenant_name') or '')[:200]
    if data.get('tenant_phone') is not None:
        prop.tenant_phone = (data.get('tenant_phone') or '')[:20]
    _apply_mobile_extended_fields(prop, data)
    prop.save()

    if prop.phone or prop.owner_name:
        upsert_property_owner(
            user,
            phone=prop.phone,
            name=prop.owner_name,
            crm_property=prop,
            source='موبایل',
        )
    upsert_property_tenant(
        user,
        phone=prop.tenant_phone,
        name=prop.tenant_name,
        crm_property=prop,
        source='موبایل',
    )

    contact_id = data.get('contact_id') or data.get('customer_id')
    if contact_id:
        from workspace.services.crm_scope import customers_qs
        customer = customers_qs(user).filter(pk=int(contact_id)).first()
        if customer:
            PropertyContact.objects.get_or_create(
                customer=customer,
                property=prop,
                role=(data.get('role') or 'مالک'),
                defaults={'deal_type': 'فروش'},
            )
    return prop


def update_property_from_mobile(user, property_id: int, data: Dict[str, Any]) -> Optional[CRMProperty]:
    prop = property_for_user(user, property_id)
    if not prop:
        return None

    simple_fields = {
        'title': 'title',
        'deal_mode': 'deal_mode',
        'transaction_status': 'transaction_status',
        'property_type': 'property_type',
        'city': 'city',
        'district': 'district',
        'neighborhood': 'neighborhood',
        'address': 'address',
        'rooms': 'rooms',
        'token': 'token',
        'link': 'link',
        'notes': 'notes',
        'amenities': 'amenities',
        'phone': 'phone',
        'owner_name': 'owner_name',
        'business_type': 'business_type',
    }
    for api_key, model_field in simple_fields.items():
        if api_key not in data or data.get(api_key) is None:
            continue
        setattr(prop, model_field, data.get(api_key) or '')
    if 'owner_phone' in data and data.get('owner_phone') is not None and 'phone' not in data:
        prop.phone = (data.get('owner_phone') or '')[:20]

    if 'area' in data and data.get('area') is not None:
        prop.area = _parse_float(data.get('area'))
    if 'sale_price' in data and data.get('sale_price') is not None:
        prop.sale_price = _parse_int(data.get('sale_price'))
    if 'deposit' in data and data.get('deposit') is not None:
        prop.deposit = _parse_int(data.get('deposit'))
    if 'rent' in data or 'monthly_rent' in data:
        rent_val = data.get('rent', data.get('monthly_rent'))
        if rent_val is not None:
            prop.monthly_rent = _parse_int(rent_val)
    if 'floor' in data and data.get('floor') is not None:
        prop.floor = _parse_int(data.get('floor'))
    if 'build_year' in data and data.get('build_year') is not None:
        prop.build_year = _parse_int(data.get('build_year'))
    for bool_field in ('has_parking', 'has_storage', 'has_elevator', 'is_vacant'):
        if bool_field in data and data.get(bool_field) is not None:
            setattr(prop, bool_field, bool(data.get(bool_field)))
    if 'total_floors' in data and data.get('total_floors') is not None:
        prop.total_floors = _parse_int(data.get('total_floors'))
    if 'publish_status' in data:
        prop.publish_status = (data.get('publish_status') or prop.publish_status)[:30]
    if 'tenant_name' in data and data.get('tenant_name') is not None:
        prop.tenant_name = (data.get('tenant_name') or '')[:200]
    if 'tenant_phone' in data and data.get('tenant_phone') is not None:
        prop.tenant_phone = (data.get('tenant_phone') or '')[:20]
    if 'vacancy_date' in data:
        from workspace.services.property_features import normalize_feature_date_value
        fd = dict(prop.feature_data or {})
        raw_vacancy = str(data.get('vacancy_date') or '').strip()
        if raw_vacancy:
            fd['تاریخ تخلیه'] = normalize_feature_date_value(raw_vacancy)
        else:
            fd.pop('تاریخ تخلیه', None)
        prop.feature_data = fd

    if 'feature_data' in data:
        _merge_mobile_feature_data(prop, data.get('feature_data'))
    if 'images' in data and data.get('images') is not None:
        prop.images = list(data.get('images') or [])
    old_lat, old_lng = prop.latitude, prop.longitude
    if 'latitude' in data:
        prop.latitude = _parse_float(data.get('latitude'))
    if 'longitude' in data:
        prop.longitude = _parse_float(data.get('longitude'))
    if ('latitude' in data or 'longitude' in data) and (
        prop.latitude != old_lat or prop.longitude != old_lng
    ):
        if prop.nearby_pois:
            prop.nearby_pois = {}

    prop.save()
    if prop.phone or prop.owner_name:
        upsert_property_owner(
            user,
            phone=prop.phone,
            name=prop.owner_name,
            crm_property=prop,
            source='موبایل',
        )
    upsert_property_tenant(
        user,
        phone=prop.tenant_phone,
        name=prop.tenant_name,
        crm_property=prop,
        source='موبایل',
    )
    return prop


def link_property_contact(user, property_id: int, data: Dict[str, Any]) -> PropertyContact:
    prop = property_for_user(user, property_id)
    if not prop:
        raise ValueError('ملک یافت نشد.')
    if not can_edit_property(user, prop):
        raise ValueError('امکان ویرایش این ملک را ندارید.')

    customer = _resolve_property_link_customer(user, data)

    role = (data.get('role') or 'مالک').strip()
    return link_customer_property(
        customer,
        prop,
        role,
        (data.get('deal_type') or 'سایر').strip(),
        interest_level=(data.get('interest_level') or '').strip(),
        is_primary=bool(data.get('is_primary', role == 'مالک')),
        notes=(data.get('notes') or '').strip(),
    )


def _resolve_property_link_customer(user, data: Dict[str, Any]):
    from accounts.phone_utils import normalize_phone
    from workspace.services.crm import customers_qs, find_customer_by_phone
    from mobile_api.services.crm_service import create_quick_lead

    customer_id = data.get('customer_id') or data.get('contact_id')
    if customer_id:
        customer = customers_qs(user).filter(pk=int(customer_id)).first()
        if not customer:
            raise ValueError('مخاطب یافت نشد.')
        return customer

    name = (data.get('full_name') or data.get('name') or '').strip()
    phone = normalize_phone(data.get('phone') or '')
    if not name:
        raise ValueError('نام مالک الزامی است.')
    if not phone:
        raise ValueError('شماره تلفن مالک نامعتبر است.')

    existing = find_customer_by_phone(user, phone)
    if existing:
        return existing

    return create_quick_lead(user, {'full_name': name, 'phone': phone, 'source': 'موبایل'})


def change_property_status(user, property_id: int, status: str) -> Optional[CRMProperty]:
    prop = property_for_user(user, property_id)
    if not prop:
        return None
    update_property_transaction_status(prop, status, user=user)
    return prop


def soft_delete_property(user, property_id: int) -> bool:
    prop = property_for_user(user, property_id)
    if not prop:
        return False
    prop.deleted_at = timezone.now()
    prop.save(update_fields=['deleted_at', 'updated_at'])
    return True


def get_property_public_share(user, property_id: int, request=None) -> Optional[dict]:
    from workspace.services.access import has_active_bot_license
    if not has_active_bot_license(user):
        return None
    from workspace.services.crm_scope import is_property_owner, property_for_user
    prop = property_for_user(user, property_id)
    if not prop or not is_property_owner(user, prop) or prop.deleted_at is not None:
        return None
    from workspace.services.property_public_share import (
        get_or_create_property_share,
        property_public_share_to_dict,
    )
    share = get_or_create_property_share(user, prop)
    return property_public_share_to_dict(share, request)


def update_property_public_share(
    user, property_id: int, payload: dict, request=None,
) -> Optional[dict]:
    from workspace.services.access import has_active_bot_license
    if not has_active_bot_license(user):
        return None
    from workspace.services.crm_scope import is_property_owner, property_for_user
    prop = property_for_user(user, property_id)
    if not prop or not is_property_owner(user, prop) or prop.deleted_at is not None:
        return None
    from workspace.services.property_public_share import (
        get_or_create_property_share,
        property_public_share_to_dict,
        update_property_public_share as _update_share,
    )
    share = get_or_create_property_share(user, prop)
    _update_share(share, payload)
    return property_public_share_to_dict(share, request)


def update_property_location_from_mobile(user, property_id: int, data: Dict[str, Any]) -> Optional[dict]:
    """ذخیره مختصات ملک از نقشه — هم‌تراز CRMPropertyLocationUpdateView."""
    from workspace.services.listing_map import parse_map_coordinates
    from workspace.services.public_share_common import build_map_navigation

    prop = property_for_user(user, property_id)
    if not prop or not can_edit_property(user, prop):
        return None

    lat, lng, error = parse_map_coordinates(data.get('latitude'), data.get('longitude'))
    if error:
        raise ValueError(error)

    prop.latitude = lat
    prop.longitude = lng
    update_fields = ['latitude', 'longitude', 'updated_at']
    if prop.nearby_pois:
        prop.nearby_pois = {}
        update_fields.append('nearby_pois')
    prop.save(update_fields=update_fields)
    return {
        'latitude': lat,
        'longitude': lng,
        'map_navigation': build_map_navigation(lat, lng),
        'property': property_to_dict(prop, detailed=True),
    }


def fetch_property_nearby_pois_from_mobile(
    user,
    property_id: int,
    *,
    force_refresh: bool = False,
) -> dict:
    """دریافت و ذخیره امکانات اطراف — هم‌تراز CRMPropertyNearbyPoisView."""
    from workspace.services.nearby_pois import NearbyPoiError, fetch_and_save_nearby_pois
    from workspace.services.property_public_share import build_property_share_context

    prop = property_for_user(user, property_id)
    if not prop:
        raise ValueError('ملک یافت نشد.')

    share_ctx = build_property_share_context(user, prop)
    if share_ctx.mask_sensitive:
        raise PermissionError('دسترسی ندارید.')

    try:
        return fetch_and_save_nearby_pois(prop, user, force_refresh=force_refresh)
    except NearbyPoiError as exc:
        raise ValueError(exc.message) from exc


def upload_property_image(user, property_id: int, uploaded_file, *, request=None) -> dict:
    """آپلود تصویر ملک — هم‌تراز CRMPropertyImagesView در وب."""
    from django.core.files.uploadedfile import UploadedFile
    from workspace.services.property_images import MAX_PROPERTY_IMAGES, store_property_image

    if not isinstance(uploaded_file, UploadedFile):
        raise ValueError('فایلی انتخاب نشده است.')
    prop = property_for_user(user, property_id)
    if not prop:
        raise ValueError('ملک یافت نشد.')
    if not can_edit_property(user, prop):
        raise ValueError('دسترسی ندارید.')
    images = list(prop.images or [])
    if len(images) >= MAX_PROPERTY_IMAGES:
        raise ValueError(f'حداکثر {MAX_PROPERTY_IMAGES} تصویر مجاز است.')
    url = store_property_image(user, prop, uploaded_file)
    images.append(url)
    prop.images = images
    prop.save(update_fields=['images', 'updated_at'])
    return {'url': url, 'images': images}
