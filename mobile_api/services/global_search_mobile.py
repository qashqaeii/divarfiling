"""Unified global search for Mobile API — Epic 03."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db.models import Q

from workspace.models import Dataset, Listing
from workspace.services.crm import global_search
from workspace.services.crm_deals import filter_deals
from workspace.services.access import has_active_bot_license


GROUP_LABELS = {
    'contacts': 'مخاطبین',
    'properties': 'فایل‌های شخصی',
    'deals': 'معاملات',
    'listings': 'آگهی‌ها',
    'datasets': 'فایلینگ',
}

MIN_QUERY_LEN = 2
DEFAULT_LIMIT = 8
MAX_LIMIT = 15


def _clamp_limit(raw: Optional[str]) -> int:
    try:
        n = int(raw or DEFAULT_LIMIT)
    except (TypeError, ValueError):
        n = DEFAULT_LIMIT
    return max(1, min(n, MAX_LIMIT))


def _item(
    *,
    entity_type: str,
    entity_id: str,
    title: str,
    subtitle: str = '',
    meta: Optional[Dict[str, Any]] = None,
    destination: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        'type': entity_type,
        'id': entity_id,
        'title': title,
        'subtitle': subtitle,
        'meta': meta or {},
        'destination': destination or {'kind': entity_type, 'id': entity_id},
    }


def _search_listings(user, q: str, limit: int) -> List[Dict[str, Any]]:
    if not has_active_bot_license(user):
        return []
    qs = (
        Listing.objects.filter(dataset__user=user, dataset__is_active=True)
        .select_related('dataset')
        .filter(
            Q(title__icontains=q)
            | Q(token__icontains=q)
            | Q(neighborhood__icontains=q)
            | Q(city__icontains=q)
        )
        .order_by('-created_at')[:limit]
    )
    rows: List[Dict[str, Any]] = []
    for lst in qs:
        ds_name = lst.dataset.name if lst.dataset else ''
        rows.append(
            _item(
                entity_type='listing',
                entity_id=lst.token,
                title=lst.title or lst.token or 'آگهی',
                subtitle=' · '.join(p for p in (lst.neighborhood, ds_name) if p),
                meta={'dataset_id': str(lst.dataset_id) if lst.dataset_id else '', 'dataset_name': ds_name},
                destination={'kind': 'listing', 'token': lst.token},
            )
        )
    return rows


def _search_datasets(user, q: str, limit: int) -> List[Dict[str, Any]]:
    if not has_active_bot_license(user):
        return []
    qs = (
        Dataset.objects.filter(user=user, is_active=True)
        .filter(name__icontains=q)
        .order_by('-created_at')[:limit]
    )
    return [
        _item(
            entity_type='dataset',
            entity_id=str(ds.pk),
            title=ds.name or 'فایل',
            subtitle=ds.city or '',
            meta={'listing_count': ds.listings.count()},
            destination={'kind': 'dataset', 'dataset_id': str(ds.pk)},
        )
        for ds in qs
    ]


def _search_deals(user, q: str, limit: int) -> List[Dict[str, Any]]:
    qs = filter_deals(user, {'q': q, 'sort': '-updated_at'})[:limit]
    rows: List[Dict[str, Any]] = []
    for deal in qs:
        subtitle = deal.customer.name if deal.customer else ''
        if deal.stage:
            subtitle = ' · '.join(p for p in (subtitle, deal.stage) if p)
        rows.append(
            _item(
                entity_type='deal',
                entity_id=str(deal.pk),
                title=deal.title or 'معامله',
                subtitle=subtitle,
                meta={'stage': deal.stage or ''},
                destination={'kind': 'deal', 'deal_id': deal.pk},
            )
        )
    return rows


def global_search_mobile_payload(user, query: str, *, limit: Optional[int] = None) -> Dict[str, Any]:
    q = (query or '').strip()
    lim = limit or DEFAULT_LIMIT
    if len(q) < MIN_QUERY_LEN:
        return {'query': q, 'groups': [], 'min_query_length': MIN_QUERY_LEN}

    base = global_search(user, q, limit=lim)
    groups: List[Dict[str, Any]] = []

    contact_items = [
        _item(
            entity_type='contact',
            entity_id=str(c.pk),
            title=c.name or 'مخاطب',
            subtitle=' · '.join(p for p in (c.phone, c.customer_type) if p),
            meta={'phone': c.phone or ''},
            destination={'kind': 'contact', 'contact_id': c.pk},
        )
        for c in base.get('contacts') or []
    ]
    if contact_items:
        groups.append({'key': 'contacts', 'label': GROUP_LABELS['contacts'], 'items': contact_items})

    property_items = [
        _item(
            entity_type='property',
            entity_id=str(p.pk),
            title=p.title or 'فایل شخصی',
            subtitle=' · '.join(p for p in (p.city, p.deal_mode) if p),
            meta={'transaction_status': p.transaction_status or ''},
            destination={'kind': 'property', 'property_id': p.pk},
        )
        for p in base.get('properties') or []
    ]
    if property_items:
        groups.append({'key': 'properties', 'label': GROUP_LABELS['properties'], 'items': property_items})

    deal_items = _search_deals(user, q, lim)
    if deal_items:
        groups.append({'key': 'deals', 'label': GROUP_LABELS['deals'], 'items': deal_items})

    listing_items = _search_listings(user, q, lim)
    if listing_items:
        groups.append({'key': 'listings', 'label': GROUP_LABELS['listings'], 'items': listing_items})

    dataset_items = _search_datasets(user, q, lim)
    if dataset_items:
        groups.append({'key': 'datasets', 'label': GROUP_LABELS['datasets'], 'items': dataset_items})

    return {'query': q, 'groups': groups, 'min_query_length': MIN_QUERY_LEN}
