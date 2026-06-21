"""سرویس CRM — منطق کسب‌وکار."""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import jdatetime

from workspace.services.jalali_input import format_jalali_date

from django.db.models import Count, Q
from django.utils import timezone

from workspace.constants import CONVERT_TYPE_MAP, LEAD_TYPES, ROLE_COLORS
from workspace.models import (
    CRMProperty, Customer, CustomerActivity, CustomerDocument,
    CustomerListing, Listing, PropertyContact, Reminder,
)
from workspace.services.crm_scope import customers_qs, properties_qs, reminders_qs


def normalize_phone(phone: str) -> str:
    s = re.sub(r'\D', '', (phone or '').strip())
    if s.startswith('98') and len(s) >= 12:
        s = '0' + s[2:]
    return s


def log_activity(
    customer: Customer,
    activity_type: str,
    content: str = '',
    *,
    title: str = '',
    token: str = '',
    property_obj: Optional[CRMProperty] = None,
    duration_minutes: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> CustomerActivity:
    return CustomerActivity.objects.create(
        customer=customer,
        activity_type=activity_type,
        title=title,
        content=content,
        token=token,
        property=property_obj,
        duration_minutes=duration_minutes,
        metadata=metadata or {},
    )


def set_next_follow_up(
    customer: Customer,
    follow_date: date,
    *,
    auto_status: bool = True,
) -> None:
    customer.next_follow_up = follow_date
    update_fields = ['next_follow_up', 'updated_at']
    if auto_status and customer.status == 'جدید':
        customer.status = 'در حال پیگیری'
        update_fields.append('status')
    customer.save(update_fields=update_fields)


def schedule_follow_up(
    customer: Customer,
    follow_date: date,
    note: str = '',
    *,
    auto_status: bool = True,
) -> CustomerActivity:
    set_next_follow_up(customer, follow_date, auto_status=auto_status)
    jdate = format_jalali_date(follow_date)
    content = (note or '').strip() or f'پیگیری بعدی: {jdate}'
    return log_activity(
        customer,
        'پیگیری',
        content=content,
        title='ثبت پیگیری',
        metadata={'follow_up_date': follow_date.isoformat()},
    )


def complete_follow_up(customer: Customer, note: str = '') -> Optional[CustomerActivity]:
    if not customer.next_follow_up:
        return None
    old = customer.next_follow_up
    customer.next_follow_up = None
    customer.save(update_fields=['next_follow_up', 'updated_at'])
    content = (note or '').strip() or f'پیگیری {format_jalali_date(old)} انجام شد.'
    return log_activity(
        customer,
        'پیگیری',
        content=content,
        title='انجام پیگیری',
        metadata={'completed_follow_up': old.isoformat()},
    )


def log_phone_call(
    customer: Customer,
    note: str = '',
    *,
    schedule_days: Optional[int] = None,
) -> CustomerActivity:
    activity = log_activity(
        customer,
        'تماس',
        content=(note or '').strip() or 'تماس تلفنی ثبت شد.',
        title='تماس',
    )
    if schedule_days:
        schedule_follow_up(
            customer,
            timezone.now().date() + timedelta(days=max(1, int(schedule_days))),
        )
    else:
        customer.save(update_fields=['updated_at'])
    return activity


_RECURRENCE_DAYS = {'weekly': 7, 'biweekly': 14, 'monthly': 30}


def advance_recurring_reminder(reminder: Reminder) -> Optional[Reminder]:
    """پس از انجام یادآور تکرارشونده، نوبت بعدی را بساز."""
    if not reminder.recurrence:
        return None
    days = _RECURRENCE_DAYS.get(reminder.recurrence)
    if not days:
        return None
    series = reminder.series or reminder
    return Reminder.objects.create(
        user=reminder.user,
        customer=reminder.customer,
        title=reminder.title,
        note=reminder.note,
        due_at=reminder.due_at + timedelta(days=days),
        token=reminder.token,
        recurrence=reminder.recurrence,
        series=series,
    )


def sync_follow_up_from_reminder(customer: Customer, reminder: Reminder) -> None:
    if not reminder.due_at:
        return
    follow_date = reminder.due_at.date()
    if customer.next_follow_up is None or follow_date <= customer.next_follow_up:
        set_next_follow_up(customer, follow_date, auto_status=False)


def log_status_change(customer: Customer, old_status: str, new_status: str) -> None:
    if old_status == new_status:
        return
    log_activity(
        customer,
        'تغییر وضعیت',
        content=f'وضعیت از «{old_status}» به «{new_status}» تغییر کرد.',
        metadata={'old_status': old_status, 'new_status': new_status},
    )


def convert_lead(customer: Customer, new_type: str) -> Customer:
    old_type = customer.customer_type
    customer.customer_type = new_type
    customer.converted_from = customer if old_type in LEAD_TYPES else customer.converted_from
    customer.save(update_fields=['customer_type', 'converted_from', 'updated_at'])
    log_activity(
        customer,
        'تغییر وضعیت',
        content=f'تبدیل از «{old_type}» به «{new_type}»',
        metadata={'old_type': old_type, 'new_type': new_type, 'action': 'convert'},
    )
    return customer


def link_customer_property(
    customer: Customer,
    property_obj: CRMProperty,
    role: str,
    deal_type: str = 'سایر',
    *,
    interest_level: str = '',
    is_primary: bool = False,
    notes: str = '',
) -> PropertyContact:
    link, created = PropertyContact.objects.update_or_create(
        customer=customer,
        property=property_obj,
        role=role,
        defaults={
            'deal_type': deal_type,
            'interest_level': interest_level,
            'is_primary': is_primary,
            'notes': notes,
        },
    )
    action = 'پیوند جدید' if created else 'به‌روزرسانی پیوند'
    log_activity(
        customer,
        'املاک',
        content=f'{action}: {property_obj.title} — نقش {role}',
        property_obj=property_obj,
        metadata={'role': role, 'deal_type': deal_type},
    )
    return link


def link_customer_listing(
    customer: Customer,
    *,
    token: str = '',
    title: str = '',
    price: str = '',
    area: str = '',
    link: str = '',
    role: str = 'پیشنهادی',
    deal_type: str = 'سایر',
    notes: str = '',
    crm_property: Optional[CRMProperty] = None,
) -> CustomerListing:
    obj, _ = CustomerListing.objects.update_or_create(
        customer=customer,
        token=token or (crm_property.token if crm_property else ''),
        role=role,
        defaults={
            'title': title or (crm_property.title if crm_property else ''),
            'price': price,
            'area': area or (str(crm_property.area) if crm_property and crm_property.area else ''),
            'link': link or (crm_property.link if crm_property else ''),
            'deal_type': deal_type,
            'notes': notes,
            'crm_property': crm_property,
        },
    )
    log_activity(
        customer,
        'املاک',
        content=f'ملک مرتبط: {obj.title or token}',
        token=token,
        property_obj=crm_property,
        metadata={'role': role, 'deal_type': deal_type},
    )
    return obj


def property_from_listing(user, listing) -> CRMProperty:
    """ساخت ملک CRM از آگهی اسکرپ‌شده."""
    from workspace.services.features import extract_listing_features
    from workspace.services.listing_features import build_listing_feature_profile

    deal_mode = 'فروش'
    if listing.rent or listing.deposit:
        deal_mode = 'رهن و اجاره' if listing.deposit else 'اجاره'
    feat = extract_listing_features(listing)
    profile = build_listing_feature_profile(listing, feat)
    amenity_lines = []
    for group in profile.get('groups', []):
        for item in group.get('items', []):
            amenity_lines.append(f"{item['label']}: {item['value']}")
    parking_count = (listing.data or {}).get('تعداد پارکینگ')
    floor_raw = feat.get('floor') or (listing.data or {}).get('طبقه')
    floor_val = None
    if floor_raw:
        try:
            floor_val = int(re.search(r'\d+', str(floor_raw)).group())
        except (AttributeError, ValueError, TypeError):
            pass
    total_floors_raw = (listing.data or {}).get('تعداد کل طبقات ساختمان')
    total_floors = None
    if total_floors_raw:
        try:
            total_floors = int(re.search(r'\d+', str(total_floors_raw)).group())
        except (AttributeError, ValueError, TypeError):
            pass
    return CRMProperty.objects.create(
        user=user,
        title=listing.title or f'ملک {listing.token}',
        property_type='آپارتمان',
        deal_mode=deal_mode,
        address=listing.neighborhood,
        city=listing.city,
        neighborhood=listing.neighborhood,
        latitude=listing.latitude,
        longitude=listing.longitude,
        area=listing.area,
        rooms=listing.rooms or feat.get('rooms') or '',
        floor=floor_val,
        total_floors=total_floors,
        build_year=feat.get('build_year'),
        has_parking=bool(feat.get('parking')) or bool(parking_count),
        has_storage=bool(feat.get('storage')),
        has_elevator=bool(feat.get('elevator')),
        sale_price=listing.price,
        deposit=listing.deposit,
        monthly_rent=listing.rent,
        amenities='\n'.join(amenity_lines[:40]),
        images=listing.images or [],
        token=listing.token,
        link=listing.link or '',
        publish_status='منتشرشده',
    )


def get_crm_property_by_token(user, token: str) -> Optional[CRMProperty]:
    """ملک CRM متناظر با شناسه آگهی (در صورت وجود)."""
    token = str(token or '').strip()
    if not token:
        return None
    return properties_qs(user).filter(token=token).first()


def add_listing_to_personal_files(user, listing) -> tuple[CRMProperty, bool]:
    """افزودن آگهی به فایل‌های شخصی؛ در صورت تکراری بودن همان ملک برگردانده می‌شود."""
    existing = get_crm_property_by_token(user, listing.token)
    if existing:
        return existing, False
    return property_from_listing(user, listing), True


def resolve_listing_for_property(user, prop) -> Optional[Listing]:
    """یافتن آگهی منبع برای ملک CRM بر اساس token."""
    token = str(prop.token or '').strip()
    if not token:
        return None
    return (
        Listing.objects.filter(token=token, dataset__user=user)
        .select_related('dataset')
        .order_by('-published_at', '-id')
        .first()
    )


def get_dashboard_stats(user) -> Dict[str, Any]:
    today = timezone.now().date()
    customers = customers_qs(user)
    properties = properties_qs(user)

    by_type = dict(
        customers.values('customer_type').annotate(c=Count('id')).values_list('customer_type', 'c')
    )
    by_status = dict(
        customers.values('status').annotate(c=Count('id')).values_list('status', 'c')
    )

    return {
        'total_contacts': customers.count(),
        'total_properties': properties.count(),
        'owners': customers.filter(customer_type='مالک').count(),
        'buyers': customers.filter(customer_type='خریدار').count(),
        'tenants': customers.filter(customer_type='مستاجر').count(),
        'leads': customers.filter(customer_type__in=LEAD_TYPES).count(),
        'sale_files': properties.filter(deal_mode='فروش').count(),
        'rent_files': properties.filter(deal_mode__in=['رهن و اجاره', 'اجاره']).count(),
        'new_contacts': customers.filter(status='جدید').count(),
        'in_progress': customers.filter(status='در حال پیگیری').count(),
        'contracts': customers.filter(status='قرارداد').count(),
        'due_today': customers.filter(next_follow_up=today).count(),
        'overdue_followups': customers.filter(
            next_follow_up__lt=today, status__in=['جدید', 'در حال پیگیری'],
        ).count(),
        'active_reminders': reminders_qs(user).filter(is_done=False).count(),
        'by_type': by_type,
        'by_status': by_status,
        'sale_by_status': dict(
            properties.filter(deal_mode='فروش')
            .values('transaction_status').annotate(c=Count('id'))
            .values_list('transaction_status', 'c')
        ),
        'rent_by_status': dict(
            properties.filter(deal_mode__in=['رهن و اجاره', 'اجاره'])
            .values('transaction_status').annotate(c=Count('id'))
            .values_list('transaction_status', 'c')
        ),
    }


def get_pipeline_data(user, per_column: int = 10) -> List[Dict[str, Any]]:
    from workspace.constants import CRM_STATUSES

    rows = []
    for status in CRM_STATUSES:
        qs = customers_qs(user).filter(status=status)
        rows.append({
            'status': status,
            'count': qs.count(),
            'contacts': list(qs.order_by('-updated_at')[:per_column]),
        })
    return rows


def get_property_pipeline(user, params: dict | None = None, per_column: int = 50) -> List[Dict[str, Any]]:
    """کانبان املاک بر اساس transaction_status — A8."""
    from django.db.models import Count, Sum

    from workspace.constants import PROPERTY_TX_STATUSES

    filt = params.dict() if hasattr(params, 'dict') else dict(params or {})
    filt.pop('transaction_status', None)
    filt.pop('view', None)
    filt.pop('page', None)
    filt.pop('drawer', None)

    base = filter_properties(user, filt).annotate(
        contact_count=Count('contact_links', distinct=True),
    )
    rows = []
    for status in PROPERTY_TX_STATUSES:
        qs = base.filter(transaction_status=status)
        rows.append({
            'status': status,
            'count': qs.count(),
            'total_value': qs.aggregate(s=Sum('sale_price'))['s'] or 0,
            'properties': list(qs.order_by('pipeline_order', '-updated_at')[:per_column]),
        })
    return rows


def update_property_transaction_status(prop: CRMProperty, new_status: str, *, user=None) -> None:
    """تغییر وضعیت معامله ملک با ثبت لاگ برای مخاطبین مرتبط."""
    from django.db.models import Max

    from workspace.constants import PROPERTY_TX_STATUSES
    from workspace.models import PropertyContact
    from workspace.services.crm_scope import properties_qs

    if new_status not in PROPERTY_TX_STATUSES:
        raise ValueError('وضعیت نامعتبر')
    old_status = prop.transaction_status
    if old_status == new_status:
        return
    prop.transaction_status = new_status
    if user is not None:
        max_order = (
            properties_qs(user)
            .filter(transaction_status=new_status)
            .exclude(pk=prop.pk)
            .aggregate(m=Max('pipeline_order'))['m']
        ) or 0
        prop.pipeline_order = max_order + 1
    prop.save(update_fields=['transaction_status', 'pipeline_order', 'updated_at'])
    for link in PropertyContact.objects.filter(property=prop).select_related('customer'):
        log_activity(
            link.customer,
            'تغییر وضعیت',
            title=prop.title,
            content=f'وضعیت ملک: {old_status} → {new_status}',
            property_obj=prop,
            metadata={
                'property_id': prop.pk,
                'old_status': old_status,
                'new_status': new_status,
            },
        )


def reorder_property_pipeline(user, transaction_status: str, ordered_ids: list[int]) -> None:
    """به‌روزرسانی ترتیب فایل‌ها در یک ستون کانبان."""
    from workspace.constants import PROPERTY_TX_STATUSES
    from workspace.services.crm_scope import can_edit_property, properties_qs

    if transaction_status not in PROPERTY_TX_STATUSES:
        raise ValueError('وضعیت نامعتبر')
    if not ordered_ids:
        return
    unique_ids = list(dict.fromkeys(int(i) for i in ordered_ids))
    props = {
        p.pk: p
        for p in properties_qs(user).filter(
            transaction_status=transaction_status,
            pk__in=unique_ids,
        )
    }
    if len(props) != len(unique_ids):
        raise ValueError('برخی فایل‌ها یافت نشد')
    for prop in props.values():
        if not can_edit_property(user, prop):
            raise ValueError('امکان ویرایش برخی فایل‌ها را ندارید')
    for idx, pk in enumerate(unique_ids, start=1):
        prop = props[pk]
        if prop.pipeline_order != idx:
            prop.pipeline_order = idx
            prop.save(update_fields=['pipeline_order', 'updated_at'])


def get_overdue_contacts(user, limit: int = 8):
    today = timezone.now().date()
    return customers_qs(user).filter(
        next_follow_up__lt=today,
        status__in=['جدید', 'در حال پیگیری'],
    ).order_by('next_follow_up')[:limit]


def get_upcoming_reminders(user, limit: int = 8):
    return (
        Reminder.objects
        .filter(user=user, is_done=False)
        .select_related('customer')
        .order_by('due_at')[:limit]
    )


def get_recent_properties(user, limit: int = 6):
    return properties_qs(user).order_by('-updated_at')[:limit]


def get_recent_contacts(user, limit: int = 5):
    return customers_qs(user).order_by('-created_at')[:limit]


_PERSIAN_DAYS = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه']

_STATUS_CHART_COLORS = {
    'جدید': '#2563EB',
    'در حال پیگیری': '#F59E0B',
    'بازدید انجام شد': '#10B981',
    'قرارداد': '#F43F5E',
    'بایگانی': '#7C3AED',
}


def get_activity_trends(user, days: int = 7) -> Dict[str, Any]:
    today = timezone.now().date()
    start = today - timedelta(days=days - 1)
    labels, contacts, properties, contracts = [], [], [], []

    for i in range(days):
        d = start + timedelta(days=i)
        if days <= 7:
            labels.append(_PERSIAN_DAYS[d.weekday()])
        else:
            j = jdatetime.date.fromgregorian(date=d)
            labels.append(j.strftime('%m/%d'))
        contacts.append(customers_qs(user).filter(created_at__date=d).count())
        properties.append(properties_qs(user).filter(created_at__date=d).count())
        contracts.append(
            customers_qs(user).filter(status='قرارداد', updated_at__date=d).count()
        )

    return {
        'labels': labels,
        'contacts': contacts,
        'properties': properties,
        'contracts': contracts,
    }


def _trend_line_datasets(trends: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            'label': 'معاملات',
            'data': trends['contracts'],
            'borderColor': '#10B981',
            'backgroundColor': 'rgba(16, 185, 129, 0.08)',
            'fill': True,
            'tension': 0.4,
            'pointRadius': 3,
            'pointHoverRadius': 6,
        },
        {
            'label': 'املاک جدید',
            'data': trends['properties'],
            'borderColor': '#2563EB',
            'backgroundColor': 'transparent',
            'borderDash': [5, 5],
            'tension': 0.4,
            'pointRadius': 3,
        },
        {
            'label': 'مخاطبین جدید',
            'data': trends['contacts'],
            'borderColor': '#7C3AED',
            'backgroundColor': 'transparent',
            'tension': 0.4,
            'pointRadius': 3,
        },
    ]


def _trend_range_payload(user, days: int) -> Dict[str, Any]:
    trends = get_activity_trends(user, days)
    return {
        'labels': trends['labels'],
        'datasets': _trend_line_datasets(trends),
    }


def get_communication_stats(user) -> List[Dict[str, Any]]:
    activity_map = {
        'تماس': 'phone',
        'ایمیل': 'email',
        'واتساپ': 'whatsapp',
        'پیامک': 'sms',
    }
    counts = {v: 0 for v in activity_map.values()}
    for row in (
        CustomerActivity.objects
        .filter(customer__user=user, activity_type__in=activity_map)
        .values('activity_type')
        .annotate(c=Count('id'))
    ):
        key = activity_map.get(row['activity_type'])
        if key:
            counts[key] = row['c']

    customers = customers_qs(user)
    if not any(counts.values()):
        counts['phone'] = customers.exclude(phone='').count()
        counts['email'] = customers.exclude(email='').count()

    total = sum(counts.values()) or 1
    return [
        {'key': 'phone', 'label': 'تلفن', 'icon': 'fa-phone', 'count': counts['phone'], 'pct': round(counts['phone'] / total * 100)},
        {'key': 'email', 'label': 'ایمیل', 'icon': 'fa-envelope', 'count': counts['email'], 'pct': round(counts['email'] / total * 100)},
        {'key': 'whatsapp', 'label': 'واتساپ', 'icon': 'fa-brands fa-whatsapp', 'count': counts['whatsapp'], 'pct': round(counts['whatsapp'] / total * 100)},
        {'key': 'sms', 'label': 'پیامک', 'icon': 'fa-comment-sms', 'count': counts['sms'], 'pct': round(counts['sms'] / total * 100)},
    ]


def build_dashboard_charts(user) -> List[Dict[str, Any]]:
    stats = get_dashboard_stats(user)
    trends_7 = _trend_range_payload(user, 7)

    from workspace.constants import CRM_STATUSES
    status_labels = list(CRM_STATUSES)
    status_values = [stats['by_status'].get(s, 0) for s in status_labels]
    status_colors = [_STATUS_CHART_COLORS.get(s, '#64748B') for s in status_labels]

    return [
        {
            'type': 'line',
            'id': 'activity',
            'labels': trends_7['labels'],
            'datasets': trends_7['datasets'],
            'ranges': {
                '7': trends_7,
                '30': _trend_range_payload(user, 30),
            },
        },
        {
            'type': 'doughnut',
            'id': 'status',
            'labels': status_labels,
            'datasets': [{
                'data': status_values,
                'backgroundColor': status_colors,
                'borderWidth': 0,
                'hoverOffset': 6,
            }],
        },
    ]


def global_search(user, query: str, limit: int = 12) -> Dict[str, list]:
    q = query.strip()
    if not q:
        return {'contacts': [], 'properties': []}

    contacts = customers_qs(user).filter(
        Q(name__icontains=q) | Q(phone__icontains=q) | Q(phone_alt__icontains=q)
        | Q(email__icontains=q) | Q(tags__icontains=q) | Q(company_name__icontains=q)
    )[:limit]

    properties = properties_qs(user).filter(
        Q(title__icontains=q) | Q(address__icontains=q) | Q(neighborhood__icontains=q)
        | Q(city__icontains=q) | Q(token__icontains=q)
    )[:limit]

    return {'contacts': list(contacts), 'properties': list(properties)}


def filter_contacts(user, params: dict):
    qs = customers_qs(user)
    q = params.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(phone__icontains=q) | Q(phone_alt__icontains=q)
            | Q(email__icontains=q) | Q(national_id__icontains=q) | Q(tags__icontains=q)
            | Q(notes__icontains=q) | Q(areas__icontains=q) | Q(company_name__icontains=q)
        )
    for field in ('status', 'customer_type', 'priority', 'source'):
        val = params.get(field, '').strip()
        if val:
            qs = qs.filter(**{field: val})
    tags = params.get('tags', '').strip()
    if tags:
        for tag in tags.split(','):
            tag = tag.strip()
            if tag:
                qs = qs.filter(tags__icontains=tag)
    due = params.get('due', '')
    today = timezone.now().date()
    if due == 'today':
        qs = qs.filter(next_follow_up=today)
    elif due == 'overdue':
        qs = qs.filter(next_follow_up__lt=today, status__in=['جدید', 'در حال پیگیری'])
    elif due == 'none':
        qs = qs.filter(next_follow_up__isnull=True)
    sort = params.get('sort', '-updated_at')
    allowed = {'name', '-name', 'updated_at', '-updated_at', 'next_follow_up', '-next_follow_up', 'created_at', '-created_at'}
    if sort in allowed:
        qs = qs.order_by(sort)
    else:
        qs = qs.order_by('-updated_at')
    return qs


def filter_properties(user, params: dict):
    qs = properties_qs(user)
    q = params.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(address__icontains=q) | Q(neighborhood__icontains=q)
            | Q(city__icontains=q) | Q(token__icontains=q)
        )
    for field in ('deal_mode', 'transaction_status', 'property_type', 'publish_status'):
        val = params.get(field, '').strip()
        if val:
            qs = qs.filter(**{field: val})
    city = params.get('city', '').strip()
    if city:
        qs = qs.filter(city__icontains=city)
    sort = params.get('sort', '-updated_at')
    allowed = {'title', '-title', 'updated_at', '-updated_at', 'sale_price', '-sale_price', 'area', '-area'}
    if sort in allowed:
        qs = qs.order_by(sort)
    else:
        qs = qs.order_by('-updated_at')
    return qs


def recent_activities(user, limit: int = 15):
    return (
        CustomerActivity.objects
        .filter(customer__user=user)
        .select_related('customer', 'property')[:limit]
    )


def role_color(role: str) -> tuple:
    return ROLE_COLORS.get(role, ('#f1f5f9', '#475569'))


def get_convert_options(customer_type: str) -> List[str]:
    return CONVERT_TYPE_MAP.get(customer_type, [])


def customers_linked_to_token(user, token: str):
    if not token:
        return CustomerListing.objects.none()
    return (
        CustomerListing.objects
        .filter(customer__user=user, token=token)
        .select_related('customer')
        .order_by('-updated_at')
    )


def guess_deal_type_from_listing(listing) -> str:
    if listing.rent and listing.deposit:
        return 'رهن و اجاره'
    if listing.rent:
        return 'اجاره'
    if listing.price:
        return 'فروش'
    return 'سایر'


def link_listing_to_customer(customer, listing, tx, *, role='پیشنهادی', deal_type=''):
    from workspace.services.formatting import format_toman

    deal_type = deal_type or guess_deal_type_from_listing(listing)
    price_parts = []
    if tx.get('show_price') and listing.price:
        price_parts.append(format_toman(listing.price))
    if tx.get('show_deposit') and listing.deposit:
        price_parts.append(f'رهن {format_toman(listing.deposit)}')
    if tx.get('show_rent') and listing.rent:
        price_parts.append(f'اجاره {format_toman(listing.rent)}')
    price_str = ' · '.join(price_parts)
    area_str = f'{listing.area} متر' if listing.area else ''

    return link_customer_listing(
        customer,
        token=listing.token,
        title=listing.title or '',
        price=price_str,
        area=area_str,
        link=listing.link or '',
        role=role,
        deal_type=deal_type,
    )


def update_customer_status(customer: Customer, new_status: str) -> None:
    """تغییر وضعیت مخاطب با ثبت لاگ."""
    from workspace.constants import CRM_STATUSES

    if new_status not in CRM_STATUSES:
        raise ValueError('وضعیت نامعتبر')
    old_status = customer.status
    if old_status == new_status:
        return
    customer.status = new_status
    customer.save(update_fields=['status', 'updated_at'])
    log_status_change(customer, old_status, new_status)


def build_suggestions_whatsapp_text(customer, matches: List[Dict[str, Any]]) -> str:
    """متن واتساپ برای لیست پیشنهاد ملک."""
    from workspace.services.formatting import format_toman

    lines = [f'سلام {customer.name}،', '', 'چند ملک مناسب برای شما:', '']
    for i, m in enumerate(matches, 1):
        lines.append(f'{i}. {m.get("title") or "ملک"}')
        if m.get('price_label'):
            lines.append(f'   💰 {m["price_label"]}')
        if m.get('area'):
            area_val = m['area']
            try:
                area_txt = f'{int(float(area_val))} متر'
            except (TypeError, ValueError):
                area_txt = str(area_val)
            lines.append(f'   📐 {area_txt}')
        hood = m.get('neighborhood') or m.get('city')
        if hood:
            lines.append(f'   📍 {hood}')
        if m.get('link'):
            lines.append(f'   🔗 {m["link"]}')
        lines.append('')
    lines.append('در صورت تمایل برای بازدید هماهنگ می‌کنیم.')
    lines.append('با احترام')
    return '\n'.join(lines)


def apply_property_suggestions(
    customer: Customer,
    user,
    matches: List[Dict[str, Any]],
    *,
    note: str = '',
) -> str:
    """ثبت پیشنهادها در activity و پیوند ملک‌ها."""
    if not matches:
        return ''
    titles = []
    for m in matches:
        title = m.get('title') or 'ملک'
        titles.append(title)
        if m.get('source') == 'crm' and m.get('property_id'):
            prop = CRMProperty.objects.filter(pk=m['property_id'], user=user).first()
            if prop:
                link_customer_property(
                    customer, prop, 'پیشنهادی',
                    deal_type='خرید' if prop.deal_mode == 'فروش' else 'رهن و اجاره',
                    interest_level='متوسط',
                    notes='پیشنهاد خودکار',
                )
        elif m.get('source') == 'divar' and m.get('token'):
            listing = Listing.objects.filter(
                token=m['token'], dataset__user=user,
            ).select_related('dataset').first()
            if listing:
                from workspace.services.display import transaction_profile

                tx = transaction_profile(listing.dataset.transaction_type)
                link_listing_to_customer(customer, listing, tx, role='پیشنهادی')

    content = note.strip() or f'پیشنهاد {len(matches)} ملک: ' + '، '.join(titles[:5])
    log_activity(
        customer,
        'املاک',
        content=content,
        title='ارسال پیشنهاد ملک',
        metadata={'suggestion_count': len(matches), 'titles': titles},
    )
    return build_suggestions_whatsapp_text(customer, matches)


def build_customer_whatsapp_text(customer, listing=None) -> str:
    from workspace.services.formatting import format_toman

    lines = [f'سلام {customer.name}']
    if listing:
        if listing.title:
            lines.append(listing.title)
        if getattr(listing, 'area', None):
            lines.append(f'متراژ: {listing.area} متر')
        if getattr(listing, 'price', None):
            lines.append(f'قیمت: {format_toman(listing.price)}')
        if getattr(listing, 'link', None):
            lines.append(listing.link)
    elif customer.linked_listings.exists():
        l = customer.linked_listings.first()
        if l.title:
            lines.append(l.title)
        if l.price:
            lines.append(f'قیمت: {l.price}')
        if l.link:
            lines.append(l.link)
    lines.append('با احترام')
    return '\n'.join(lines)


def export_customers_queryset(user, params: Optional[dict] = None):
    params = params or {}
    return filter_contacts(user, params)


def _excel_safe_value(value: Any) -> Any:
    if isinstance(value, datetime) and timezone.is_aware(value):
        return timezone.localtime(value).replace(tzinfo=None)
    return value


def customers_to_export_rows(customers) -> List[Dict[str, Any]]:
    rows = []
    for c in customers:
        rows.append({
            'نام': c.name,
            'تلفن': c.phone,
            'تلفن دوم': c.phone_alt,
            'ایمیل': c.email,
            'نوع': c.customer_type,
            'وضعیت': c.status,
            'اولویت': c.priority,
            'منبع': c.source,
            'شهر': c.city,
            'منطقه': c.district,
            'بودجه از': c.budget_min,
            'بودجه تا': c.budget_max,
            'ودیعه از': c.deposit_min,
            'ودیعه تا': c.deposit_max,
            'اجاره از': c.rent_min,
            'اجاره تا': c.rent_max,
            'متراژ از': c.min_area,
            'متراژ تا': c.max_area,
            'محله‌ها': c.areas,
            'برچسب‌ها': c.tags,
            'پیگیری بعدی': _excel_safe_value(c.next_follow_up),
            'یادداشت': c.notes,
            'تاریخ ثبت': _excel_safe_value(c.created_at),
        })
    return rows


def export_customers_excel_response(user, params: Optional[dict] = None):
    import io

    import pandas as pd
    from django.http import HttpResponse

    qs = export_customers_queryset(user, params)
    rows = customers_to_export_rows(qs)
    if not rows:
        rows = [{'نام': ''}]

    df = pd.DataFrame(rows)
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            tz = getattr(df[col].dt, 'tz', None)
            if tz is not None:
                df[col] = df[col].dt.tz_localize(None)
        elif df[col].dtype == object:
            df[col] = df[col].map(_excel_safe_value)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine='openpyxl')
    buf.seek(0)
    filename = f'crm_contacts_{datetime.now().strftime("%Y%m%d")}.xlsx'
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _bool_fa(value: Any) -> str:
    return 'بله' if value else 'خیر'


def export_properties_queryset(user, params: Optional[dict] = None):
    params = params or {}
    export_params = {k: v for k, v in params.items() if k != 'format'}
    return filter_properties(user, export_params).annotate(
        contact_count=Count('contact_links', distinct=True),
    )


def properties_to_export_rows(properties) -> List[Dict[str, Any]]:
    from workspace.services.formatting import format_toman

    rows = []
    for p in properties:
        price_parts = []
        if p.sale_price:
            price_parts.append(f'فروش {format_toman(p.sale_price)}')
        if p.deposit:
            price_parts.append(f'رهن {format_toman(p.deposit)}')
        if p.monthly_rent:
            price_parts.append(f'اجاره {format_toman(p.monthly_rent)}')
        rows.append({
            'شناسه': p.pk,
            'عنوان': p.title,
            'نوع ملک': p.property_type,
            'نوع معامله': p.deal_mode,
            'وضعیت معامله': p.transaction_status,
            'وضعیت انتشار': p.publish_status,
            'شهر': p.city,
            'منطقه': p.district,
            'محله': p.neighborhood,
            'آدرس': p.address,
            'متراژ (متر)': p.area,
            'اتاق': p.rooms,
            'طبقه': p.floor,
            'تعداد طبقات': p.total_floors,
            'سال ساخت': p.build_year,
            'پارکینگ': _bool_fa(p.has_parking),
            'انباری': _bool_fa(p.has_storage),
            'آسانسور': _bool_fa(p.has_elevator),
            'قیمت فروش (تومان)': p.sale_price,
            'رهن (تومان)': p.deposit,
            'اجاره ماهانه (تومان)': p.monthly_rent,
            'قیمت (نمایش)': ' · '.join(price_parts),
            'امکانات': p.amenities,
            'شناسه آگهی': p.token,
            'لینک': p.link,
            'عرض جغرافیایی': p.latitude,
            'طول جغرافیایی': p.longitude,
            'تعداد مخاطب': getattr(p, 'contact_count', 0),
            'یادداشت': p.notes,
            'تاریخ ثبت': format_jalali_date(p.created_at),
            'آخرین بروزرسانی': format_jalali_date(p.updated_at),
        })
    return rows


def _properties_export_rows(user, params: Optional[dict] = None) -> List[Dict[str, Any]]:
    qs = export_properties_queryset(user, params)
    rows = properties_to_export_rows(qs)
    if not rows:
        rows = [{'عنوان': ''}]
    return rows


def export_properties_excel_response(user, params: Optional[dict] = None):
    import io

    import pandas as pd
    from django.http import HttpResponse

    rows = _properties_export_rows(user, params)
    df = pd.DataFrame(rows)
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(_excel_safe_value)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine='openpyxl')
    buf.seek(0)
    filename = f'crm_properties_{datetime.now().strftime("%Y%m%d")}.xlsx'
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def export_properties_csv_response(user, params: Optional[dict] = None):
    import csv
    import io

    from django.http import HttpResponse

    rows = _properties_export_rows(user, params)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    filename = f'crm_properties_{datetime.now().strftime("%Y%m%d")}.csv'
    response = HttpResponse(
        buf.getvalue().encode('utf-8-sig'),
        content_type='text/csv; charset=utf-8',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
