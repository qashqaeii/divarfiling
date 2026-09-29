"""همگام‌سازی CRM وب ↔ دسکتاپ — D8."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.models import CRMDeal, CRMProperty, CRMSyncLog, Customer
from workspace.services.crm_audit import log_agency_audit
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


def _import_contacts(user, agency, rows: List[dict], *, merge: bool, dry_run: bool) -> Dict[str, int]:
    stats = {'contacts': 0, 'skipped': 0, 'conflicts': 0}
    for row in rows or []:
        phone = (row.get('phone') or '').strip()
        name = (row.get('name') or '').strip()
        if not name:
            stats['skipped'] += 1
            continue
        existing = None
        if phone:
            from workspace.services.crm_merge import find_duplicate_contact
            existing = find_duplicate_contact(user, name, phone)
        if existing:
            stats['skipped'] += 1
            if merge:
                stats['conflicts'] += 1
            continue
        if dry_run:
            stats['contacts'] += 1
            continue
        gender = None
        if row.get('gender') is not None:
            from workspace.services.contact_gender import normalize_contact_gender_import
            gender = normalize_contact_gender_import(row.get('gender'))
        Customer.objects.create(
            user=user,
            agency=agency,
            name=name,
            phone=phone,
            phone_alt=row.get('phone_alt') or '',
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
        stats['contacts'] += 1
    return stats


def _import_properties(user, agency, rows: List[dict], *, dry_run: bool) -> Dict[str, int]:
    stats = {'properties': 0, 'skipped': 0}
    for row in rows or []:
        title = (row.get('title') or '').strip()
        if not title:
            stats['skipped'] += 1
            continue
        if dry_run:
            stats['properties'] += 1
            continue
        CRMProperty.objects.create(
            user=user,
            agency=agency,
            title=title,
            property_type=row.get('property_type') or 'آپارتمان',
            deal_mode=row.get('deal_mode') or 'فروش',
            transaction_status=row.get('transaction_status') or 'فعال',
            city=row.get('city') or '',
            neighborhood=row.get('neighborhood') or '',
            sale_price=row.get('sale_price'),
            deposit=row.get('deposit'),
            monthly_rent=row.get('monthly_rent'),
            area=row.get('area'),
            token=row.get('token') or '',
            notes=row.get('notes') or '',
        )
        stats['properties'] += 1
    return stats


def _import_deals(user, agency, rows: List[dict], *, dry_run: bool) -> Dict[str, int]:
    stats = {'deals': 0, 'skipped': 0}
    for row in rows or []:
        title = (row.get('title') or '').strip()
        if not title:
            stats['skipped'] += 1
            continue
        customer_id = row.get('customer_id')
        if customer_id and not customers_qs(user).filter(pk=customer_id).exists():
            stats['skipped'] += 1
            continue
        if dry_run:
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
            listing_token=row.get('listing_token') or '',
            commission_amount=row.get('commission_amount'),
        )
        stats['deals'] += 1
    return stats


def import_crm_payload(
    user,
    payload: dict,
    *,
    merge: bool = True,
    dry_run: bool = False,
) -> Dict[str, int]:
    agency = get_agency(user)
    stats: Dict[str, int] = {'contacts': 0, 'properties': 0, 'deals': 0, 'skipped': 0, 'conflicts': 0}
    c = _import_contacts(user, agency, payload.get('contacts') or [], merge=merge, dry_run=dry_run)
    p = _import_properties(user, agency, payload.get('properties') or [], dry_run=dry_run)
    d = _import_deals(user, agency, payload.get('deals') or [], dry_run=dry_run)
    for k, v in c.items():
        stats[k] = stats.get(k, 0) + v
    for k, v in p.items():
        stats[k] = stats.get(k, 0) + v
    for k, v in d.items():
        stats[k] = stats.get(k, 0) + v
    return stats


def record_sync_log(user, sync_type: str, stats: dict) -> Optional[CRMSyncLog]:
    agency = get_agency(user)
    if not agency:
        return None
    log = CRMSyncLog.objects.create(agency=agency, user=user, sync_type=sync_type, stats=stats)
    event = 'sync.export' if sync_type == CRMSyncLog.SYNC_EXPORT else 'sync.import'
    if sync_type != CRMSyncLog.SYNC_DRY_RUN:
        log_agency_audit(agency, user, event, stats)
    return log
