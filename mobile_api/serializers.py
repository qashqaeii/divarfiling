"""سریالایزرهای dict برای API موبایل."""
from __future__ import annotations

from typing import Any, Dict, Optional

from workspace.models import Customer, Dataset, Listing, Reminder


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
        'notes': c.notes or '',
        'address': c.city or '',
        'latitude': None,
        'longitude': None,
        'next_follow_up_at': c.next_follow_up.isoformat() if c.next_follow_up else None,
        'updated_at': c.updated_at.isoformat() if c.updated_at else None,
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
        'area': int(lst.area) if lst.area else None,
        'rooms': rooms_val,
        'district': lst.neighborhood or '',
        'latitude': lst.latitude,
        'longitude': lst.longitude,
        'thumbnail_url': thumb,
        'share_link': lst.link or '',
        'advertiser_type': adv,
        'scraped_at': lst.created_at.isoformat() if lst.created_at else None,
    }


def reminder_to_dict(r: Reminder) -> Dict[str, Any]:
    return {
        'id': r.pk,
        'title': r.title,
        'contact_id': r.customer_id,
        'due_at': r.due_at.isoformat() if r.due_at else None,
        'done': r.is_done,
    }
