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
from workspace.services.crm_scope import (
    assert_can_mutate_customer,
    can_mutate_reminder,
    customers_qs,
    get_agency,
    properties_qs,
    reminders_qs,
)
from workspace.services.crm_today import get_today_queue
from accounts.phone_utils import normalize_phone


def list_contacts(
    user,
    *,
    q: str = '',
    page: int = 1,
    page_size: int = 50,
    customer_type: str = '',
    status: str = '',
    priority: str = '',
    due: str = '',
    sort: str = '',
    tag: str = '',
    archive_scope: str = '',
) -> Tuple[List[dict], dict]:
    qs = filter_contacts(user, {
        'q': q,
        'customer_type': customer_type,
        'status': status,
        'priority': priority,
        'due': due,
        'sort': sort,
        'tags': tag,
        'archive_scope': archive_scope,
    })
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    items = [contact_to_dict(c) for c in page_obj.object_list]
    meta = {'page': page, 'page_size': page_size, 'total': paginator.count}
    return items, meta


def get_contact(user, contact_id: int) -> Optional[Customer]:
    contact = customers_qs(user).filter(pk=contact_id).first()
    if contact:
        return contact
    from workspace.services.agency_data_scope import customer_for_agency_viewer

    return customer_for_agency_viewer(user, contact_id)


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
    payload = contact_detail_to_dict(
        c,
        activities=activities,
        reminders=reminders,
        linked_listings=linked,
        deals=deals,
        properties=properties,
        documents=documents,
        request=request,
    )
    from mobile_api.services.agency_space_mobile import (
        mobile_provenance_for_customer,
        mobile_source_context,
    )

    from workspace.services.crm_scope import can_edit_customer

    payload['agency_space'] = mobile_source_context(user, customer=c)
    payload['agency_space_provenance'] = mobile_provenance_for_customer(c, user)
    payload['can_edit'] = can_edit_customer(user, c)
    return payload


def _field_present(data: Dict[str, Any], key: str) -> bool:
    """JSON null یعنی بدون تغییر؛ کلید غایب هم بدون تغییر."""
    return key in data and data.get(key) is not None


def _contact_patch_has_writes(data: Dict[str, Any]) -> bool:
    if not data:
        return False
    scalar_fields = (
        'full_name', 'name', 'phone', 'email', 'status', 'customer_type', 'priority', 'notes', 'tags',
        'property_type', 'property_types', 'rooms', 'areas', 'streets', 'budget', 'budget_min', 'budget_max',
        'deposit_min', 'deposit_max', 'rent_min', 'rent_max', 'builder_buy_property_types',
        'builder_buy_types', 'builder_buy_areas', 'builder_buy_budget_min', 'builder_buy_budget_max',
        'builder_buy_min_area', 'builder_buy_max_area', 'min_area', 'max_area', 'lease_deadline',
        'matching_tolerance_percent', 'restore_status', 'reactivation_due_jalali',
    )
    for key in scalar_fields:
        if _field_present(data, key):
            return True
    for key in ('rooms_min', 'rooms_max', 'year_min', 'year_max', 'floor_min', 'floor_max'):
        if key in data and data[key] is not None:
            return True
    for key in ('want_parking', 'want_storage', 'want_elevator'):
        if key in data and data[key] is not None:
            return True
    if 'is_archived' in data and data['is_archived'] is not None:
        return True
    if 'source' in data and data['source'] is not None:
        return True
    if 'city' in data and data['city'] is not None:
        return True
    if 'district' in data and data['district'] is not None:
        return True
    if 'phone_alt' in data and data['phone_alt'] is not None:
        return True
    if 'job' in data and data['job'] is not None:
        return True
    if 'company_name' in data and data['company_name'] is not None:
        return True
    if 'national_id' in data and data['national_id'] is not None:
        return True
    if 'gender' in data:
        return True
    if 'social_links' in data and isinstance(data['social_links'], dict):
        return True
    if 'active_channels' in data and isinstance(data['active_channels'], list):
        return True
    return False


def _parse_contact_archive_patch(data: Dict[str, Any], customer: Customer) -> Dict[str, Any]:
    from workspace.constants import CRM_STATUSES
    from workspace.services.crm_contact_archive import COMMUNICATION_STATUSES, is_contact_archived

    has_archived_flag = 'is_archived' in data and data['is_archived'] is not None
    is_archived_flag = data.get('is_archived') if has_archived_flag else None
    status_present = _field_present(data, 'status')
    status_val = (data.get('status') or '').strip() if status_present else ''
    restore_status = (data.get('restore_status') or '').strip()

    wants_archive = is_archived_flag is True or status_val == 'بایگانی'
    wants_restore = is_archived_flag is False and is_contact_archived(customer)

    if wants_archive and wants_restore:
        raise ValueError('درخواست بایگانی و بازگردانی همزمان معتبر نیست.')
    if is_archived_flag is False and status_val == 'بایگانی':
        raise ValueError('برای بازگردانی، وضعیت «بایگانی» قابل استفاده نیست.')
    if wants_restore and status_present and status_val and status_val not in COMMUNICATION_STATUSES:
        raise ValueError('وضعیت بازگردانی نامعتبر است.')
    if (
        status_present
        and status_val
        and status_val != 'بایگانی'
        and is_contact_archived(customer)
        and not wants_restore
    ):
        raise ValueError('برای تغییر وضعیت، ابتدا مخاطب را از بایگانی بازگردانید.')

    effective_restore_status = restore_status
    if wants_restore and not effective_restore_status and status_val and status_val != 'بایگانی':
        effective_restore_status = status_val

    new_status = ''
    if status_present and status_val and status_val != 'بایگانی' and not wants_archive and not wants_restore:
        if status_val not in CRM_STATUSES:
            raise ValueError('وضعیت نامعتبر')
        new_status = status_val

    if wants_archive and is_contact_archived(customer):
        wants_archive = False

    return {
        'archive': wants_archive,
        'restore': wants_restore,
        'restore_status': effective_restore_status,
        'new_status': new_status,
        'via_legacy_status': status_val == 'بایگانی',
        'reactivation_due_jalali': (data.get('reactivation_due_jalali') or '').strip(),
        'archive_reason': (data.get('archive_reason') or '').strip(),
        'archive_note': (data.get('archive_note') or '').strip(),
    }


def update_contact(user, contact_id: int, data: Dict[str, Any]) -> Optional[Customer]:
    from django.db import transaction

    from workspace.services.crm import update_customer_status
    from workspace.services.crm_contact_archive import archive_contact, is_contact_archived, restore_contact
    from workspace.services.crm_scope import can_edit_customer

    c = get_contact(user, contact_id)
    if not c:
        return None
    if _contact_patch_has_writes(data) and not can_edit_customer(user, c):
        raise PermissionError('امکان ویرایش این مخاطب را ندارید')
    if not _contact_patch_has_writes(data):
        return c

    archive_patch = _parse_contact_archive_patch(data, c)

    if _field_present(data, 'full_name') or _field_present(data, 'name'):
        c.name = (data.get('full_name') or data.get('name') or c.name).strip()
    if _field_present(data, 'phone'):
        phone = normalize_phone(data['phone'])
        if phone:
            c.phone = phone
    if _field_present(data, 'email'):
        c.email = (data.get('email') or '').strip()
    if 'source' in data and data['source'] is not None:
        c.source = (data.get('source') or '').strip()[:30]
    if _field_present(data, 'customer_type') and data['customer_type']:
        c.customer_type = data['customer_type']
    if _field_present(data, 'priority') and data['priority']:
        c.priority = data['priority']
    if _field_present(data, 'notes'):
        c.notes = data['notes'] or ''
    if _field_present(data, 'tags'):
        c.tags = (data.get('tags') or '').strip()[:500]
    if _field_present(data, 'property_type'):
        from workspace.services.customer_search_property_types import (
            apply_customer_search_property_types,
            normalize_customer_search_property_types,
        )
        pt = (data['property_type'] or '').strip()
        if pt:
            c.property_type = pt
            if not _field_present(data, 'property_types'):
                apply_customer_search_property_types(c, [pt])
        elif not _field_present(data, 'property_types'):
            apply_customer_search_property_types(c, [])
    if _field_present(data, 'property_types'):
        from workspace.services.customer_search_property_types import (
            apply_customer_search_property_types,
            normalize_customer_search_property_types,
        )
        raw = data['property_types']
        if isinstance(raw, list):
            apply_customer_search_property_types(
                c,
                normalize_customer_search_property_types(raw),
            )
        else:
            apply_customer_search_property_types(c, [])
    if _field_present(data, 'rooms'):
        c.rooms = (data['rooms'] or '').strip()
    if _field_present(data, 'areas'):
        c.areas = (data['areas'] or '').strip()
    if _field_present(data, 'streets'):
        c.streets = (data['streets'] or '').strip()
    for field in ('budget_min', 'budget_max', 'deposit_min', 'deposit_max', 'rent_min', 'rent_max',
                  'builder_buy_budget_min', 'builder_buy_budget_max'):
        if _field_present(data, field):
            setattr(c, field, _optional_bigint(data[field]))
    if _field_present(data, 'builder_buy_property_types'):
        raw = data['builder_buy_property_types']
        if isinstance(raw, list):
            c.builder_buy_property_types = ', '.join(str(x).strip() for x in raw if str(x).strip())
        else:
            c.builder_buy_property_types = (raw or '').strip()
    if _field_present(data, 'builder_buy_types'):
        raw = data['builder_buy_types']
        if isinstance(raw, list):
            c.builder_buy_property_types = ', '.join(str(x).strip() for x in raw if str(x).strip())
        else:
            c.builder_buy_property_types = (raw or '').strip()
    if _field_present(data, 'builder_buy_areas'):
        c.builder_buy_areas = (data['builder_buy_areas'] or '').strip()
    for field in ('builder_buy_min_area', 'builder_buy_max_area'):
        if _field_present(data, field):
            setattr(c, field, _optional_int(data[field]))
    if _field_present(data, 'budget') and not _field_present(data, 'budget_max'):
        c.budget_max = _optional_bigint(data['budget'])
    for field in ('min_area', 'max_area'):
        if _field_present(data, field):
            setattr(c, field, _optional_int(data[field]))
    if 'social_links' in data and isinstance(data['social_links'], dict):
        from workspace.services.public_share_common import normalize_social_links
        c.social_links = normalize_social_links(data['social_links'])
    if 'active_channels' in data and isinstance(data['active_channels'], list):
        from workspace.services.contact_channels import normalize_active_channels
        c.active_channels = normalize_active_channels(
            data['active_channels'],
            social_links=c.social_links,
            phone=c.phone or '',
        )
    if 'city' in data and data['city'] is not None:
        c.city = (data.get('city') or '').strip()
    if 'district' in data and data['district'] is not None:
        c.district = (data.get('district') or '').strip()
    if 'phone_alt' in data and data['phone_alt'] is not None:
        alt = normalize_phone(data.get('phone_alt') or '')
        c.phone_alt = alt
    if 'job' in data and data['job'] is not None:
        c.job = (data.get('job') or '').strip()[:120]
    if 'company_name' in data and data['company_name'] is not None:
        c.company_name = (data.get('company_name') or '').strip()[:200]
    if 'national_id' in data and data['national_id'] is not None:
        c.national_id = (data.get('national_id') or '').strip()[:20]
    if 'gender' in data:
        from workspace.services.contact_gender import parse_contact_gender_api
        raw_gender = data.get('gender')
        if raw_gender is None:
            pass
        elif raw_gender == '':
            c.gender = None
        else:
            c.gender = parse_contact_gender_api(raw_gender)
    if c.is_legal_entity:
        c.gender = None
    if _field_present(data, 'lease_deadline'):
        from workspace.services.jalali_input import parse_jalali_date_string
        raw = data.get('lease_deadline')
        if raw == '':
            c.lease_deadline = None
        else:
            parsed = parse_jalali_date_string(str(raw).strip())
            if parsed is None:
                raise ValueError('تاریخ مهلت اجاره نامعتبر است.')
            c.lease_deadline = parsed
    for field in ('rooms_min', 'rooms_max', 'year_min', 'year_max', 'floor_min', 'floor_max'):
        if field in data and data[field] is not None:
            setattr(c, field, _optional_int(data[field]))
    for bool_field in ('want_parking', 'want_storage', 'want_elevator'):
        if bool_field in data and data[bool_field] is not None:
            setattr(c, bool_field, bool(data.get(bool_field)))
    if _field_present(data, 'matching_tolerance_percent'):
        from workspace.services.crm_matching import normalize_matching_tolerance_percent
        try:
            c.matching_tolerance_percent = normalize_matching_tolerance_percent(
                data.get('matching_tolerance_percent'),
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
    from workspace.services.crm_merge import duplicate_contact_message, find_duplicate_contact
    duplicate = find_duplicate_contact(user, c.name, c.phone, exclude_pk=c.pk)
    if duplicate:
        raise ValueError(duplicate_contact_message(duplicate))

    with transaction.atomic():
        c.save()
        if archive_patch['archive']:
            archive_contact(
                user,
                c,
                reason=archive_patch['archive_reason'],
                archive_note=archive_patch['archive_note'],
                reactivation_due_jalali=archive_patch['reactivation_due_jalali'],
                via_legacy_status=archive_patch['via_legacy_status'],
            )
        elif archive_patch['restore']:
            restore_contact(user, c, restore_status=archive_patch['restore_status'])
        elif archive_patch['new_status']:
            update_customer_status(c, archive_patch['new_status'], user=user)
    c.refresh_from_db()
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
    from workspace.services.crm_merge import duplicate_contact_message, find_duplicate_contact

    name = (data.get('full_name') or data.get('name') or '').strip()
    phone = normalize_phone(data.get('phone') or '')
    if not name:
        raise ValueError('نام الزامی است.')
    if not phone:
        raise ValueError('شماره تلفن نامعتبر است.')
    duplicate = find_duplicate_contact(user, name, phone)
    if duplicate:
        raise ValueError(duplicate_contact_message(duplicate))
    source = (data.get('source') or 'موبایل').strip()[:30]
    valid_sources = {s for s, _ in Customer._meta.get_field('source').choices}
    if source not in valid_sources:
        source = 'موبایل' if 'موبایل' in valid_sources else 'سایر'
    customer_type = (data.get('customer_type') or '').strip()
    valid_types = {t for t, _ in Customer._meta.get_field('customer_type').choices}
    if customer_type not in valid_types:
        customer_type = 'سرنخ'
    customer = Customer(
        user=user,
        agency=get_agency(user),
        name=name,
        phone=phone,
        source=source,
        customer_type=customer_type,
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


_NL_CUSTOMER_ALLOWED = frozenset({
    'name', 'phone', 'phone_alt', 'email', 'city', 'district', 'job', 'gender',
    'is_legal_entity', 'company_name',
    'customer_type', 'status', 'priority', 'source', 'property_type',
    'budget_min', 'budget_max', 'deposit_min', 'deposit_max', 'rent_min', 'rent_max',
    'min_area', 'max_area', 'rooms_min', 'rooms_max', 'year_min', 'year_max',
    'floor_min', 'floor_max', 'areas', 'streets', 'rooms',
    'want_parking', 'want_storage', 'want_elevator',
    'tags', 'notes', 'next_follow_up',
})


def create_customer_from_nl(user, data: Dict[str, Any]) -> Customer:
    """ثبت مخاطب از فرمان هوشمند — فیلدهای CRM موجود (whitelist)."""
    from workspace.constants import CRM_PRIORITIES, CRM_PROPERTIES, CRM_SOURCES, CRM_STATUSES, CRM_TYPES

    payload = {k: v for k, v in (data or {}).items() if k in _NL_CUSTOMER_ALLOWED}

    name = (payload.get('name') or '').strip()
    if not name:
        raise ValueError('نام الزامی است.')
    phone = normalize_phone(payload.get('phone') or '')
    phone_alt = normalize_phone(payload.get('phone_alt') or '')

    customer_type = (payload.get('customer_type') or 'خریدار').strip()
    if customer_type not in CRM_TYPES:
        customer_type = 'خریدار'

    status = (payload.get('status') or 'جدید').strip() or 'جدید'
    if status not in CRM_STATUSES:
        status = 'جدید'

    priority = (payload.get('priority') or 'متوسط').strip() or 'متوسط'
    if priority not in CRM_PRIORITIES:
        priority = 'متوسط'

    source = (payload.get('source') or '').strip()[:30]
    valid_sources = set(CRM_SOURCES)
    if source and source not in valid_sources:
        source = ''

    property_type = (payload.get('property_type') or '').strip()
    if property_type and property_type not in CRM_PROPERTIES:
        property_type = ''

    rooms = (payload.get('rooms') or '').strip()
    rmin, rmax = payload.get('rooms_min'), payload.get('rooms_max')
    if rmin is not None and rmax is not None:
        rooms = f'{rmin}-{rmax}' if rmin != rmax else str(rmin)
    elif rmin is not None:
        rooms = str(rmin)
    elif rmax is not None:
        rooms = str(rmax)

    customer = Customer(
        user=user,
        agency=get_agency(user),
        name=name,
        phone=phone,
        phone_alt=phone_alt,
        email=(payload.get('email') or '').strip(),
        city=(payload.get('city') or '').strip()[:100],
        district=(payload.get('district') or '').strip()[:100],
        job=(payload.get('job') or '').strip()[:120],
        gender=payload.get('gender') if payload.get('gender') in ('male', 'female') else None,
        is_legal_entity=bool(payload.get('is_legal_entity')) if payload.get('is_legal_entity') is not None else False,
        company_name=(payload.get('company_name') or '').strip()[:200],
        customer_type=customer_type,
        status=status,
        priority=priority,
        source=source,
        property_type=property_type,
        areas=(payload.get('areas') or '').strip(),
        streets=(payload.get('streets') or '').strip(),
        min_area=payload.get('min_area'),
        max_area=payload.get('max_area'),
        budget_min=payload.get('budget_min'),
        budget_max=payload.get('budget_max'),
        deposit_min=payload.get('deposit_min'),
        deposit_max=payload.get('deposit_max'),
        rent_min=payload.get('rent_min'),
        rent_max=payload.get('rent_max'),
        rooms_min=rmin,
        rooms_max=rmax,
        rooms=rooms,
        year_min=payload.get('year_min'),
        year_max=payload.get('year_max'),
        floor_min=payload.get('floor_min'),
        floor_max=payload.get('floor_max'),
        want_parking=bool(payload.get('want_parking')),
        want_storage=bool(payload.get('want_storage')),
        want_elevator=bool(payload.get('want_elevator')),
        tags=(payload.get('tags') or '').strip()[:500],
        notes=(payload.get('notes') or '').strip(),
        next_follow_up=payload.get('next_follow_up'),
    )
    if customer.is_legal_entity:
        customer.gender = None
    customer.save()
    log_activity(customer, 'یادداشت', content='ثبت از فرمان هوشمند', title='ثبت مخاطب')
    return customer


_NL_PROPERTY_ALLOWED = frozenset({
    'title', 'property_type', 'deal_mode', 'transaction_status', 'publish_status',
    'business_type', 'city', 'district', 'neighborhood', 'address',
    'area', 'rooms', 'floor', 'total_floors', 'build_year',
    'postal_code', 'land_area', 'frontage_width',
    'has_parking', 'has_storage', 'has_elevator', 'is_vacant',
    'has_wardrobe', 'has_two_corner', 'has_two_access',
    'has_wallpaper', 'has_knauf', 'has_lighting',
    'feature_data',
    'sale_price', 'deposit', 'monthly_rent', 'amenities', 'phone', 'owner_name', 'notes',
})


def create_property_from_nl(user, data: Dict[str, Any]) -> CRMProperty:
    """ثبت فایل شخصی از فرمان هوشمند — فقط فیلدهای explicit + عنوان."""
    from workspace.constants import CRM_PROPERTIES, PROPERTY_DEAL_MODES, PROPERTY_PUBLISH_STATUSES, PROPERTY_TX_STATUSES

    explicit = set(data.get('_explicit_fields') or [])
    payload = {k: v for k, v in (data or {}).items() if k in _NL_PROPERTY_ALLOWED}

    title = (payload.get('title') or '').strip()
    if not title:
        raise ValueError('عنوان ملک الزامی است.')

    deal_mode = (payload.get('deal_mode') or '').strip()
    if deal_mode not in PROPERTY_DEAL_MODES:
        raise ValueError('نوع معامله نامعتبر است.')

    prop = CRMProperty(
        user=user,
        agency=get_agency(user),
        title=title[:300],
        deal_mode=deal_mode,
        area=payload.get('area'),
    )

    if 'property_type' in explicit:
        property_type = (payload.get('property_type') or '').strip()
        if property_type in CRM_PROPERTIES:
            prop.property_type = property_type

    if 'transaction_status' in explicit:
        tx = (payload.get('transaction_status') or '').strip()
        if tx in PROPERTY_TX_STATUSES:
            prop.transaction_status = tx

    if 'publish_status' in explicit:
        pub = (payload.get('publish_status') or '').strip()
        if pub in PROPERTY_PUBLISH_STATUSES:
            prop.publish_status = pub

    str_fields = (
        'city', 'district', 'neighborhood', 'address', 'rooms',
        'amenities', 'notes', 'owner_name', 'business_type',
    )
    max_len = {
        'city': 100, 'district': 100, 'neighborhood': 200, 'rooms': 20,
        'owner_name': 200, 'business_type': 50,
    }
    for field in str_fields:
        if field in explicit and payload.get(field) is not None:
            val = (payload.get(field) or '')
            if field in max_len:
                val = val[: max_len[field]]
            setattr(prop, field, val)

    if 'phone' in explicit:
        prop.phone = (payload.get('phone') or '')[:20]

    for int_field in ('floor', 'total_floors', 'build_year', 'sale_price', 'deposit', 'monthly_rent'):
        if int_field in explicit and payload.get(int_field) is not None:
            setattr(prop, int_field, payload.get(int_field))

    for bool_field in (
        'has_parking', 'has_storage', 'has_elevator', 'is_vacant',
        'has_wardrobe', 'has_two_corner', 'has_two_access',
        'has_wallpaper', 'has_knauf', 'has_lighting',
    ):
        if bool_field in explicit and payload.get(bool_field) is not None:
            setattr(prop, bool_field, bool(payload[bool_field]))

    if 'postal_code' in explicit:
        from contracts.services.party_sanitize import sanitize_postal_code
        prop.postal_code = sanitize_postal_code(str(payload.get('postal_code') or ''))

    for float_field in ('land_area', 'frontage_width'):
        if float_field in explicit and payload.get(float_field) is not None:
            setattr(prop, float_field, payload.get(float_field))

    fd = dict(payload.get('feature_data') or {})
    if fd:
        from workspace.services.property_features import seed_feature_toggles_from_amenities
        from workspace.services.property_public_share import split_amenities_for_checkbox_form

        if 'amenities' in explicit and payload.get('amenities'):
            selected, _left = split_amenities_for_checkbox_form(
                payload.get('amenities') or '',
                has_parking=prop.has_parking,
                has_storage=prop.has_storage,
                has_elevator=prop.has_elevator,
            )
            fd = seed_feature_toggles_from_amenities(fd, selected)
        prop.feature_data = fd

    if 'postal_code' in explicit:
        from mobile_api.services.properties_service import _sync_property_postal_feature
        _sync_property_postal_feature(prop)

    prop.save()
    return prop


def create_activity(user, contact_id: int, data: Dict[str, Any]) -> CustomerActivity:
    c = get_contact(user, contact_id)
    if not c:
        raise ValueError('مخاطب یافت نشد.')
    assert_can_mutate_customer(user, c)
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
    assert_can_mutate_customer(user, c)
    title = (data.get('title') or '').strip()
    if not title:
        raise ValueError('عنوان یادآور الزامی است.')
    due_raw = data.get('due_at') or data.get('due_date')
    due_at = parse_datetime(due_raw) if due_raw else None
    if not due_at:
        raise ValueError('زمان سررسید الزامی است.')
    if timezone.is_naive(due_at):
        due_at = timezone.make_aware(due_at, timezone.get_current_timezone())
    from workspace.constants import REMINDER_RECURRENCE
    allowed = {key for key, _ in REMINDER_RECURRENCE}
    recurrence = (data.get('recurrence') or '').strip()
    if recurrence not in allowed:
        recurrence = ''
    reminder = Reminder.objects.create(
        user=user,
        customer=c,
        title=title,
        note=(data.get('note') or '').strip(),
        due_at=due_at,
        token=(data.get('token') or '')[:100],
        recurrence=recurrence,
    )
    log_activity(c, 'یادآور', content=title, title='یادآور جدید')
    return reminder


def create_standalone_reminder(user, data: Dict[str, Any]) -> Reminder:
    """ایجاد یادآور با contact_id اختیاری."""
    contact_id = data.get('contact_id')
    if contact_id:
        return create_reminder(user, int(contact_id), data)
    title = (data.get('title') or '').strip()
    if not title:
        raise ValueError('عنوان یادآور الزامی است.')
    due_raw = data.get('due_at') or data.get('due_date')
    due_at = parse_datetime(due_raw) if due_raw else None
    if not due_at:
        raise ValueError('زمان سررسید الزامی است.')
    if timezone.is_naive(due_at):
        due_at = timezone.make_aware(due_at, timezone.get_current_timezone())
    from workspace.constants import REMINDER_RECURRENCE
    allowed = {key for key, _ in REMINDER_RECURRENCE}
    recurrence = (data.get('recurrence') or '').strip()
    if recurrence not in allowed:
        recurrence = ''
    return Reminder.objects.create(
        user=user,
        customer=None,
        title=title,
        note=(data.get('note') or '').strip(),
        due_at=due_at,
        token=(data.get('token') or '')[:100],
        recurrence=recurrence,
    )


def list_reminders(
    user,
    *,
    due_from=None,
    due_to=None,
    done: Optional[bool] = None,
    limit: int = 200,
) -> List[Reminder]:
    qs = reminders_qs(user).select_related('customer').order_by('due_at')
    if due_from is not None:
        qs = qs.filter(due_at__gte=due_from)
    if due_to is not None:
        qs = qs.filter(due_at__lte=due_to)
    if done is True:
        qs = qs.filter(is_done=True)
    elif done is False:
        qs = qs.filter(is_done=False)
    return list(qs[:limit])


def update_reminder(user, reminder_id: int, data: Dict[str, Any]) -> Optional[Reminder]:
    r = reminders_qs(user).filter(pk=reminder_id).select_related('customer').first()
    if not r:
        return None
    if not can_mutate_reminder(user, r):
        raise PermissionError('امکان ویرایش این یادآور را ندارید')
    fields = []
    if 'title' in data:
        title = (data.get('title') or '').strip()
        if not title:
            raise ValueError('عنوان یادآور الزامی است.')
        r.title = title
        fields.append('title')
    if 'note' in data:
        r.note = (data.get('note') or '').strip()
        fields.append('note')
    if data.get('due_at') or data.get('due_date'):
        due_raw = data.get('due_at') or data.get('due_date')
        due_at = parse_datetime(due_raw)
        if not due_at:
            raise ValueError('زمان سررسید نامعتبر است.')
        if timezone.is_naive(due_at):
            due_at = timezone.make_aware(due_at, timezone.get_current_timezone())
        r.due_at = due_at
        fields.append('due_at')
    if 'recurrence' in data:
        from workspace.constants import REMINDER_RECURRENCE
        allowed = {key for key, _ in REMINDER_RECURRENCE}
        recurrence = (data.get('recurrence') or '').strip()
        if recurrence not in allowed:
            raise ValueError('نوع تکرار نامعتبر است.')
        r.recurrence = recurrence
        fields.append('recurrence')
    if fields:
        r.save(update_fields=fields)
    return r


def delete_reminder(user, reminder_id: int) -> bool:
    r = reminders_qs(user).filter(pk=reminder_id).select_related('customer').first()
    if not r:
        return False
    if not can_mutate_reminder(user, r):
        raise PermissionError('امکان حذف این یادآور را ندارید')
    r.delete()
    return True


def complete_reminder(user, reminder_id: int, *, note: str = '') -> Optional[Reminder]:
    r = reminders_qs(user).filter(pk=reminder_id, is_done=False).select_related('customer').first()
    if not r:
        return None
    if not can_mutate_reminder(user, r):
        raise PermissionError('امکان تکمیل این یادآور را ندارید')
    r.is_done = True
    r.save(update_fields=['is_done'])
    if r.customer_id:
        content = (note or '').strip() or f'یادآور «{r.title}» انجام شد.'
        log_activity(r.customer, 'یادآور', content=content, title='انجام یادآور')
    if r.recurrence:
        from workspace.services.crm import advance_recurring_reminder
        advance_recurring_reminder(r)
    return r


def postpone_reminder(user, reminder_id: int, *, days: int = 1, hours: int = 0) -> Optional[Reminder]:
    r = reminders_qs(user).filter(pk=reminder_id, is_done=False).select_related('customer').first()
    if not r:
        return None
    if not can_mutate_reminder(user, r):
        raise PermissionError('امکان تعویق این یادآور را ندارید')
    delta_days = max(0, int(days or 0))
    delta_hours = max(0, int(hours or 0))
    if delta_days == 0 and delta_hours == 0:
        delta_days = 1
    r.due_at = r.due_at + timedelta(days=delta_days, hours=delta_hours)
    r.save(update_fields=['due_at'])
    return r


def complete_follow_up_task(user, contact_id: int, *, note: str = '') -> Optional[Customer]:
    from workspace.services.crm import complete_follow_up
    c = get_contact(user, contact_id)
    if not c:
        return None
    assert_can_mutate_customer(user, c)
    complete_follow_up(c, note=note)
    return c


def postpone_follow_up(user, contact_id: int, *, days: int = 1) -> Optional[Customer]:
    from workspace.services.crm import set_next_follow_up
    c = get_contact(user, contact_id)
    if not c:
        return None
    assert_can_mutate_customer(user, c)
    base = c.next_follow_up or timezone.now().date()
    new_date = base + timedelta(days=max(1, days))
    set_next_follow_up(c, new_date, auto_status=False)
    log_activity(c, 'پیگیری', content=f'پیگیری به {new_date.isoformat()} موکول شد.', title='تعویق پیگیری')
    return c


def link_listing_to_contact(user, contact_id: int, data: Dict[str, Any]) -> CustomerListing:
    c = get_contact(user, contact_id)
    if not c:
        raise ValueError('مخاطب یافت نشد.')
    assert_can_mutate_customer(user, c)
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
    # Follow-ups do not have an is_done flag: completion clears
    # next_follow_up and writes a structured CustomerActivity. Count these
    # explicitly or dashboard progress can stay at zero all day.
    done_followups = CustomerActivity.objects.filter(
        customer__in=customers_qs(user),
        metadata__has_key='completed_follow_up',
        created_at__date=timezone.now().date(),
    ).count()
    done_today += done_followups
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


def crm_neighborhoods_payload(user) -> Dict[str, Any]:
    """محله و خیابان distinct از فایلینگ و فایل شخصی — برای ترجیحات مخاطب."""
    from workspace.services.filters import get_user_dataset_neighborhoods, get_user_location_streets

    return {
        'neighborhoods': get_user_dataset_neighborhoods(user),
        'streets': get_user_location_streets(user),
    }
