"""سرویس CRM — منطق کسب‌وکار."""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import jdatetime

from workspace.services.jalali_input import format_jalali_date, to_persian_digits

from django.db.models import Count, Q
from django.utils import timezone

from workspace.constants import CONVERT_TYPE_MAP, LEAD_TYPES, ROLE_COLORS
from workspace.models import (
    CRMProperty, Customer, CustomerActivity, CustomerDocument,
    CustomerListing, Listing, PropertyContact, PropertyMatchAlert, Reminder,
)
from workspace.services.crm_scope import customers_qs, get_agency, properties_qs, reminders_qs


def normalize_phone(phone: str) -> str:
    """نرمال‌سازی شماره — ارقام فارسی/عربی و پیش‌شماره ایران."""
    if not phone:
        return ''
    s = str(phone).strip().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))
    s = re.sub(r'\D', '', s)
    if s.startswith('98') and len(s) >= 12:
        s = '0' + s[2:]
    elif s.startswith('9') and len(s) == 10:
        s = '0' + s
    return s


def find_customer_by_phone(user, phone: str) -> Optional[Customer]:
    """یافتن مخاطب با شماره نرمال‌شده در اسکوپ کاربر/آژانس."""
    key = normalize_phone(phone)
    if not key:
        return None
    for customer in customers_qs(user).filter(Q(phone__gt='') | Q(phone_alt__gt='')).only(
        'id', 'phone', 'phone_alt', 'name', 'customer_type', 'user_id',
    ):
        if normalize_phone(customer.phone) == key or normalize_phone(customer.phone_alt) == key:
            return customer
    return None


def primary_owner_contact(
    *,
    listing: Optional[Listing] = None,
    crm_property: Optional[CRMProperty] = None,
) -> Optional[Customer]:
    """مخاطب پیوندخورده با نقش مالک (اولویت: فایل شخصی، سپس آگهی)."""
    if crm_property is not None:
        link = (
            PropertyContact.objects
            .filter(property=crm_property, role='مالک')
            .select_related('customer')
            .order_by('-is_primary', '-updated_at')
            .first()
        )
        if link:
            return link.customer
    token = ''
    if listing is not None:
        token = str(listing.token or '').strip()
    elif crm_property is not None:
        token = str(crm_property.token or '').strip()
    if token:
        link = (
            CustomerListing.objects
            .filter(token=token, role='مالک')
            .select_related('customer')
            .order_by('-updated_at')
            .first()
        )
        if link:
            return link.customer
    return None


def _resolve_owner_customer(
    user,
    *,
    phone_key: str,
    name_raw: str,
    listing: Optional[Listing],
    crm_property: Optional[CRMProperty],
    source: str,
) -> Customer:
    """
    یافتن یا ساخت مخاطب مالک.
    اگر این ملک از قبل مالک داشته باشد و شماره متعلق به کس دیگری نباشد،
    همان مخاطب به‌روز می‌شود (نه مخاطب جدید).
    """
    by_phone = find_customer_by_phone(user, phone_key)
    current_owner = primary_owner_contact(listing=listing, crm_property=crm_property)

    if by_phone is not None:
        customer = by_phone
    elif current_owner is not None:
        # ویرایش همان مالک ملک — شماره عوض شده یا قبلاً match نشده
        customer = current_owner
    else:
        customer = Customer.objects.create(
            user=user,
            agency=get_agency(user),
            name=name_raw or f'مالک {phone_key[-4:]}',
            phone=phone_key,
            customer_type='مالک',
            status='جدید',
            priority='متوسط',
            source=source if source in (
                'دیوار', 'معرف', 'ورود به املاک', 'تماس ورودی',
                'اینستاگرام', 'سایت', 'تلگرام', 'موبایل', 'سایر',
            ) else 'سایر',
        )
        log_activity(
            customer,
            'یادداشت',
            content='ثبت خودکار به‌عنوان مالک ملک',
            title='ثبت مالک',
            token=(listing.token if listing else '') or (crm_property.token if crm_property else ''),
            property_obj=crm_property,
        )
        return customer

    update_fields = ['updated_at']
    if name_raw and customer.name != name_raw:
        customer.name = name_raw
        update_fields.append('name')
    current_phone = normalize_phone(customer.phone)
    if current_phone != phone_key:
        # اگر شماره جدید مالِ مخاطب دیگری نیست، روی همین مالک بنویس
        if by_phone is None or by_phone.pk == customer.pk:
            customer.phone = phone_key
            update_fields.append('phone')
    elif not current_phone:
        customer.phone = phone_key
        update_fields.append('phone')
    if customer.customer_type not in ('مالک', 'فروشنده', 'موجر'):
        customer.customer_type = 'مالک'
        update_fields.append('customer_type')
    if len(update_fields) > 1:
        customer.save(update_fields=update_fields)
    return customer


def upsert_property_owner(
    user,
    *,
    phone: str = '',
    name: str = '',
    listing: Optional[Listing] = None,
    crm_property: Optional[CRMProperty] = None,
    source: str = 'سایر',
) -> Optional[Customer]:
    """
    ذخیره شماره/نام مالک روی آگهی و/یا فایل شخصی،
    ساخت یا یافتن مخاطب، و پیوند با نقش «مالک».
    ویرایش مجدد همان ملک مخاطب تکراری نمی‌سازد.
    """
    from django.db import transaction as db_transaction
    from workspace.services.listing_edit import apply_owner_fields

    phone_raw = (phone or '').strip()
    name_raw = (name or '').strip()
    phone_key = normalize_phone(phone_raw)

    if listing is None and crm_property is not None and crm_property.token:
        listing = resolve_listing_for_property(user, crm_property)
    if crm_property is None and listing is not None:
        crm_property = get_crm_property_by_token(user, listing.token)

    with db_transaction.atomic():
        if listing is not None:
            # همیشه نسخه نرمال‌شده را در data نگه دار تا match پایدار بماند
            apply_owner_fields(listing, phone=phone_key or phone_raw, name=name_raw)
            listing.save(update_fields=['data'])

        if crm_property is not None:
            crm_property.phone = phone_key or phone_raw
            crm_property.owner_name = name_raw
            crm_property.save(update_fields=['phone', 'owner_name', 'updated_at'])

        if not phone_key:
            return None

        customer = _resolve_owner_customer(
            user,
            phone_key=phone_key,
            name_raw=name_raw,
            listing=listing,
            crm_property=crm_property,
            source=source,
        )

        deal_type = 'سایر'
        if listing is not None:
            deal_type = guess_deal_type_from_listing(listing)
        elif crm_property is not None and crm_property.deal_mode:
            deal_type = crm_property.deal_mode

        if crm_property is not None:
            # فقط یک مالک primary روی ملک
            PropertyContact.objects.filter(
                property=crm_property, role='مالک',
            ).exclude(customer=customer).delete()
            existing_pc = PropertyContact.objects.filter(
                customer=customer, property=crm_property, role='مالک',
            ).first()
            if existing_pc is None:
                link_customer_property(
                    customer,
                    crm_property,
                    role='مالک',
                    deal_type=deal_type,
                    is_primary=True,
                )
            else:
                pc_updates = []
                if not existing_pc.is_primary:
                    existing_pc.is_primary = True
                    pc_updates.append('is_primary')
                if deal_type and existing_pc.deal_type != deal_type:
                    existing_pc.deal_type = deal_type
                    pc_updates.append('deal_type')
                if pc_updates:
                    existing_pc.save(update_fields=[*pc_updates, 'updated_at'])

        if listing is not None and listing.token:
            from workspace.services.formatting import format_toman

            price_parts = []
            if listing.price:
                price_parts.append(format_toman(listing.price))
            if listing.deposit:
                price_parts.append(f'رهن {format_toman(listing.deposit)}')
            if listing.rent:
                price_parts.append(f'اجاره {format_toman(listing.rent)}')
            # مالک‌های قبلی همین آگهی با نقش مالک را به مخاطب فعلی منتقل/پاک کن
            CustomerListing.objects.filter(
                token=listing.token, role='مالک',
            ).exclude(customer=customer).delete()
            existing_cl = CustomerListing.objects.filter(
                customer=customer, token=listing.token, role='مالک',
            ).first()
            if existing_cl is None:
                link_customer_listing(
                    customer,
                    token=listing.token,
                    title=listing.title or '',
                    price=' · '.join(price_parts),
                    area=f'{listing.area} متر' if listing.area else '',
                    link=listing.link or '',
                    role='مالک',
                    deal_type=deal_type,
                    crm_property=crm_property,
                )
            elif crm_property is not None and existing_cl.crm_property_id != crm_property.pk:
                existing_cl.crm_property = crm_property
                existing_cl.save(update_fields=['crm_property', 'updated_at'])

    return customer


def primary_tenant_contact(crm_property: CRMProperty) -> Optional[Customer]:
    """مخاطب پیوندخورده با نقش مستاجر روی ملک."""
    link = (
        PropertyContact.objects
        .filter(property=crm_property, role='مستاجر')
        .select_related('customer')
        .order_by('-is_primary', '-updated_at')
        .first()
    )
    return link.customer if link else None


def _resolve_tenant_customer(
    user,
    *,
    phone_key: str,
    name_raw: str,
    crm_property: CRMProperty,
    source: str,
) -> Customer:
    by_phone = find_customer_by_phone(user, phone_key)
    current_tenant = primary_tenant_contact(crm_property)

    if by_phone is not None:
        customer = by_phone
    elif current_tenant is not None:
        customer = current_tenant
    else:
        customer = Customer.objects.create(
            user=user,
            agency=get_agency(user),
            name=name_raw or f'مستاجر {phone_key[-4:]}',
            phone=phone_key,
            customer_type='مستاجر',
            status='جدید',
            priority='متوسط',
            source=source if source in (
                'دیوار', 'معرف', 'ورود به املاک', 'تماس ورودی',
                'اینستاگرام', 'سایت', 'تلگرام', 'موبایل', 'سایر',
            ) else 'سایر',
        )
        log_activity(
            customer,
            'یادداشت',
            content='ثبت خودکار به‌عنوان مستاجر فعلی ملک',
            title='ثبت مستاجر',
            token=crm_property.token or '',
            property_obj=crm_property,
        )
        return customer

    update_fields = ['updated_at']
    if name_raw and customer.name != name_raw:
        customer.name = name_raw
        update_fields.append('name')
    current_phone = normalize_phone(customer.phone)
    if current_phone != phone_key:
        if by_phone is None or by_phone.pk == customer.pk:
            customer.phone = phone_key
            update_fields.append('phone')
    elif not current_phone:
        customer.phone = phone_key
        update_fields.append('phone')
    if customer.customer_type not in ('مستاجر', 'متقاضی اجاره'):
        customer.customer_type = 'مستاجر'
        update_fields.append('customer_type')
    if len(update_fields) > 1:
        customer.save(update_fields=update_fields)
    return customer


def upsert_property_tenant(
    user,
    *,
    phone: str = '',
    name: str = '',
    crm_property: Optional[CRMProperty] = None,
    source: str = 'سایر',
) -> Optional[Customer]:
    """
    ذخیره شماره/نام مستاجر فعلی روی فایل شخصی،
    ساخت یا یافتن مخاطب، و پیوند با نقش «مستاجر».
    """
    from django.db import transaction as db_transaction

    if crm_property is None:
        return None

    phone_raw = (phone or '').strip()
    name_raw = (name or '').strip()
    phone_key = normalize_phone(phone_raw)

    with db_transaction.atomic():
        crm_property.tenant_phone = phone_key or phone_raw
        crm_property.tenant_name = name_raw
        crm_property.save(update_fields=['tenant_phone', 'tenant_name', 'updated_at'])

        if crm_property.is_vacant:
            PropertyContact.objects.filter(
                property=crm_property, role='مستاجر',
            ).delete()
            return None

        if not phone_key:
            return None

        customer = _resolve_tenant_customer(
            user,
            phone_key=phone_key,
            name_raw=name_raw,
            crm_property=crm_property,
            source=source,
        )
        deal_type = crm_property.deal_mode or 'سایر'

        PropertyContact.objects.filter(
            property=crm_property, role='مستاجر',
        ).exclude(customer=customer).delete()
        existing_pc = PropertyContact.objects.filter(
            customer=customer, property=crm_property, role='مستاجر',
        ).first()
        if existing_pc is None:
            link_customer_property(
                customer,
                crm_property,
                role='مستاجر',
                deal_type=deal_type,
                is_primary=True,
                notes='مستاجر فعلی ساکن در ملک',
            )
        else:
            pc_updates = []
            if not existing_pc.is_primary:
                existing_pc.is_primary = True
                pc_updates.append('is_primary')
            if deal_type and existing_pc.deal_type != deal_type:
                existing_pc.deal_type = deal_type
                pc_updates.append('deal_type')
            if pc_updates:
                existing_pc.save(update_fields=[*pc_updates, 'updated_at'])

    return customer


def _resolve_tenant_customer_for_listing(
    user,
    *,
    phone_key: str,
    name_raw: str,
    listing,
    source: str,
) -> Customer:
    """یافتن/ساخت مخاطب مستاجر برای آگهی فایلینگ."""
    by_phone = find_customer_by_phone(user, phone_key)
    existing_link = (
        CustomerListing.objects.filter(
            customer__user=user,
            token=listing.token,
            role='مستاجر',
        )
        .select_related('customer')
        .order_by('-updated_at')
        .first()
    )
    current_tenant = existing_link.customer if existing_link else None

    if by_phone is not None:
        customer = by_phone
    elif current_tenant is not None:
        customer = current_tenant
    else:
        customer = Customer.objects.create(
            user=user,
            agency=get_agency(user),
            name=name_raw or f'مستاجر {phone_key[-4:]}',
            phone=phone_key,
            customer_type='مستاجر',
            status='جدید',
            priority='متوسط',
            source=source if source in (
                'دیوار', 'معرف', 'ورود به املاک', 'تماس ورودی',
                'اینستاگرام', 'سایت', 'تلگرام', 'موبایل', 'سایر',
            ) else 'سایر',
        )
        log_activity(
            customer,
            'یادداشت',
            content='ثبت خودکار به‌عنوان مستاجر فعلی آگهی',
            title='ثبت مستاجر',
            token=listing.token or '',
        )
        return customer

    update_fields = ['updated_at']
    if name_raw and customer.name != name_raw:
        customer.name = name_raw
        update_fields.append('name')
    current_phone = normalize_phone(customer.phone)
    if current_phone != phone_key:
        if by_phone is None or by_phone.pk == customer.pk:
            customer.phone = phone_key
            update_fields.append('phone')
    elif not current_phone:
        customer.phone = phone_key
        update_fields.append('phone')
    if customer.customer_type not in ('مستاجر', 'متقاضی اجاره'):
        customer.customer_type = 'مستاجر'
        update_fields.append('customer_type')
    if len(update_fields) > 1:
        customer.save(update_fields=update_fields)
    return customer


def upsert_listing_tenant(
    user,
    *,
    phone: str = '',
    name: str = '',
    listing: Optional[Listing] = None,
    is_vacant: bool = False,
    source: str = 'دیوار',
) -> Optional[Customer]:
    """
    ذخیره مستاجر روی آگهی فایلینگ و پیوند با مخاطب CRM (نقش «مستاجر»).
    """
    from django.db import transaction as db_transaction
    from workspace.services.formatting import format_toman

    if listing is None or not listing.token:
        return None

    phone_raw = (phone or '').strip()
    name_raw = (name or '').strip()
    phone_key = normalize_phone(phone_raw)
    crm_property = get_crm_property_by_token(user, listing.token)

    with db_transaction.atomic():
        if is_vacant or not phone_key:
            CustomerListing.objects.filter(
                customer__user=user,
                token=listing.token,
                role='مستاجر',
            ).delete()
            if crm_property is not None:
                crm_property.tenant_phone = ''
                crm_property.tenant_name = ''
                crm_property.save(update_fields=['tenant_phone', 'tenant_name', 'updated_at'])
                PropertyContact.objects.filter(
                    property=crm_property, role='مستاجر',
                ).delete()
            return None

        customer = _resolve_tenant_customer_for_listing(
            user,
            phone_key=phone_key,
            name_raw=name_raw,
            listing=listing,
            source=source,
        )
        deal_type = guess_deal_type_from_listing(listing)
        price_parts = []
        if listing.price:
            price_parts.append(format_toman(listing.price))
        if listing.deposit:
            price_parts.append(f'رهن {format_toman(listing.deposit)}')
        if listing.rent:
            price_parts.append(f'اجاره {format_toman(listing.rent)}')

        CustomerListing.objects.filter(
            customer__user=user,
            token=listing.token,
            role='مستاجر',
        ).exclude(customer=customer).delete()
        existing_cl = CustomerListing.objects.filter(
            customer=customer,
            token=listing.token,
            role='مستاجر',
        ).first()
        if existing_cl is None:
            link_customer_listing(
                customer,
                token=listing.token,
                title=listing.title or '',
                price=' · '.join(price_parts),
                area=f'{listing.area} متر' if listing.area else '',
                link=listing.link or '',
                role='مستاجر',
                deal_type=deal_type,
                notes='مستاجر فعلی ساکن در ملک',
                crm_property=crm_property,
            )
        elif crm_property is not None and existing_cl.crm_property_id != crm_property.pk:
            existing_cl.crm_property = crm_property
            existing_cl.save(update_fields=['crm_property', 'updated_at'])

        if crm_property is not None:
            upsert_property_tenant(
                user,
                phone=phone_key,
                name=name_raw,
                crm_property=crm_property,
                source=source,
            )

    return customer


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


def _property_follow_up_customer(user, prop: CRMProperty) -> Optional[Customer]:
    customer = primary_owner_contact(crm_property=prop)
    if customer:
        return customer
    phone = (prop.phone or '').strip()
    if phone:
        return upsert_property_owner(
            user,
            phone=phone,
            name=(prop.owner_name or '').strip() or 'مالک',
            crm_property=prop,
            source='سایر',
        )
    link = (
        prop.contact_links.select_related('customer')
        .order_by('-is_primary', '-updated_at')
        .first()
    )
    return link.customer if link else None


def set_property_next_follow_up(prop: CRMProperty, follow_date: date) -> None:
    prop.next_follow_up = follow_date
    prop.save(update_fields=['next_follow_up', 'updated_at'])


def schedule_property_follow_up(
    user,
    prop: CRMProperty,
    follow_date: date,
    note: str = '',
) -> Optional[CustomerActivity]:
    set_property_next_follow_up(prop, follow_date)
    jdate = format_jalali_date(follow_date)
    content = (note or '').strip() or f'پیگیری بعدی: {jdate}'
    customer = _property_follow_up_customer(user, prop)
    if not customer:
        return None
    return log_activity(
        customer,
        'پیگیری',
        content=content,
        title='ثبت پیگیری فایل',
        property_obj=prop,
        metadata={'follow_up_date': follow_date.isoformat(), 'property_id': prop.pk},
    )


def complete_property_follow_up(
    user,
    prop: CRMProperty,
    note: str = '',
) -> Optional[CustomerActivity]:
    if not prop.next_follow_up:
        return None
    old = prop.next_follow_up
    prop.next_follow_up = None
    prop.save(update_fields=['next_follow_up', 'updated_at'])
    content = (note or '').strip() or f'پیگیری {format_jalali_date(old)} انجام شد.'
    customer = _property_follow_up_customer(user, prop)
    if not customer:
        return None
    return log_activity(
        customer,
        'پیگیری',
        content=content,
        title='انجام پیگیری فایل',
        property_obj=prop,
        metadata={'completed_follow_up': old.isoformat(), 'property_id': prop.pk},
    )


def property_follow_up_state(prop: CRMProperty, today: date) -> str:
    fu = prop.next_follow_up
    if fu is None:
        return 'none'
    if fu < today:
        return 'overdue'
    if fu == today:
        return 'today'
    return 'upcoming'


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


_RECURRENCE_DAYS = {'daily': 1, 'weekly': 7, 'biweekly': 14, 'monthly': 30}


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
    log: bool = True,
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
    if log:
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
    from workspace.services.listing_edit import (
        district_from_listing,
        owner_name_from_listing,
        owner_phone_from_listing,
        tenant_name_from_listing,
        tenant_phone_from_listing,
    )
    from workspace.services.listing_features import build_listing_feature_profile
    from workspace.services.property_features import extract_feature_data_from_listing_data

    deal_mode = 'فروش'
    if listing.rent or listing.deposit:
        deal_mode = 'رهن و اجاره' if listing.deposit else 'اجاره'
    feat = extract_listing_features(listing)
    profile = build_listing_feature_profile(listing, feat)
    biz = (listing.business_type or '').strip()
    if feat.get('is_consultant') and not biz:
        biz = 'مشاور'
    owner_phone = normalize_phone(owner_phone_from_listing(listing))
    owner_name = (owner_name_from_listing(listing) or '').strip()
    amenity_lines = []
    for group in profile.get('groups', []):
        for item in group.get('items', []):
            amenity_lines.append(f"{item['label']}: {item['value']}")
    parking_count = (listing.data or {}).get('تعداد پارکینگ')
    from workspace.services.features import merge_data_with_attributes, parse_floor_int

    merged_data = merge_data_with_attributes(listing.data or {})
    floor_raw = feat.get('floor') or merged_data.get('طبقه')
    floor_val = parse_floor_int(floor_raw)
    if floor_val is None and floor_raw:
        floor_val = parse_floor_int(str(floor_raw).split(' از ', 1)[0])
    total_floors_raw = merged_data.get('تعداد کل طبقات ساختمان')
    total_floors = None
    if total_floors_raw:
        try:
            total_floors = int(re.search(r'\d+', str(total_floors_raw)).group())
        except (AttributeError, ValueError, TypeError):
            pass
    from workspace.services.listing_personal_status import DIVAR_SOURCE_PLATFORM

    platform, external_id = DIVAR_SOURCE_PLATFORM, str(listing.token or '').strip()
    return CRMProperty.objects.create(
        user=user,
        agency=get_agency(user),
        title=listing.title or f'ملک {listing.token}',
        property_type='آپارتمان',
        deal_mode=deal_mode,
        address=listing.neighborhood,
        city=listing.city,
        district=district_from_listing(listing),
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
        is_vacant=bool(feat.get('is_vacant')),
        tenant_phone=tenant_phone_from_listing(listing) if not feat.get('is_vacant') else '',
        tenant_name=tenant_name_from_listing(listing) if not feat.get('is_vacant') else '',
        sale_price=listing.price,
        deposit=listing.deposit,
        monthly_rent=listing.rent,
        amenities='\n'.join(amenity_lines[:40]),
        feature_data=extract_feature_data_from_listing_data(merged_data),
        images=listing.images or [],
        token=listing.token,
        source_platform=platform if external_id else '',
        source_external_id=external_id,
        link=listing.link or '',
        business_type=biz or 'شخصی',
        phone=owner_phone,
        owner_name=owner_name,
        publish_status='منتشرشده',
    )


def get_crm_property_by_token(user, token: str) -> Optional[CRMProperty]:
    """ملک CRM متناظر با شناسه آگهی (در صورت وجود)."""
    from workspace.services.listing_personal_status import (
        DIVAR_SOURCE_PLATFORM,
        get_crm_property_by_source,
    )

    token = str(token or '').strip()
    if not token:
        return None
    return get_crm_property_by_source(user, DIVAR_SOURCE_PLATFORM, token)


def migrate_customer_listings_to_crm_property(user, token: str, prop: CRMProperty) -> int:
    """
    پیوندهای «املاک مرتبط» مبتنی بر آگهی دیوار را به PropertyContact فایل شخصی منتقل می‌کند
    تا پس از حذف آگهی از فایلینگ، ملک دوبار نمایش داده نشود.
    """
    token = str(token or '').strip()
    if not token:
        return 0
    customer_ids = list(customers_qs(user).values_list('id', flat=True))
    if not customer_ids:
        return 0
    qs = CustomerListing.objects.filter(token=token, customer_id__in=customer_ids)
    migrated = 0
    for cl in qs.iterator():
        PropertyContact.objects.update_or_create(
            customer_id=cl.customer_id,
            property=prop,
            role=cl.role,
            defaults={
                'deal_type': cl.deal_type or 'سایر',
                'is_primary': cl.role == 'مالک',
                'notes': cl.notes or '',
            },
        )
        cl.delete()
        migrated += 1
    return migrated


def remove_listing_from_filing(user, listing) -> int:
    """حذف آگهی (و نسخه‌های هم‌توکن کاربر) از فایلینگ دیوار."""
    token = str(getattr(listing, 'token', '') or '').strip()
    if token:
        qs = Listing.objects.filter(token=token, dataset__user=user).select_related('dataset')
    else:
        qs = Listing.objects.filter(pk=listing.pk).select_related('dataset')

    dataset_ids = set()
    deleted = 0
    for row in list(qs):
        dataset_ids.add(row.dataset_id)
        row.delete()
        deleted += 1

    if dataset_ids:
        from workspace.models import Dataset

        for ds_id in dataset_ids:
            Dataset.objects.filter(pk=ds_id).update(
                row_count=Listing.objects.filter(dataset_id=ds_id).count(),
            )
    return deleted


def finalize_listing_moved_to_personal(user, listing, prop: CRMProperty) -> None:
    """پس از ساخت/یافتن فایل شخصی: ذخیره عکس‌ها، مهاجرت لینک‌ها، حذف از فایلینگ."""
    from workspace.services.property_images import mirror_remote_images_to_property

    source_images = list(prop.images or []) or list(listing.images or [])
    mirrored = mirror_remote_images_to_property(user, prop, source_images)
    if mirrored != list(prop.images or []):
        prop.images = mirrored
        prop.save(update_fields=['images', 'updated_at'])

    migrate_customer_listings_to_crm_property(user, listing.token, prop)
    remove_listing_from_filing(user, listing)


def add_listing_to_personal_files(user, listing) -> tuple[CRMProperty, bool]:
    """
    انتقال آگهی به فایل‌های شخصی:
    ساخت/بازیابی CRMProperty، ذخیره محلی تصاویر، مهاجرت املاک مرتبط، حذف از فایلینگ دیوار.
    """
    from django.db import IntegrityError, transaction

    from workspace.services.listing_edit import owner_name_from_listing, owner_phone_from_listing
    from workspace.services.listing_personal_status import (
        DIVAR_SOURCE_PLATFORM,
        get_crm_property_by_source,
    )

    token = str(getattr(listing, 'token', '') or '').strip()
    existing = get_crm_property_by_source(user, DIVAR_SOURCE_PLATFORM, token) if token else None
    if existing:
        phone = owner_phone_from_listing(listing) or existing.phone
        name = owner_name_from_listing(listing) or existing.owner_name
        if normalize_phone(phone):
            upsert_property_owner(
                user,
                phone=phone,
                name=name,
                crm_property=existing,
                source='دیوار',
            )
        finalize_listing_moved_to_personal(user, listing, existing)
        return existing, False

    try:
        with transaction.atomic():
            prop = property_from_listing(user, listing)
            phone = owner_phone_from_listing(listing) or prop.phone
            name = owner_name_from_listing(listing) or prop.owner_name
            if normalize_phone(phone):
                upsert_property_owner(
                    user,
                    phone=phone,
                    name=name,
                    crm_property=prop,
                    source='دیوار',
                )
            if not prop.is_vacant:
                from workspace.services.listing_edit import tenant_name_from_listing, tenant_phone_from_listing
                t_phone = tenant_phone_from_listing(listing) or prop.tenant_phone
                t_name = tenant_name_from_listing(listing) or prop.tenant_name
                if normalize_phone(t_phone) or (t_name or '').strip():
                    upsert_property_tenant(
                        user,
                        phone=t_phone,
                        name=t_name,
                        crm_property=prop,
                        source='دیوار',
                    )
            finalize_listing_moved_to_personal(user, listing, prop)
            return prop, True
    except IntegrityError:
        existing = get_crm_property_by_source(user, DIVAR_SOURCE_PLATFORM, token)
        if not existing:
            raise
        phone = owner_phone_from_listing(listing) or existing.phone
        name = owner_name_from_listing(listing) or existing.owner_name
        if normalize_phone(phone):
            upsert_property_owner(
                user,
                phone=phone,
                name=name,
                crm_property=existing,
                source='دیوار',
            )
        finalize_listing_moved_to_personal(user, listing, existing)
        return existing, False


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


def resolve_district_for_property(prop) -> str:
    """منطقه ذخیره‌شده روی ملک، یا از آگهی/دیتاست منبع."""
    existing = (getattr(prop, 'district', None) or '').strip()
    if existing:
        return existing
    user = getattr(prop, 'user', None)
    if user is None:
        return ''
    listing = resolve_listing_for_property(user, prop)
    if not listing:
        return ''
    from workspace.services.listing_edit import district_from_listing
    return district_from_listing(listing)


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
            labels.append(to_persian_digits(f'{j.day:02d}/{j.month:02d}'))
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
        {'key': 'phone', 'label': 'تلفن', 'decor': 'phone', 'count': counts['phone'], 'pct': round(counts['phone'] / total * 100)},
        {'key': 'email', 'label': 'ایمیل', 'decor': 'email', 'count': counts['email'], 'pct': round(counts['email'] / total * 100)},
        {'key': 'whatsapp', 'label': 'واتساپ', 'decor': 'whatsapp', 'count': counts['whatsapp'], 'pct': round(counts['whatsapp'] / total * 100)},
        {'key': 'sms', 'label': 'پیامک', 'decor': 'sms', 'count': counts['sms'], 'pct': round(counts['sms'] / total * 100)},
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
    if params.get('match_alerts') == '1':
        qs = qs.filter(
            match_alerts__user=user,
            match_alerts__status__in=[
                PropertyMatchAlert.STATUS_PENDING,
                PropertyMatchAlert.STATUS_NOTIFIED,
            ],
        ).distinct()
    sort = params.get('sort', '-updated_at')
    allowed = {'name', '-name', 'updated_at', '-updated_at', 'next_follow_up', '-next_follow_up', 'created_at', '-created_at'}
    if sort in allowed:
        qs = qs.order_by(sort)
    else:
        qs = qs.order_by('-updated_at')
    return qs


def filter_properties(user, params: dict):
    from datetime import date

    from workspace.services.filters import _float_param, _int_param

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

    folder_id = (params.get('folder_id') or '').strip()
    if folder_id:
        try:
            qs = qs.filter(
                folder_items__folder_id=int(folder_id),
                folder_items__folder__user=user,
            )
        except (TypeError, ValueError):
            pass
    else:
        cabinet_id = (params.get('cabinet_id') or '').strip()
        if cabinet_id:
            try:
                if cabinet_id.lower() == 'none':
                    qs = qs.filter(
                        folder_items__folder__cabinet__isnull=True,
                        folder_items__folder__user=user,
                    ).distinct()
                else:
                    qs = qs.filter(
                        folder_items__folder__cabinet_id=int(cabinet_id),
                        folder_items__folder__user=user,
                    ).distinct()
            except (TypeError, ValueError):
                pass

    for field, key in (
        ('has_parking', 'parking'),
        ('has_storage', 'storage'),
        ('has_elevator', 'elevator'),
    ):
        val = (params.get(key) or '').strip()
        if val == '1':
            qs = qs.filter(**{field: True})
        elif val == '0':
            qs = qs.filter(**{field: False})

    rooms = (params.get('rooms') or '').strip()
    if rooms:
        qs = qs.filter(rooms__icontains=rooms)

    area_min = _float_param(params.get('area_min', ''))
    area_max = _float_param(params.get('area_max', ''))
    if area_min is not None:
        qs = qs.filter(area__gte=area_min)
    if area_max is not None:
        qs = qs.filter(area__lte=area_max)

    price_min = _int_param(params.get('price_min', ''))
    price_max = _int_param(params.get('price_max', ''))
    if price_min is not None or price_max is not None:
        sale_q = Q(sale_price__isnull=False)
        deposit_q = Q(deposit__isnull=False)
        if price_min is not None:
            sale_q &= Q(sale_price__gte=price_min)
            deposit_q &= Q(deposit__gte=price_min)
        if price_max is not None:
            sale_q &= Q(sale_price__lte=price_max)
            deposit_q &= Q(deposit__lte=price_max)
        qs = qs.filter(sale_q | deposit_q)

    year_min = _int_param(params.get('year_min', ''))
    year_max = _int_param(params.get('year_max', ''))
    if year_min is not None:
        qs = qs.filter(build_year__gte=year_min)
    if year_max is not None:
        qs = qs.filter(build_year__lte=year_max)

    age_max = _int_param(params.get('age_max', ''))
    if age_max is not None and age_max >= 0:
        qs = qs.filter(build_year__gte=date.today().year - age_max)

    sort = params.get('sort', '-updated_at')
    allowed = {'title', '-title', 'updated_at', '-updated_at', 'sale_price', '-sale_price', 'area', '-area'}
    if sort in allowed:
        qs = qs.order_by(sort)
    else:
        qs = qs.order_by('-updated_at')
    return qs


PROPERTY_ADV_FILTER_KEYS = (
    'parking', 'storage', 'elevator', 'rooms',
    'area_min', 'area_max', 'price_min', 'price_max',
    'year_min', 'year_max', 'age_max',
)


def property_advanced_filter_count(params: dict) -> int:
    return sum(1 for key in PROPERTY_ADV_FILTER_KEYS if str(params.get(key) or '').strip())


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
    crm_prop = get_crm_property_by_token(customer.user, listing.token)

    link = link_customer_listing(
        customer,
        token=listing.token,
        title=listing.title or '',
        price=price_str,
        area=area_str,
        link=listing.link or '',
        role=role,
        deal_type=deal_type,
        crm_property=crm_prop,
    )
    if crm_prop is not None:
        link_customer_property(
            customer,
            crm_prop,
            role=role,
            deal_type=deal_type,
            is_primary=(role == 'مالک'),
        )
    return link


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
    """متن واتساپ برای لیست پیشنهاد ملک به خریدار/مستاجر — فقط لینک عمومی."""
    return _build_share_whatsapp_text(
        customer,
        matches,
        intro_line='چند ملک مناسب برای شما:',
        outro_lines=['در صورت تمایل برای بازدید هماهنگ می‌کنیم.', 'با احترام'],
    )


_OWNER_SIDE_ROLES = frozenset({
    'مالک', 'فروشنده', 'موجر', 'سازنده',
})


def _format_share_match_block(index: int, match: Dict[str, Any]) -> List[str]:
    from workspace.services.property_suggestion_share import sharing_link_for_match

    lines = [f'{index}. {match.get("title") or "ملک"}']
    if match.get('price_label'):
        lines.append(f'   💰 {match["price_label"]}')
    if match.get('area'):
        area_val = match['area']
        try:
            area_txt = f'{int(float(area_val))} متر'
        except (TypeError, ValueError):
            area_txt = str(area_val)
        lines.append(f'   📐 {area_txt}')
    hood = match.get('neighborhood') or match.get('city')
    if hood:
        lines.append(f'   📍 {hood}')
    share_link = sharing_link_for_match(match)
    if share_link:
        lines.append(f'   🔗 {share_link}')
    lines.append('')
    return lines


def _build_share_whatsapp_text(
    customer,
    matches: List[Dict[str, Any]],
    *,
    intro_line: str,
    outro_lines: List[str],
) -> str:
    lines = [f'سلام {customer.name}،', '', intro_line, '']
    for i, m in enumerate(matches, 1):
        lines.extend(_format_share_match_block(i, m))
    lines.extend(outro_lines)
    return '\n'.join(lines)


def build_portfolio_whatsapp_text(customer, matches: List[Dict[str, Any]]) -> str:
    """
    متن واتساپ برای اشتراک از تب املاک مرتبط.
    اگر نقش‌ها مالک/فروشنده/موجر باشند، پیام «فایل شما» است نه «پیشنهاد به مشتری».
    """
    roles = {(m.get('role') or '').strip() for m in matches}
    roles.discard('')
    owner_side = roles & _OWNER_SIDE_ROLES
    other_side = roles - _OWNER_SIDE_ROLES

    if owner_side and not other_side:
        n = len(matches)
        intro = 'لینک فایل‌های ملکی شما:' if n > 1 else 'لینک فایل ملک شما:'
        return _build_share_whatsapp_text(
            customer,
            matches,
            intro_line=intro,
            outro_lines=[
                'در صورت نیاز به هماهنگی بازدید یا به‌روزرسانی فایل، در خدمتم.',
                'با احترام',
            ],
        )

    if other_side and not owner_side:
        return build_suggestions_whatsapp_text(customer, matches)

    return _build_share_whatsapp_text(
        customer,
        matches,
        intro_line='اطلاعات املاک مرتبط:',
        outro_lines=['در صورت نیاز هماهنگ می‌کنیم.', 'با احترام'],
    )


def apply_property_suggestions(
    customer: Customer,
    user,
    matches: List[Dict[str, Any]],
    *,
    note: str = '',
    request=None,
) -> tuple[str, int]:
    """ثبت پیشنهادها در activity و پیوند ملک‌ها. برگشت: (متن واتساپ, تعداد پیوند موفق)."""
    if not matches:
        return '', 0
    from workspace.services.crm_scope import property_for_user

    if request is not None:
        from workspace.services.property_suggestion_share import enrich_matches_with_public_urls
        matches = enrich_matches_with_public_urls(user, request, matches)
    titles = []
    linked = 0
    for m in matches:
        title = m.get('title') or 'ملک'
        titles.append(title)
        if m.get('source') == 'crm' and m.get('property_id'):
            try:
                prop_id = int(m['property_id'])
            except (TypeError, ValueError):
                continue
            prop = property_for_user(user, prop_id)
            if prop is None and m.get('token'):
                prop = get_crm_property_by_token(user, m['token'])
            if prop:
                link_customer_property(
                    customer, prop, 'پیشنهادی',
                    deal_type='خرید' if prop.deal_mode == 'فروش' else 'رهن و اجاره',
                    interest_level='متوسط',
                    notes='پیشنهاد خودکار',
                )
                linked += 1
        elif m.get('source') == 'divar' and m.get('token'):
            listing = Listing.objects.filter(
                token=m['token'],
                dataset__user=user,
                dataset__is_active=True,
                is_expired=False,
            ).select_related('dataset').first()
            if listing:
                from workspace.services.display import transaction_profile

                tx = transaction_profile(listing.dataset.transaction_type)
                link_listing_to_customer(customer, listing, tx, role='پیشنهادی')
                linked += 1

    if linked:
        content = note.strip() or f'پیشنهاد {linked} ملک: ' + '، '.join(titles[:5])
        log_activity(
            customer,
            'املاک',
            content=content,
            title='ارسال پیشنهاد ملک',
            metadata={'suggestion_count': linked, 'titles': titles[:linked]},
        )
    return build_suggestions_whatsapp_text(customer, matches), linked


def _deal_type_for_property(prop: CRMProperty) -> str:
    if prop.deal_mode in ('فروش', 'پیش‌فروش'):
        return 'خرید'
    if prop.deal_mode in ('رهن و اجاره', 'اجاره'):
        return 'رهن و اجاره'
    return 'سایر'


def build_contact_suggestion_whatsapp_text(
    customer: Customer,
    prop: CRMProperty,
    *,
    public_url: str = '',
) -> str:
    """متن واتساپ پیشنهاد یک فایل شخصی به یک مخاطب."""
    from workspace.services.formatting import format_toman

    lines = [f'سلام {customer.name}،', '', 'یک ملک مناسب برای شما:', '']
    lines.append(f'1. {prop.title or "ملک"}')
    if prop.sale_price:
        lines.append(f'   💰 {format_toman(prop.sale_price)}')
    else:
        if prop.deposit:
            lines.append(f'   💰 رهن {format_toman(prop.deposit)}')
        if prop.monthly_rent:
            lines.append(f'   💰 اجاره {format_toman(prop.monthly_rent)}')
    if prop.area:
        try:
            area_txt = f'{int(float(prop.area))} متر'
        except (TypeError, ValueError):
            area_txt = str(prop.area)
        lines.append(f'   📐 {area_txt}')
    hood = prop.neighborhood or prop.district or prop.city
    if hood:
        lines.append(f'   📍 {hood}')
    if prop.property_type:
        lines.append(f'   🏠 {prop.property_type}')
    if public_url:
        lines.append(f'   🔗 {public_url}')
    lines.extend(['', 'در صورت تمایل برای بازدید هماهنگ می‌کنیم.', 'با احترام'])
    return '\n'.join(lines)


def apply_contact_suggestions(
    prop: CRMProperty,
    user,
    customer_ids: List[Any],
    *,
    note: str = '',
    request=None,
) -> Dict[str, Any]:
    """
    پیوند مخاطبان پیشنهادی به فایل شخصی.
    برگشت: {
      linked_count, whatsapp_text, public_url,
      suggestions: [{customer_id, name, phone, whatsapp_text, whatsapp_url}]
    }
    """
    from workspace.services.crm_scope import can_edit_customer, customer_for_user
    from workspace.services.property_suggestion_share import whatsapp_url_for_customer

    empty = {
        'linked_count': 0,
        'whatsapp_text': '',
        'public_url': '',
        'suggestions': [],
    }
    if not customer_ids:
        return empty

    public_url = ''
    if request is not None:
        from workspace.services.property_public_share import (
            get_or_create_property_share,
            property_public_share_url,
        )
        share = get_or_create_property_share(user, prop)
        public_url = property_public_share_url(request, share)

    deal_type = _deal_type_for_property(prop)
    suggestions: List[Dict[str, Any]] = []
    seen: set[int] = set()
    note_content = note.strip() or f'پیشنهاد فایل شخصی «{prop.title}»'

    for raw_id in customer_ids:
        try:
            cid = int(raw_id)
        except (TypeError, ValueError):
            continue
        if cid in seen:
            continue
        seen.add(cid)
        customer = customer_for_user(user, cid)
        if not customer or not can_edit_customer(user, customer):
            continue
        link_customer_property(
            customer,
            prop,
            'پیشنهادی',
            deal_type=deal_type,
            interest_level='متوسط',
            notes='پیشنهاد خودکار',
            log=False,
        )
        log_activity(
            customer,
            'املاک',
            content=note_content,
            title='پیشنهاد ملک از فایل شخصی',
            property_obj=prop,
            metadata={
                'suggestion_from': 'property',
                'property_id': prop.pk,
                'property_title': prop.title or '',
                'role': 'پیشنهادی',
                'deal_type': deal_type,
            },
        )
        wa_text = build_contact_suggestion_whatsapp_text(
            customer, prop, public_url=public_url,
        )
        suggestions.append({
            'customer_id': customer.pk,
            'name': customer.name,
            'phone': customer.phone or '',
            'whatsapp_text': wa_text,
            'whatsapp_url': whatsapp_url_for_customer(customer, wa_text),
            'active_channels': list(getattr(customer, 'active_channels', None) or []),
            'social_links': dict(getattr(customer, 'social_links', None) or {}),
        })

    if not suggestions:
        return empty

    return {
        'linked_count': len(suggestions),
        'whatsapp_text': suggestions[0]['whatsapp_text'],
        'public_url': public_url,
        'suggestions': suggestions,
    }


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
            'شغل': c.job,
            'نام شرکت': c.company_name,
            'کد ملی': c.national_id,
            'مهلت اجاره': _excel_safe_value(c.lease_deadline),
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


def export_customers_csv_response(user, params: Optional[dict] = None):
    import csv
    import io

    from django.http import HttpResponse

    rows = customers_to_export_rows(export_customers_queryset(user, params))
    if not rows:
        rows = [{'نام': ''}]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    filename = f'crm_contacts_{datetime.now().strftime("%Y%m%d")}.csv'
    response = HttpResponse(
        buf.getvalue().encode('utf-8-sig'),
        content_type='text/csv; charset=utf-8',
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
            'نوع آگهی دهنده': p.business_type,
            'شماره تماس': p.phone,
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
            'تخلیه': _bool_fa(p.is_vacant),
            'نام مستاجر': p.tenant_name if not p.is_vacant else '',
            'شماره مستاجر': p.tenant_phone if not p.is_vacant else '',
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
