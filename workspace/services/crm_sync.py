"""همگام‌سازی CRM وب ↔ دسکتاپ — D8."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from workspace.models import CRMDeal, CRMProperty, CRMSyncLog, Customer
from workspace.services.crm_audit import log_agency_audit
from workspace.services.crm_import_phone import parse_import_phone_fields
from workspace.services.crm_scope import (
    agency_customers_qs, agency_deals_qs, agency_properties_qs,
    can_manage_team, customers_qs, deals_qs, get_agency, properties_qs,
)


def export_crm_payload(user, *, agency_scope: bool = False) -> Dict[str, Any]:
    agency = get_agency(user)
    if agency_scope and agency and can_manage_team(user):
        contacts = list(agency_customers_qs(agency).values(
            'id', 'name', 'phone', 'phone_alt', 'email', 'customer_type', 'status',
            'priority', 'source', 'city', 'tags', 'notes', 'next_follow_up',
            'assigned_to_id', 'team_visibility', 'created_at', 'updated_at',
        ))
        properties = list(agency_properties_qs(agency).values(
            'id', 'title', 'property_type', 'deal_mode', 'transaction_status',
            'city', 'neighborhood', 'sale_price', 'deposit', 'monthly_rent', 'area',
            'token', 'notes', 'user_id', 'created_at', 'updated_at',
        ))
        deals = list(agency_deals_qs(agency).values(
            'id', 'title', 'stage', 'value', 'probability', 'customer_id',
            'listing_token', 'commission_amount', 'user_id', 'created_at', 'updated_at',
        ))
        scope = 'agency'
    else:
        contacts = list(customers_qs(user).values(
            'id', 'name', 'phone', 'phone_alt', 'email', 'customer_type', 'status',
            'priority', 'source', 'city', 'tags', 'notes', 'next_follow_up',
            'assigned_to_id', 'created_at', 'updated_at',
        ))
        properties = list(properties_qs(user).values(
            'id', 'title', 'property_type', 'deal_mode', 'transaction_status',
            'city', 'neighborhood', 'sale_price', 'deposit', 'monthly_rent', 'area',
            'token', 'notes', 'created_at', 'updated_at',
        ))
        deals = list(deals_qs(user).values(
            'id', 'title', 'stage', 'value', 'probability', 'customer_id',
            'listing_token', 'commission_amount', 'created_at', 'updated_at',
        ))
        scope = 'user'
    return {
        'version': 2,
        'scope': scope,
        'agency_id': agency.pk if agency else None,
        'contacts': contacts,
        'properties': properties,
        'deals': deals,
    }


def _property_dedup_key(title: str, city: str, neighborhood: str, token: str) -> str:
    if token:
        return f'token:{token.strip().lower()}'
    title = (title or '').strip().lower()
    city = (city or '').strip().lower()
    neighborhood = (neighborhood or '').strip().lower()
    if title and city and neighborhood:
        return f'title:{title}|{city}|{neighborhood}'
    return ''


def _find_existing_property(user, row: dict) -> Optional[CRMProperty]:
    token = (row.get('token') or '').strip()
    title = (row.get('title') or '').strip()
    city = (row.get('city') or '').strip()
    neighborhood = (row.get('neighborhood') or '').strip()
    if token:
        found = properties_qs(user).filter(token=token).first()
        if found:
            return found
    if not title:
        return None
    city = (city or '').strip()
    neighborhood = (neighborhood or '').strip()
    if not (city and neighborhood):
        return None
    return properties_qs(user).filter(
        title=title, city=city, neighborhood=neighborhood,
    ).first()


def _find_existing_deal(user, row: dict, customer_id: Optional[int]) -> Optional[CRMDeal]:
    title = (row.get('title') or '').strip()
    if not title:
        return None
    listing_token = (row.get('listing_token') or '').strip()
    qs = deals_qs(user).filter(title=title)
    if listing_token:
        qs = qs.filter(listing_token=listing_token)
    if customer_id:
        qs = qs.filter(customer_id=customer_id)
    return qs.first()


def _import_contacts(
    user,
    agency,
    rows: List[dict],
    *,
    merge: bool,
    dry_run: bool,
    contact_id_map: Dict[int, int],
    temp_id_counter: List[int],
) -> Dict[str, int]:
    stats = {'contacts': 0, 'skipped': 0, 'conflicts': 0}
    for row in rows or []:
        name = (row.get('name') or '').strip()
        if not name:
            stats['skipped'] += 1
            continue
        phone, phone_alt, phone_err = parse_import_phone_fields(
            row.get('phone'),
            row.get('phone_alt'),
        )
        if phone_err:
            stats['skipped'] += 1
            continue

        source_id = row.get('id')
        try:
            source_id_int = int(source_id) if source_id is not None else None
        except (TypeError, ValueError):
            source_id_int = None

        existing = None
        if phone:
            from workspace.services.crm_merge import find_duplicate_contact
            existing = find_duplicate_contact(user, name, phone)
        if existing:
            if source_id_int:
                contact_id_map[source_id_int] = existing.pk
            stats['skipped'] += 1
            if merge:
                stats['conflicts'] += 1
            continue
        if dry_run:
            if source_id_int:
                temp_id_counter[0] -= 1
                contact_id_map[source_id_int] = temp_id_counter[0]
            stats['contacts'] += 1
            continue
        gender = None
        if row.get('gender') is not None:
            from workspace.services.contact_gender import normalize_contact_gender_import
            gender = normalize_contact_gender_import(row.get('gender'))
        customer = Customer.objects.create(
            user=user,
            agency=agency,
            name=name,
            phone=phone,
            phone_alt=phone_alt or '',
            email=row.get('email') or '',
            gender=gender,
            customer_type=row.get('customer_type') or 'سرنخ',
            status=row.get('status') or 'جدید',
            priority=row.get('priority') or 'متوسط',
            source=row.get('source') or '',
            city=row.get('city') or '',
            tags=row.get('tags') or '',
            notes=row.get('notes') or '',
        )
        if source_id_int:
            contact_id_map[source_id_int] = customer.pk
        stats['contacts'] += 1
    return stats


def _import_properties(
    user,
    agency,
    rows: List[dict],
    *,
    dry_run: bool,
    property_id_map: Dict[int, int],
    seen_keys: set,
) -> Dict[str, int]:
    stats = {'properties': 0, 'skipped': 0}
    for row in rows or []:
        title = (row.get('title') or '').strip()
        if not title:
            stats['skipped'] += 1
            continue
        token = (row.get('token') or '').strip()
        city = (row.get('city') or '').strip()
        neighborhood = (row.get('neighborhood') or '').strip()
        dedup = _property_dedup_key(title, city, neighborhood, token)

        source_id = row.get('id')
        try:
            source_id_int = int(source_id) if source_id is not None else None
        except (TypeError, ValueError):
            source_id_int = None

        existing = _find_existing_property(user, row)
        if existing or (dedup and dedup in seen_keys):
            if source_id_int and existing:
                property_id_map[source_id_int] = existing.pk
            stats['skipped'] += 1
            continue
        if dry_run:
            if source_id_int:
                property_id_map[source_id_int] = -1
            if dedup:
                seen_keys.add(dedup)
            stats['properties'] += 1
            continue
        prop = CRMProperty.objects.create(
            user=user,
            agency=agency,
            title=title,
            property_type=row.get('property_type') or 'آپارتمان',
            deal_mode=row.get('deal_mode') or 'فروش',
            transaction_status=row.get('transaction_status') or 'فعال',
            city=city,
            neighborhood=neighborhood,
            sale_price=row.get('sale_price'),
            deposit=row.get('deposit'),
            monthly_rent=row.get('monthly_rent'),
            area=row.get('area'),
            token=token,
            notes=row.get('notes') or '',
        )
        if source_id_int:
            property_id_map[source_id_int] = prop.pk
        if dedup:
            seen_keys.add(dedup)
        stats['properties'] += 1
    return stats


def _import_deals(
    user,
    agency,
    rows: List[dict],
    *,
    dry_run: bool,
    contact_id_map: Dict[int, int],
    seen_deal_keys: set,
) -> Dict[str, int]:
    stats = {'deals': 0, 'skipped': 0}
    for row in rows or []:
        title = (row.get('title') or '').strip()
        if not title:
            stats['skipped'] += 1
            continue
        raw_customer_id = row.get('customer_id')
        customer_id = None
        if raw_customer_id is not None and str(raw_customer_id).strip() != '':
            try:
                source_cid = int(raw_customer_id)
            except (TypeError, ValueError):
                stats['skipped'] += 1
                continue
            customer_id = contact_id_map.get(source_cid)
            if customer_id is None:
                stats['skipped'] += 1
                continue
            if customer_id < 0:
                if dry_run:
                    customer_id = None
                else:
                    stats['skipped'] += 1
                    continue
            elif not customers_qs(user).filter(pk=customer_id).exists():
                stats['skipped'] += 1
                continue

        listing_token = (row.get('listing_token') or '').strip()
        deal_key = f'{listing_token}|{title}|{customer_id or ""}'
        existing = _find_existing_deal(user, row, customer_id)
        if existing or deal_key in seen_deal_keys:
            stats['skipped'] += 1
            continue
        if dry_run:
            seen_deal_keys.add(deal_key)
            stats['deals'] += 1
            continue
        CRMDeal.objects.create(
            user=user,
            agency=agency,
            title=title,
            stage=row.get('stage') or 'سرنخ',
            value=row.get('value'),
            probability=row.get('probability') or 0,
            customer_id=customer_id,
            listing_token=listing_token,
            commission_amount=row.get('commission_amount'),
        )
        seen_deal_keys.add(deal_key)
        stats['deals'] += 1
    return stats


def _run_import_payload(user, payload: dict, *, merge: bool, dry_run: bool) -> Dict[str, int]:
    agency = get_agency(user)
    contact_id_map: Dict[int, int] = {}
    property_id_map: Dict[int, int] = {}
    temp_id_counter = [0]
    property_keys: set = set()
    deal_keys: set = set()

    for c in properties_qs(user).only('title', 'city', 'neighborhood', 'token'):
        key = _property_dedup_key(c.title or '', c.city or '', c.neighborhood or '', c.token or '')
        if key:
            property_keys.add(key)

    for d in deals_qs(user).only('title', 'listing_token', 'customer_id'):
        deal_keys.add(f'{d.listing_token or ""}|{d.title or ""}|{d.customer_id or ""}')

    stats: Dict[str, int] = {'contacts': 0, 'properties': 0, 'deals': 0, 'skipped': 0, 'conflicts': 0}

    c = _import_contacts(
        user, agency, payload.get('contacts') or [],
        merge=merge, dry_run=dry_run, contact_id_map=contact_id_map, temp_id_counter=temp_id_counter,
    )
    p = _import_properties(
        user, agency, payload.get('properties') or [],
        dry_run=dry_run, property_id_map=property_id_map, seen_keys=property_keys,
    )
    d = _import_deals(
        user, agency, payload.get('deals') or [],
        dry_run=dry_run, contact_id_map=contact_id_map, seen_deal_keys=deal_keys,
    )
    for part in (c, p, d):
        for k, v in part.items():
            stats[k] = stats.get(k, 0) + v
    return stats


def import_crm_payload(
    user,
    payload: dict,
    *,
    merge: bool = True,
    dry_run: bool = False,
) -> Dict[str, int]:
    if dry_run:
        with transaction.atomic():
            stats = _run_import_payload(user, payload, merge=merge, dry_run=True)
            transaction.set_rollback(True)
        return stats

    with transaction.atomic():
        return _run_import_payload(user, payload, merge=merge, dry_run=False)


def record_sync_log(user, sync_type: str, stats: dict) -> Optional[CRMSyncLog]:
    agency = get_agency(user)
    if not agency:
        return None
    log = CRMSyncLog.objects.create(agency=agency, user=user, sync_type=sync_type, stats=stats)
    event = 'sync.export' if sync_type == CRMSyncLog.SYNC_EXPORT else 'sync.import'
    if sync_type != CRMSyncLog.SYNC_DRY_RUN:
        log_agency_audit(agency, user, event, stats)
    return log
