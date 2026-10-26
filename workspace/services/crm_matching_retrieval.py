"""بازیابی کامل نتایج تطبیق — بدون سقف اسکن دلخواه."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from workspace.models import Customer

MATCH_PAGE_SIZE_DEFAULT = 24
MATCH_ITERATOR_CHUNK_SIZE = 500


def _sort_match_items(items: List[Dict[str, Any]]) -> None:
    items.sort(
        key=lambda x: (
            -int(x.get('score') or 0),
            -(x.get('property_id') or x.get('id') or 0),
        ),
    )


def _sort_divar_items(items: List[Dict[str, Any]]) -> None:
    items.sort(
        key=lambda x: (
            -int(x.get('score') or 0),
            -(x.get('listing_id') or x.get('id') or 0),
        ),
    )


def paginate_match_list(
    items: List[Dict[str, Any]],
    *,
    page: int,
    page_size: int,
) -> Tuple[List[Dict[str, Any]], int]:
    total = len(items)
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = MATCH_PAGE_SIZE_DEFAULT
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total


def collect_crm_property_matches(
    customer: Customer,
    user,
    *,
    min_score: int,
) -> List[Dict[str, Any]]:
    from workspace.services.crm_matching import (
        _crm_match_candidates_filtered_qs,
        _crm_match_compatible,
        _score_crm_property,
    )

    scored: List[Dict[str, Any]] = []
    qs = _crm_match_candidates_filtered_qs(customer, user).order_by('pk')
    for prop in qs.iterator(chunk_size=MATCH_ITERATOR_CHUNK_SIZE):
        if not _crm_match_compatible(customer, prop):
            continue
        item = _score_crm_property(customer, prop)
        if item and int(item.get('score') or 0) >= min_score:
            scored.append(item)
    _sort_match_items(scored)
    return scored


def collect_divar_listing_matches(
    customer: Customer,
    user,
    *,
    min_score: int,
    dataset_id=None,
) -> List[Dict[str, Any]]:
    from workspace.services.crm_matching import (
        _divar_match_candidates_filtered_qs,
        _listing_is_genuine_owner,
        _listing_match_compatible,
        _score_listing,
    )

    scored: List[Dict[str, Any]] = []
    qs = _divar_match_candidates_filtered_qs(
        customer, user, dataset_id=dataset_id,
    ).order_by('pk')
    for listing in qs.iterator(chunk_size=MATCH_ITERATOR_CHUNK_SIZE):
        if not _listing_is_genuine_owner(listing):
            continue
        if not _listing_match_compatible(customer, listing):
            continue
        item = _score_listing(customer, listing)
        if item and int(item.get('score') or 0) >= min_score:
            scored.append(item)
    _sort_divar_items(scored)
    return scored


def collect_customer_match_results(
    customer: Customer,
    user,
    *,
    divar_enabled: bool,
    dataset_id=None,
    crm_min_score: int,
    divar_min_score: int,
    page: int = 1,
    page_size: int = MATCH_PAGE_SIZE_DEFAULT,
    paginate: bool = True,
) -> Dict[str, Any]:
    crm_all = collect_crm_property_matches(
        customer, user, min_score=crm_min_score,
    )
    divar_all: List[Dict[str, Any]] = []
    if divar_enabled:
        divar_all = collect_divar_listing_matches(
            customer, user, min_score=divar_min_score, dataset_id=dataset_id,
        )

    crm_total = len(crm_all)
    divar_total = len(divar_all)
    if paginate:
        crm_out, _ = paginate_match_list(crm_all, page=page, page_size=page_size)
        divar_out, _ = paginate_match_list(divar_all, page=page, page_size=page_size)
        crm_has_more = (page * page_size) < crm_total
        divar_has_more = (page * page_size) < divar_total
    else:
        crm_out = crm_all
        divar_out = divar_all
        crm_has_more = False
        divar_has_more = False

    return {
        'crm_matches': crm_out,
        'divar_matches': divar_out,
        'crm_total_count': crm_total,
        'divar_total_count': divar_total,
        'total_count': crm_total + divar_total,
        'match_page': page,
        'match_page_size': page_size if paginate else crm_total + divar_total,
        'crm_has_more': crm_has_more,
        'divar_has_more': divar_has_more,
    }


def collect_property_contact_matches(
    prop,
    user,
    *,
    page: int = 1,
    page_size: int = MATCH_PAGE_SIZE_DEFAULT,
    paginate: bool = True,
) -> Dict[str, Any]:
    from workspace.services.crm_matching import (
        _customer_match_candidates_filtered_qs,
        _score_customer_for_property,
    )

    scored: List[Dict[str, Any]] = []
    qs = _customer_match_candidates_filtered_qs(prop, user).order_by('pk')
    for customer in qs.iterator(chunk_size=MATCH_ITERATOR_CHUNK_SIZE):
        item = _score_customer_for_property(customer, prop)
        if item:
            scored.append(item)
    scored.sort(
        key=lambda x: (
            -int(x.get('score') or 0),
            -(x.get('customer_id') or 0),
        ),
    )
    total = len(scored)
    if paginate:
        page_items, _ = paginate_match_list(scored, page=page, page_size=page_size)
        has_more = (page * page_size) < total
        effective_size = page_size
    else:
        page_items = scored
        has_more = False
        effective_size = total
    return {
        'matches': page_items,
        'total_count': total,
        'match_page': page,
        'match_page_size': effective_size,
        'has_more': has_more,
    }
