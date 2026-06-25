"""عملیات CRM برای API موبایل."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.core.paginator import Paginator
from django.utils import timezone

from mobile_api.serializers import contact_to_dict
from workspace.models import Customer, CustomerActivity
from workspace.services.crm import filter_contacts
from workspace.services.crm_scope import get_agency
from workspace.services.crm_today import get_today_queue
from accounts.phone_utils import normalize_phone


def list_contacts(user, *, q: str = '', page: int = 1, page_size: int = 50) -> Tuple[List[dict], dict]:
    qs = filter_contacts(user, {'q': q})
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    items = [contact_to_dict(c) for c in page_obj.object_list]
    meta = {'page': page, 'page_size': page_size, 'total': paginator.count}
    return items, meta


def get_contact(user, contact_id: int) -> Optional[Customer]:
    return filter_contacts(user, {}).filter(pk=contact_id).first()


def create_quick_lead(user, data: Dict[str, Any]) -> Customer:
    name = (data.get('full_name') or data.get('name') or '').strip()
    phone = normalize_phone(data.get('phone') or '')
    if not name:
        raise ValueError('نام الزامی است.')
    if not phone:
        raise ValueError('شماره تلفن نامعتبر است.')
    source = (data.get('source') or 'موبایل').strip()[:30]
    valid_sources = {s for s, _ in Customer._meta.get_field('source').choices}
    if source not in valid_sources:
        source = 'موبایل' if 'موبایل' in valid_sources else 'سایر'
    customer = Customer(
        user=user,
        agency=get_agency(user),
        name=name,
        phone=phone,
        source=source,
        customer_type='سرنخ',
        status='جدید',
        priority='متوسط',
    )
    customer.save()
    CustomerActivity.objects.create(
        customer=customer,
        activity_type='یادداشت',
        title='ثبت سرنخ از موبایل',
        content=f'منبع: {source}',
    )
    return customer


def today_payload(user) -> Dict[str, Any]:
    items, stats = get_today_queue(user)
    overdue = []
    today_items = []
    for item in items:
        entry = _today_item_to_api(item)
        if item.get('urgency') == 'overdue':
            overdue.append(entry)
        else:
            today_items.append(entry)
    return {
        'date': timezone.now().date().isoformat(),
        'overdue': overdue,
        'today': today_items,
        'stats': {'total': stats.get('total', 0), 'done': 0},
    }


def _today_item_to_api(item: Dict[str, Any]) -> Dict[str, Any]:
    if item.get('kind') == 'reminder':
        contact = None
        if item.get('customer_id'):
            contact = {
                'id': item['customer_id'],
                'full_name': item.get('customer_name', ''),
                'phone': item.get('customer_phone', ''),
            }
        return {
            'type': 'reminder',
            'contact': contact,
            'reminder': {
                'id': item.get('reminder_id'),
                'title': item.get('title', ''),
                'contact_id': item.get('customer_id'),
                'due_at': item.get('due_at'),
                'done': False,
            },
        }
    return {
        'type': 'follow_up',
        'contact': {
            'id': item.get('customer_id'),
            'full_name': item.get('customer_name', ''),
            'phone': item.get('customer_phone', ''),
            'customer_type': item.get('customer_type', ''),
            'status': item.get('customer_status', ''),
        },
        'reminder': None,
    }
