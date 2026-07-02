"""عملیات CRM برای API موبایل."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from mobile_api.activity_types import api_type_to_workspace
from mobile_api.serializers import (
    activity_to_dict,
    contact_detail_to_dict,
    contact_to_dict,
    reminder_to_dict,
)
from workspace.models import CRMDeal, CRMProperty, Customer, CustomerActivity, CustomerDocument, CustomerListing, PropertyContact, Reminder
from workspace.services.crm import filter_contacts, link_customer_listing, log_activity
from workspace.services.crm_match_notifications import is_match_eligible
from workspace.services.crm_scope import customers_qs, get_agency, properties_qs, reminders_qs
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


def contact_detail_payload(user, contact_id: int, *, request=None) -> Optional[dict]:
    c = get_contact(user, contact_id)
    if not c:
        return None
    activities = list(
        CustomerActivity.objects.filter(customer=c).order_by('-created_at')[:50]
    )
    reminders = list(
        c.reminders.filter(is_done=False).order_by('due_at')[:20]
    )
    linked = list(c.linked_listings.all()[:30])
    deals = list(CRMDeal.objects.filter(customer=c, user=user).order_by('-updated_at')[:20])
    prop_ids = PropertyContact.objects.filter(customer=c).values_list('property_id', flat=True)
    properties = list(properties_qs(user).filter(pk__in=prop_ids)[:20])
    documents = list(
        CustomerDocument.objects.filter(user=user, customer=c).order_by('-uploaded_at')[:30]
    )
    return contact_detail_to_dict(
        c,
        activities=activities,
        reminders=reminders,
        linked_listings=linked,
        deals=deals,
        properties=properties,
        documents=documents,
        request=request,
    )


def update_contact(user, contact_id: int, data: Dict[str, Any]) -> Optional[Customer]:
    c = get_contact(user, contact_id)
    if not c:
        return None
    if 'full_name' in data or 'name' in data:
        c.name = (data.get('full_name') or data.get('name') or c.name).strip()
    if 'phone' in data:
        phone = normalize_phone(data['phone'])
        if phone:
            c.phone = phone
    if 'status' in data and data['status']:
        c.status = data['status']
    if 'customer_type' in data and data['customer_type']:
        c.customer_type = data['customer_type']
    if 'priority' in data and data['priority']:
        c.priority = data['priority']
    if 'notes' in data:
        c.notes = data['notes'] or ''
    if 'property_type' in data:
        c.property_type = (data['property_type'] or '').strip()
    if 'rooms' in data:
        c.rooms = (data['rooms'] or '').strip()
    if 'areas' in data:
        c.areas = (data['areas'] or '').strip()
    for field in ('budget_min', 'budget_max', 'deposit_min', 'deposit_max', 'rent_min', 'rent_max',
                  'builder_buy_budget_min', 'builder_buy_budget_max'):
        if field in data:
            setattr(c, field, _optional_bigint(data[field]))
    if 'builder_buy_property_types' in data:
        raw = data['builder_buy_property_types']
        if isinstance(raw, list):
            c.builder_buy_property_types = ', '.join(str(x).strip() for x in raw if str(x).strip())
        else:
            c.builder_buy_property_types = (raw or '').strip()
    if 'builder_buy_types' in data:
        raw = data['builder_buy_types']
        if isinstance(raw, list):
            c.builder_buy_property_types = ', '.join(str(x).strip() for x in raw if str(x).strip())
        else:
            c.builder_buy_property_types = (raw or '').strip()
    if 'builder_buy_areas' in data:
        c.builder_buy_areas = (data['builder_buy_areas'] or '').strip()
    for field in ('builder_buy_min_area', 'builder_buy_max_area'):
        if field in data:
            setattr(c, field, _optional_int(data[field]))
    if 'budget' in data and 'budget_max' not in data:
        c.budget_max = _optional_bigint(data['budget'])
    for field in ('min_area', 'max_area'):
        if field in data:
            setattr(c, field, _optional_int(data[field]))
    c.save()
    return c


def _optional_bigint(value):
    if value is None or value == '':
        return None
    return int(value)


def _optional_int(value):
    if value is None or value == '':
        return None
    return int(value)


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


def create_activity(user, contact_id: int, data: Dict[str, Any]) -> CustomerActivity:
    c = get_contact(user, contact_id)
    if not c:
        raise ValueError('مخاطب یافت نشد.')
    api_type = data.get('activity_type') or data.get('type') or 'note'
    ws_type = api_type_to_workspace(api_type)
    if not ws_type:
        raise ValueError('نوع فعالیت نامعتبر است.')
    content = (data.get('content') or data.get('note') or '').strip()
    title = (data.get('title') or '').strip()
    if not title:
        title = ws_type
    activity = log_activity(
        c,
        ws_type,
        content=content or f'{ws_type} ثبت شد.',
        title=title,
        token=(data.get('token') or '')[:100],
    )
    if ws_type in ('تماس', 'واتساپ', 'بازدید', 'پیگیری') and c.status == 'جدید':
        c.status = 'در حال پیگیری'
        c.save(update_fields=['status', 'updated_at'])
    return activity


def create_note(user, contact_id: int, data: Dict[str, Any]) -> CustomerActivity:
    note = (data.get('content') or data.get('note') or '').strip()
    if not note:
        raise ValueError('متن یادداشت الزامی است.')
    return create_activity(user, contact_id, {
        'activity_type': 'note',
        'content': note,
        'title': (data.get('title') or 'یادداشت').strip(),
    })


def create_reminder(user, contact_id: int, data: Dict[str, Any]) -> Reminder:
    c = get_contact(user, contact_id)
    if not c:
        raise ValueError('مخاطب یافت نشد.')
    title = (data.get('title') or '').strip()
    if not title:
        raise ValueError('عنوان یادآور الزامی است.')
    due_raw = data.get('due_at') or data.get('due_date')
    due_at = parse_datetime(due_raw) if due_raw else None
    if not due_at:
        raise ValueError('زمان سررسید الزامی است.')
    if timezone.is_naive(due_at):
        due_at = timezone.make_aware(due_at, timezone.get_current_timezone())
    reminder = Reminder.objects.create(
        user=user,
        customer=c,
        title=title,
        note=(data.get('note') or '').strip(),
        due_at=due_at,
        token=(data.get('token') or '')[:100],
    )
    log_activity(c, 'یادآور', content=title, title='یادآور جدید')
    return reminder


def complete_reminder(user, reminder_id: int, *, note: str = '') -> Optional[Reminder]:
    r = reminders_qs(user).filter(pk=reminder_id, is_done=False).select_related('customer').first()
    if not r:
        return None
    r.is_done = True
    r.save(update_fields=['is_done'])
    if r.customer_id:
        content = (note or '').strip() or f'یادآور «{r.title}» انجام شد.'
        log_activity(r.customer, 'یادآور', content=content, title='انجام یادآور')
    return r


def postpone_reminder(user, reminder_id: int, *, days: int = 1) -> Optional[Reminder]:
    r = reminders_qs(user).filter(pk=reminder_id, is_done=False).first()
    if not r:
        return None
    r.due_at = r.due_at + timedelta(days=max(1, days))
    r.save(update_fields=['due_at'])
    return r


def complete_follow_up_task(user, contact_id: int, *, note: str = '') -> Optional[Customer]:
    from workspace.services.crm import complete_follow_up
    c = get_contact(user, contact_id)
    if not c:
        return None
    complete_follow_up(c, note=note)
    return c


def postpone_follow_up(user, contact_id: int, *, days: int = 1) -> Optional[Customer]:
    from workspace.services.crm import set_next_follow_up
    c = get_contact(user, contact_id)
    if not c:
        return None
    base = c.next_follow_up or timezone.now().date()
    new_date = base + timedelta(days=max(1, days))
    set_next_follow_up(c, new_date, auto_status=False)
    log_activity(c, 'پیگیری', content=f'پیگیری به {new_date.isoformat()} موکول شد.', title='تعویق پیگیری')
    return c


def link_listing_to_contact(user, contact_id: int, data: Dict[str, Any]) -> CustomerListing:
    c = get_contact(user, contact_id)
    if not c:
        raise ValueError('مخاطب یافت نشد.')
    token = (data.get('token') or '').strip()
    if not token:
        raise ValueError('شناسه آگهی الزامی است.')
    return link_customer_listing(
        c,
        token=token,
        title=(data.get('title') or '')[:500],
        price=str(data.get('price') or ''),
        area=str(data.get('area') or ''),
        link=(data.get('link') or data.get('share_link') or '')[:500],
        role=(data.get('role') or 'پیشنهادی'),
        deal_type=(data.get('deal_type') or 'سایر'),
        notes=(data.get('notes') or ''),
    )


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
    done_today = reminders_qs(user).filter(
        is_done=True,
        due_at__date=timezone.now().date(),
    ).count()
    return {
        'date': timezone.now().date().isoformat(),
        'overdue': overdue,
        'today': today_items,
        'stats': {
            'total': stats.get('total', 0),
            'done': done_today,
            'overdue': len(overdue),
        },
    }


def _today_item_to_api(item: Dict[str, Any]) -> Dict[str, Any]:
    if item.get('kind') == 'reminder':
        contact = None
        if item.get('customer_id'):
            contact = {
                'id': item['customer_id'],
                'full_name': item.get('customer_name', ''),
                'phone': item.get('customer_phone', ''),
                'customer_type': item.get('customer_type', ''),
                'status': item.get('customer_status', ''),
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
            'next_follow_up_at': item.get('due_date') or None,
        },
        'reminder': None,
    }
