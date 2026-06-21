"""ادغام مخاطبین تکراری CRM."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction

from workspace.models import (
    CRMDeal, Customer, CustomerActivity, CustomerDocument,
    CustomerListing, PropertyContact, PropertyVisit, Reminder,
)
from workspace.services.crm import log_activity, normalize_phone


def find_duplicate_groups(user, *, min_group_size: int = 2) -> List[Dict[str, Any]]:
    """گروه‌های مخاطب با تلفن یکسان."""
    phone_map: Dict[str, List[Customer]] = defaultdict(list)
    customers = Customer.objects.filter(user=user).exclude(phone='').order_by('-updated_at')

    for c in customers:
        key = normalize_phone(c.phone)
        if len(key) >= 10:
            phone_map[key].append(c)

    groups = []
    for phone, members in phone_map.items():
        if len(members) < min_group_size:
            continue
        groups.append({
            'phone': phone,
            'display_phone': members[0].phone,
            'count': len(members),
            'customers': members,
        })
    groups.sort(key=lambda g: g['count'], reverse=True)
    return groups


def find_duplicates_for_customer(customer: Customer) -> List[Customer]:
    key = normalize_phone(customer.phone)
    if len(key) < 10:
        return []
    return list(
        Customer.objects.filter(user=customer.user)
        .exclude(pk=customer.pk)
        .exclude(phone='')
        .order_by('-updated_at')
    )[:20]  # filter in python for alt phones


def _phone_matches(customer: Customer, key: str) -> bool:
    for raw in (customer.phone, customer.phone_alt):
        if raw and normalize_phone(raw) == key:
            return True
    return False


def find_duplicates_for_customer_strict(customer: Customer) -> List[Customer]:
    key = normalize_phone(customer.phone)
    if len(key) < 10:
        return []
    others = Customer.objects.filter(user=customer.user).exclude(pk=customer.pk)
    return [c for c in others if _phone_matches(c, key)]


@transaction.atomic
def merge_customers(primary: Customer, secondary: Customer) -> Customer:
    """ادغام secondary در primary — secondary حذف می‌شود."""
    if primary.user_id != secondary.user_id:
        raise ValueError('مخاطبین متعلق به کاربران مختلف هستند.')
    if primary.pk == secondary.pk:
        raise ValueError('نمی‌توان یک مخاطب را با خودش ادغام کرد.')

    secondary_name = secondary.name

    CustomerActivity.objects.filter(customer=secondary).update(customer=primary)
    Reminder.objects.filter(customer=secondary).update(customer=primary)
    CustomerDocument.objects.filter(customer=secondary).update(customer=primary)
    CRMDeal.objects.filter(customer=secondary).update(customer=primary)
    PropertyVisit.objects.filter(customer=secondary).update(customer=primary)

    for link in PropertyContact.objects.filter(customer=secondary):
        if PropertyContact.objects.filter(
            customer=primary, property=link.property, role=link.role,
        ).exists():
            link.delete()
        else:
            link.customer = primary
            link.save(update_fields=['customer'])

    for listing in CustomerListing.objects.filter(customer=secondary):
        if CustomerListing.objects.filter(
            customer=primary, token=listing.token, role=listing.role,
        ).exists():
            listing.delete()
        else:
            listing.customer = primary
            listing.save(update_fields=['customer'])

    if secondary.phone_alt and not primary.phone_alt:
        primary.phone_alt = secondary.phone_alt
    if secondary.email and not primary.email:
        primary.email = secondary.email
    if secondary.notes:
        primary.notes = '\n---\n'.join(filter(None, [primary.notes, secondary.notes]))
    if secondary.tags:
        tags = set(t.strip() for t in (primary.tags or '').split(',') if t.strip())
        tags.update(t.strip() for t in secondary.tags.split(',') if t.strip())
        primary.tags = ', '.join(sorted(tags))

    primary.save()
    secondary.delete()

    log_activity(
        primary,
        'یادداشت',
        content=f'ادغام با مخاطب «{secondary_name}»',
        title='ادغام مخاطب',
        metadata={'merged_from': secondary_name},
    )
    return primary
