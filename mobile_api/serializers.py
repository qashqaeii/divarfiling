"""سریالایزرهای dict برای API موبایل."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from mobile_api.activity_types import workspace_type_to_api
from workspace.models import CRMDeal, CRMProperty, Customer, CustomerActivity, CustomerListing, Dataset, Listing, Reminder


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
        'item_count': ds.row_count or ds.listings.count(),
        'created_at': ds.created_at.isoformat() if ds.created_at else None,
    }


def listing_to_dict(lst: Listing) -> Dict[str, Any]:
    thumb = ''
    images = lst.images or []
    if images:
        thumb = images[0] if isinstance(images[0], str) else str(images[0])
    adv = 'مشاور' if lst.business_type and 'مشاور' in lst.business_type else 'شخصی'
    rooms_val: Optional[int] = None
    if lst.rooms:
        try:
            rooms_val = int(str(lst.rooms).replace('،', '').strip().split()[0])
        except (ValueError, IndexError):
            rooms_val = None
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
        'scraped_at': lst.created_at.isoformat() if lst.created_at else None,
        'dataset_id': str(lst.dataset_id) if lst.dataset_id else None,
    }


def listing_detail_to_dict(lst: Listing) -> Dict[str, Any]:
    base = listing_to_dict(lst)
    data = lst.data or {}
    images: List[str] = []
    for img in (lst.images or []):
        images.append(img if isinstance(img, str) else str(img))

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


def deal_to_dict(d: CRMDeal) -> Dict[str, Any]:
    return {
        'id': d.pk,
        'title': d.title,
        'stage': d.stage,
        'amount': d.value,
        'listing_token': d.listing_token or '',
        'property_id': d.property_id,
        'updated_at': d.updated_at.isoformat() if d.updated_at else None,
    }


def property_to_dict(p: CRMProperty) -> Dict[str, Any]:
    return {
        'id': p.pk,
        'title': p.title,
        'deal_mode': p.deal_mode,
        'transaction_status': p.transaction_status,
        'city': p.city or '',
        'district': p.district or '',
        'sale_price': p.sale_price,
        'rent': p.rent,
        'deposit': p.deposit,
        'area': p.area,
        'updated_at': p.updated_at.isoformat() if p.updated_at else None,
    }


def contact_detail_to_dict(
    c: Customer,
    *,
    activities: Optional[List[CustomerActivity]] = None,
    reminders: Optional[List[Reminder]] = None,
    linked_listings: Optional[List[CustomerListing]] = None,
    deals: Optional[List[CRMDeal]] = None,
    properties: Optional[List[CRMProperty]] = None,
) -> Dict[str, Any]:
    return {
        'contact': contact_to_dict(c),
        'activities': [activity_to_dict(a) for a in (activities or [])],
        'reminders': [reminder_to_dict(r) for r in (reminders or [])],
        'linked_listings': [linked_listing_to_dict(cl) for cl in (linked_listings or [])],
        'deals': [deal_to_dict(d) for d in (deals or [])],
        'properties': [property_to_dict(p) for p in (properties or [])],
    }
