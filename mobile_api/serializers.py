"""سریالایزرهای dict برای API موبایل."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from mobile_api.activity_types import workspace_type_to_api
from workspace.models import (
    CRMDeal, CRMProperty, Customer, CustomerActivity, CustomerDocument,
    CustomerListing, Dataset, Listing, PropertyContact, Reminder,
)
from workspace.services.features import (
    extract_listing_features,
    parse_rooms_from_text,
    parse_rooms_value,
)
from workspace.services.listing_features import build_listing_feature_profile, feature_highlights_for_listing
from workspace.services.advertiser_signal import advertiser_signal_label, detect_advertiser_signal
from workspace.services.listing_edit import owner_phone_from_listing
from workspace.services.property_images import normalize_external_image_url

_FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
_EMPTY_DATA_VALUES = frozenset({'', '-', '—', 'nan', 'none', 'null'})


def _data_value(data: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text.lower() in _EMPTY_DATA_VALUES:
            continue
        return text
    return None


def _rooms_to_api_int(rooms: Optional[str]) -> Optional[int]:
    if not rooms:
        return None
    normalized = parse_rooms_value(rooms)
    if normalized == 'بدون اتاق':
        return 0
    if normalized.isdigit():
        return int(normalized)
    return None


def _parse_floor_from_text(text: str) -> str:
    if not text:
        return ''
    translated = text.translate(_FA_DIGITS)
    match = re.search(r'طبقه\s*(\d+)', translated)
    if match:
        return match.group(1)
    match = re.search(r'(\d+)\s*از\s*(\d+)', translated)
    if match:
        return match.group(1)
    return ''


def _non_empty_spec(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in _EMPTY_DATA_VALUES:
        return None
    return text.translate(_FA_DIGITS)


def _listing_specs(lst: Listing) -> Dict[str, Any]:
    """اتاق، طبقه، سال ساخت — با fallback از data، عنوان و توضیحات."""
    data = lst.data or {}
    feat = extract_listing_features(lst)

    rooms_raw = (
        parse_rooms_value(lst.rooms)
        or _non_empty_spec(feat.get('rooms'))
        or _data_value(data, 'اتاق', 'تعداد اتاق', 'rooms')
        or parse_rooms_from_text(lst.title or '')
        or parse_rooms_from_text(lst.description or '')
        or parse_rooms_from_text(_data_value(data, 'توضیحات', 'description') or '')
        or parse_rooms_from_text(_data_value(data, 'زیرعنوان') or '')
    )

    floor = (
        _non_empty_spec(feat.get('floor'))
        or _data_value(data, 'طبقه', 'floor')
        or _parse_floor_from_text(lst.title or '')
        or _parse_floor_from_text(lst.description or '')
        or _parse_floor_from_text(_data_value(data, 'توضیحات', 'description') or '')
        or _parse_floor_from_text(_data_value(data, 'زیرعنوان') or '')
    )
    if floor:
        floor = floor.translate(_FA_DIGITS)

    total_floors = _data_value(data, 'تعداد کل طبقات ساختمان', 'total_floors')
    if not total_floors:
        combined = ' '.join(filter(None, [
            _data_value(data, 'زیرعنوان') or '',
            lst.description or '',
        ]))
        match = re.search(r'(\d+)\s*از\s*(\d+)', combined.translate(_FA_DIGITS))
        if match:
            total_floors = match.group(2)
    if total_floors:
        total_floors = total_floors.translate(_FA_DIGITS)

    build_year = feat.get('build_year')
    year_built = (
        str(build_year) if build_year else None
    ) or _data_value(data, 'سال ساخت', 'ساخت', 'year_built', 'construction_year')

    return {
        'rooms_val': _rooms_to_api_int(rooms_raw),
        'floor': floor or None,
        'total_floors': total_floors or None,
        'year_built': year_built,
    }


_CORE_AMENITY_API_KEYS = {
    'پارکینگ': 'has_parking',
    'انباری': 'has_storage',
    'آسانسور': 'has_elevator',
}


def _listing_amenity_fields(lst: Listing) -> Dict[str, Any]:
    """وضعیت واحد و امکانات اصلی — همان منطق پلتفرم وب."""
    feat = extract_listing_features(lst)
    profile = build_listing_feature_profile(lst, base_feat=feat)
    data = lst.data or {}
    result: Dict[str, Any] = {
        'has_parking': None,
        'has_storage': None,
        'has_elevator': None,
        'unit_status': _data_value(data, 'وضعیت واحد', 'وضعیت سکونت'),
    }
    for item in profile.get('core') or []:
        api_key = _CORE_AMENITY_API_KEYS.get(str(item.get('key') or '').strip())
        if not api_key:
            continue
        state = item.get('state') or 'unknown'
        if state == 'yes':
            result[api_key] = True
        elif state == 'no':
            result[api_key] = False
    return result


def _listing_image_urls(lst: Listing) -> List[str]:
    images: List[str] = []
    for img in (lst.images or []):
        url = normalize_external_image_url(img if isinstance(img, str) else str(img))
        if url:
            images.append(url)
    if images:
        return images
    data = lst.data or {}
    for key in ('رسانه_تصاویر', 'images', 'تصاویر'):
        raw = data.get(key)
        if raw:
            return _parse_images(raw)
    return []


def _dataset_thumbnail(ds: Dataset) -> str:
    lst = (
        Listing.objects.filter(dataset=ds)
        .order_by('-created_at')
        .only('images', 'data')
        .first()
    )
    if not lst:
        return ''
    urls = _listing_image_urls(lst)
    return urls[0] if urls else ''


def user_to_dict(user) -> Dict[str, Any]:
    agency_name = ''
    if hasattr(user, 'profile'):
        agency_name = getattr(user.profile, 'company_name', '') or ''
    full_name = user.get_full_name() or user.username or ''
    return {
        'id': user.pk,
        'full_name': full_name.strip() or str(user.phone or user.username),
        'phone': user.phone or '',
        'agency_name': agency_name,
    }


def contact_to_dict(c: Customer) -> Dict[str, Any]:
    budget = c.budget_max or c.budget_min
    return {
        'id': c.pk,
        'full_name': c.name,
        'phone': c.phone or '',
        'customer_type': c.customer_type,
        'status': c.status,
        'source': c.source or '',
        'priority': c.priority,
        'budget': budget,
        'budget_min': c.budget_min,
        'budget_max': c.budget_max,
        'notes': c.notes or '',
        'address': c.city or '',
        'city': c.city or '',
        'email': getattr(c, 'email', '') or '',
        'latitude': None,
        'longitude': None,
        'next_follow_up_at': c.next_follow_up.isoformat() if c.next_follow_up else None,
        'updated_at': c.updated_at.isoformat() if c.updated_at else None,
        'created_at': c.created_at.isoformat() if c.created_at else None,
    }


def dataset_to_dict(ds: Dataset) -> Dict[str, Any]:
    source = (ds.metadata or {}).get('source', 'windows')
    if (ds.metadata or {}).get('mobile_extraction'):
        source = 'mobile'
    return {
        'id': str(ds.pk),
        'name': ds.name,
        'source': source,
        'transaction_type': ds.transaction_type or '',
        'city': ds.city or '',
        'district': ds.district or '',
        'item_count': ds.row_count if ds.row_count is not None else 0,
        'thumbnail_url': _dataset_thumbnail(ds),
        'created_at': ds.created_at.isoformat() if ds.created_at else None,
    }


def listing_to_dict(lst: Listing) -> Dict[str, Any]:
    image_urls = _listing_image_urls(lst)
    thumb = image_urls[0] if image_urls else ''
    adv = 'مشاور' if lst.business_type and 'مشاور' in lst.business_type else 'شخصی'
    signal = lst.advertiser_signal or detect_advertiser_signal(
        title=lst.title or '',
        description=lst.description or '',
        business_type=lst.business_type or '',
        data=lst.data or {},
    )
    specs = _listing_specs(lst)
    transaction_type = 'اجاره' if (lst.rent or lst.deposit) else ('فروش' if lst.price else '')

    return {
        'token': lst.token,
        'title': lst.title or '',
        'price': lst.price,
        'deposit': lst.deposit,
        'rent': lst.rent,
        'area': int(lst.area) if lst.area else None,
        'rooms': specs['rooms_val'],
        'district': lst.neighborhood or '',
        'city': lst.city or '',
        'latitude': lst.latitude,
        'longitude': lst.longitude,
        'thumbnail_url': thumb,
        'share_link': lst.link or '',
        'advertiser_type': adv,
        'advertiser_signal': signal,
        'advertiser_signal_label': advertiser_signal_label(signal),
        'business_type': lst.business_type or '',
        'scraped_at': lst.created_at.isoformat() if lst.created_at else None,
        'dataset_id': str(lst.dataset_id) if lst.dataset_id else None,
        'price_per_sqm': _calc_price_per_sqm(lst),
        'year_built': specs['year_built'],
        'floor': specs['floor'],
        'transaction_type': transaction_type,
        'feature_highlights': feature_highlights_for_listing(lst, limit=5),
        **_listing_amenity_fields(lst),
    }


def listing_detail_to_dict(lst: Listing) -> Dict[str, Any]:
    base = listing_to_dict(lst)
    data = lst.data or {}
    images = _listing_image_urls(lst)
    specs = _listing_specs(lst)

    base.update({
        'description': lst.description or _data_value(data, 'توضیحات', 'description') or '',
        'images': images,
        'year_built': specs['year_built'],
        'floor': specs['floor'],
        'total_floors': specs['total_floors'],
        'business_type': lst.business_type or '',
        'owner_phone': owner_phone_from_listing(lst),
        'published_at': lst.published_at.isoformat() if lst.published_at else None,
        'expires_at': lst.expires_at.isoformat() if lst.expires_at else None,
        'is_expired': lst.is_expired,
        'price_per_sqm': _calc_price_per_sqm(lst),
        **_listing_amenity_fields(lst),
    })
    return base


def _calc_price_per_sqm(lst: Listing) -> Optional[int]:
    if lst.price and lst.area and lst.area > 0:
        return int(lst.price / lst.area)
    return None


def activity_to_dict(a: CustomerActivity) -> Dict[str, Any]:
    data = {
        'id': a.pk,
        'activity_type': workspace_type_to_api(a.activity_type),
        'activity_type_label': a.activity_type,
        'title': a.title or '',
        'content': a.content or '',
        'token': a.token or '',
        'created_at': a.created_at.isoformat() if a.created_at else None,
    }
    customer = getattr(a, 'customer', None)
    if customer is not None:
        data['customer_id'] = customer.pk
        data['customer_name'] = customer.name or ''
    return data


def reminder_to_dict(r: Reminder) -> Dict[str, Any]:
    return {
        'id': r.pk,
        'title': r.title,
        'note': r.note or '',
        'contact_id': r.customer_id,
        'due_at': r.due_at.isoformat() if r.due_at else None,
        'done': r.is_done,
        'token': r.token or '',
    }


def linked_listing_to_dict(cl: CustomerListing) -> Dict[str, Any]:
    return {
        'id': cl.pk,
        'token': cl.token,
        'title': cl.title or '',
        'price': cl.price or '',
        'area': cl.area or '',
        'link': cl.link or '',
        'role': cl.role,
        'deal_type': cl.deal_type,
        'notes': cl.notes or '',
        'created_at': cl.created_at.isoformat() if cl.created_at else None,
    }


def document_to_dict(doc: CustomerDocument, *, request=None) -> Dict[str, Any]:
    file_url = ''
    if doc.file:
        try:
            file_url = request.build_absolute_uri(doc.file.url) if request else doc.file.url
        except Exception:
            file_url = doc.file.url or ''
    return {
        'id': doc.pk,
        'title': doc.title,
        'doc_type': doc.doc_type or '',
        'file_url': file_url,
        'uploaded_at': doc.uploaded_at.isoformat() if doc.uploaded_at else None,
    }


def deal_to_dict(d: CRMDeal, *, detailed: bool = False) -> Dict[str, Any]:
    data = {
        'id': d.pk,
        'title': d.title,
        'stage': d.stage,
        'amount': d.value,
        'listing_token': d.listing_token or '',
        'property_id': d.property_id,
        'customer_id': d.customer_id,
        'probability': d.probability,
        'commission_rate': d.commission_rate,
        'commission_amount': d.commission_amount,
        'notes': d.notes or '',
        'updated_at': d.updated_at.isoformat() if d.updated_at else None,
    }
    if detailed:
        data.update({
            'checklist': d.checklist or [],
            'lost_reason': d.lost_reason or '',
            'contract_number': d.contract_number or '',
            'contract_amount': d.contract_amount,
            'expected_close_date': d.expected_close_date.isoformat() if d.expected_close_date else None,
            'customer_name': d.customer.name if getattr(d, 'customer', None) else '',
            'property_title': d.property.title if getattr(d, 'property', None) else '',
        })
    return data


def property_to_dict(p: CRMProperty, *, detailed: bool = False) -> Dict[str, Any]:
    data = {
        'id': p.pk,
        'title': p.title,
        'deal_mode': p.deal_mode,
        'transaction_status': p.transaction_status,
        'property_type': p.property_type,
        'publish_status': p.publish_status,
        'city': p.city or '',
        'district': p.district or '',
        'neighborhood': p.neighborhood or '',
        'sale_price': p.sale_price,
        'rent': p.monthly_rent,
        'deposit': p.deposit,
        'area': p.area,
        'rooms': p.rooms or '',
        'token': p.token or '',
        'link': p.link or '',
        'created_at': p.created_at.isoformat() if p.created_at else None,
        'updated_at': p.updated_at.isoformat() if p.updated_at else None,
    }
    if detailed:
        data.update({
            'address': p.address or '',
            'floor': p.floor,
            'total_floors': p.total_floors,
            'build_year': p.build_year,
            'has_parking': p.has_parking,
            'has_storage': p.has_storage,
            'has_elevator': p.has_elevator,
            'amenities': p.amenities or '',
            'notes': p.notes or '',
            'images': p.images or [],
        })
    return data


def property_contact_to_dict(link: PropertyContact) -> Dict[str, Any]:
    customer = link.customer
    return {
        'id': link.pk,
        'customer_id': customer.pk,
        'customer_name': customer.name or '',
        'phone': customer.phone or '',
        'status': customer.status or '',
        'role': link.role or '',
        'deal_type': link.deal_type or '',
        'interest_level': link.interest_level or '',
        'is_primary': link.is_primary,
        'notes': link.notes or '',
        'created_at': link.created_at.isoformat() if link.created_at else None,
    }


def property_detail_to_dict(
    prop: CRMProperty,
    *,
    contacts: Optional[List[PropertyContact]] = None,
    activities: Optional[List[CustomerActivity]] = None,
    documents: Optional[List[CustomerDocument]] = None,
    feature_profile: Optional[Dict[str, Any]] = None,
    listing_highlights: Optional[List[str]] = None,
    can_edit: bool = True,
    mask_sensitive: bool = False,
    request=None,
) -> Dict[str, Any]:
    property_data = property_to_dict(prop, detailed=True)
    if mask_sensitive:
        property_data['address'] = ''
        property_data['notes'] = ''
        property_data['neighborhood'] = ''
    return {
        'property': property_data,
        'contacts': [] if mask_sensitive else [property_contact_to_dict(c) for c in (contacts or [])],
        'activities': [] if mask_sensitive else [activity_to_dict(a) for a in (activities or [])],
        'documents': [] if mask_sensitive else [document_to_dict(d, request=request) for d in (documents or [])],
        'feature_profile': feature_profile or {'has_details': False, 'core': [], 'groups': []},
        'listing_highlights': listing_highlights or [],
        'can_edit': can_edit,
        'mask_sensitive': mask_sensitive,
        'contact_count': 0 if mask_sensitive else len(contacts or []),
    }


def contact_detail_to_dict(
    c: Customer,
    *,
    activities: Optional[List[CustomerActivity]] = None,
    reminders: Optional[List[Reminder]] = None,
    linked_listings: Optional[List[CustomerListing]] = None,
    deals: Optional[List[CRMDeal]] = None,
    properties: Optional[List[CRMProperty]] = None,
    documents: Optional[List[CustomerDocument]] = None,
    request=None,
) -> Dict[str, Any]:
    return {
        'contact': contact_to_dict(c),
        'activities': [activity_to_dict(a) for a in (activities or [])],
        'reminders': [reminder_to_dict(r) for r in (reminders or [])],
        'linked_listings': [linked_listing_to_dict(cl) for cl in (linked_listings or [])],
        'deals': [deal_to_dict(d) for d in (deals or [])],
        'properties': [property_to_dict(p) for p in (properties or [])],
        'documents': [document_to_dict(d, request=request) for d in (documents or [])],
    }


def schedule_to_dict(s) -> Dict[str, Any]:
    return {
        'id': s.pk,
        'title': s.title,
        'is_enabled': s.is_enabled,
        'interval_hours': s.interval_hours,
        'filters': s.filters or {},
        'max_items': s.max_items,
        'next_run_at': s.next_run_at.isoformat() if s.next_run_at else None,
        'last_run_at': s.last_run_at.isoformat() if s.last_run_at else None,
        'last_status': s.last_status,
        'last_error': s.last_error or '',
        'last_dataset_id': str(s.last_dataset_id) if s.last_dataset_id else '',
        'run_count': s.run_count,
        'consecutive_failures': s.consecutive_failures,
        'primary_device_id': s.primary_device_id or '',
        'created_at': s.created_at.isoformat() if s.created_at else None,
        'updated_at': s.updated_at.isoformat() if s.updated_at else None,
    }


def run_to_dict(r) -> Dict[str, Any]:
    return {
        'id': r.pk,
        'schedule_id': r.schedule_id,
        'status': r.status,
        'trigger': r.trigger,
        'filters': r.filters_snapshot or {},
        'dataset_id': str(r.dataset_id) if r.dataset_id else '',
        'ingested_count': r.ingested_count,
        'created_count': r.created_count,
        'updated_count': r.updated_count,
        'skipped_count': r.skipped_count,
        'error': r.error or '',
        'started_at': r.started_at.isoformat() if r.started_at else None,
        'finished_at': r.finished_at.isoformat() if r.finished_at else None,
    }
