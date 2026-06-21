"""همگام‌سازی CRM وب ↔ دسکتاپ — D8."""
from __future__ import annotations

from typing import Any, Dict, List

from workspace.models import CRMDeal, CRMProperty, Customer
from workspace.services.crm_scope import customers_qs, deals_qs, properties_qs, get_agency


def export_crm_payload(user) -> Dict[str, Any]:
    agency = get_agency(user)
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
    return {
        'version': 1,
        'agency_id': agency.pk if agency else None,
        'contacts': contacts,
        'properties': properties,
        'deals': deals,
    }


def import_crm_payload(user, payload: dict, *, merge: bool = True) -> Dict[str, int]:
    agency = get_agency(user)
    stats = {'contacts': 0, 'properties': 0, 'skipped': 0}
    for row in payload.get('contacts') or []:
        phone = (row.get('phone') or '').strip()
        name = (row.get('name') or '').strip()
        if not name:
            stats['skipped'] += 1
            continue
        existing = None
        if phone:
            existing = customers_qs(user).filter(phone=phone).first()
        if existing and merge:
            stats['skipped'] += 1
            continue
        Customer.objects.create(
            user=user,
            agency=agency,
            name=name,
            phone=phone,
            phone_alt=row.get('phone_alt') or '',
            email=row.get('email') or '',
            customer_type=row.get('customer_type') or 'سرنخ',
            status=row.get('status') or 'جدید',
            priority=row.get('priority') or 'متوسط',
            source=row.get('source') or '',
            city=row.get('city') or '',
            tags=row.get('tags') or '',
            notes=row.get('notes') or '',
        )
        stats['contacts'] += 1
    for row in payload.get('properties') or []:
        title = (row.get('title') or '').strip()
        if not title:
            stats['skipped'] += 1
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
