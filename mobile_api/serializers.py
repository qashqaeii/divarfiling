"""سریالایزرهای dict برای API موبایل."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from mobile_api.activity_types import workspace_type_to_api
from workspace.models import CRMDeal, CRMProperty, Customer, CustomerActivity, CustomerDocument, CustomerListing, Dataset, Listing, Reminder
from workspace.services.listing_features import feature_highlights_for_listing
from workspace.services.property_images import normalize_external_image_url


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
    rooms_val: Optional[int] = None
    if lst.rooms:
        try:
            rooms_val = int(str(lst.rooms).replace('،', '').strip().split()[0])
        except (ValueError, IndexError):
            rooms_val = None
    data = lst.data or {}

    def _from_data(*keys: str) -> Optional[str]:
        for k in keys:
            v = data.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
        return None

    year_built = _from_data('سال ساخت', 'year_built', 'construction_year')
    floor = _from_data('طبقه', 'floor')
    transaction_type = 'اجاره' if (lst.rent or lst.deposit) else ('فروش' if lst.price else '')

    return {
        'token': lst.token,
        'title': lst.title or '',
        'price': lst.price,
        'deposit': lst.deposit,
        'rent': lst.rent,
        'area': int(lst.area) if lst.area else None,
        'rooms': rooms_val,
        'district': lst.neighborhood or '',
        'city': lst.city or '',
        'latitude': lst.latitude,
        'longitude': lst.longitude,
        'thumbnail_url': thumb,
        'share_link': lst.link or '',
        'advertiser_type': adv,
        'business_type': lst.business_type or '',
        'scraped_at': lst.created_at.isoformat() if lst.created_at else None,
        'dataset_id': str(lst.dataset_id) if lst.dataset_id else None,
        'price_per_sqm': _calc_price_per_sqm(lst),
        'year_built': year_built,
        'floor': floor,
        'transaction_type': transaction_type,
        'feature_highlights': feature_highlights_for_listing(lst, limit=5),
    }


def listing_detail_to_dict(lst: Listing) -> Dict[str, Any]:
    base = listing_to_dict(lst)
    data = lst.data or {}
    images = _listing_image_urls(lst)

    def _from_data(*keys: str) -> Optional[str]:
        for k in keys:
            v = data.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
        return None

    year_built = _from_data('سال ساخت', 'year_built', 'construction_year')
    floor = _from_data('طبقه', 'floor')
    total_floors = _from_data('تعداد کل طبقات ساختمان', 'total_floors')

    base.update({
        'description': lst.description or _from_data('توضیحات', 'description') or '',
        'images': images,
        'year_built': year_built,
        'floor': floor,
        'total_floors': total_floors,
        'business_type': lst.business_type or '',
        'published_at': lst.published_at.isoformat() if lst.published_at else None,
        'expires_at': lst.expires_at.isoformat() if lst.expires_at else None,
        'is_expired': lst.is_expired,
        'price_per_sqm': _calc_price_per_sqm(lst),
    })
    return base


def _calc_price_per_sqm(lst: Listing) -> Optional[int]:
    if lst.price and lst.area and lst.area > 0:
        return int(lst.price / lst.area)
    return None


def activity_to_dict(a: CustomerActivity) -> Dict[str, Any]:
    return {
        'id': a.pk,
        'activity_type': workspace_type_to_api(a.activity_type),
        'activity_type_label': a.activity_type,
        'title': a.title or '',
        'content': a.content or '',
        'token': a.token or '',
        'created_at': a.created_at.isoformat() if a.created_at else None,
    }


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
