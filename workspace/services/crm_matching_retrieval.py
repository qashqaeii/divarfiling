"""بازیابی صفحه‌بندی‌شده تطبیق — ایندکس سبک + کش."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from workspace.models import Customer
from workspace.services.crm_matching_index import (
    MATCH_ITERATOR_CHUNK_SIZE,
    ScoredRef,
    build_crm_index,
    build_divar_index,
    customer_match_fingerprint,
    get_or_build_index,
    hydrate_crm_matches,
    hydrate_divar_matches,
    page_has_more,
    property_match_fingerprint,
    slice_refs,
    user_contacts_catalog_extra,
    user_crm_properties_catalog_extra,
    user_divar_listings_catalog_extra,
    _index_cache_key,
)

MATCH_PAGE_SIZE_DEFAULT = 24


def collect_customer_match_results(
    customer: Customer,
    user,
    *,
    divar_enabled: bool,
    dataset_id=None,
    crm_min_score: int,
    divar_min_score: int,
    crm_page: int = 1,
    divar_page: int = 1,
    page_size: int = MATCH_PAGE_SIZE_DEFAULT,
    rebuild_index: bool = False,
) -> Dict[str, Any]:
    fp = customer_match_fingerprint(customer)
    user_id = int(user.pk)
    customer_id = int(customer.pk)
    ds = str(dataset_id or '')

    crm_key = _index_cache_key(
        user_id=user_id, scope='cust', scope_id=customer_id,
        source='crm', fingerprint=fp, dataset_id=ds,
        extra=user_crm_properties_catalog_extra(user),
    )
    crm_refs, _ = get_or_build_index(
        crm_key,
        lambda: build_crm_index(customer, user, min_score=crm_min_score),
        rebuild=rebuild_index,
    )
    crm_total = len(crm_refs)
    crm_slice = slice_refs(crm_refs, crm_page, page_size)
    crm_out = hydrate_crm_matches(
        customer, user, crm_slice, min_score=crm_min_score,
    )

    divar_refs: List[ScoredRef] = []
    divar_out: List[Dict[str, Any]] = []
    divar_total = 0
    if divar_enabled:
        divar_key = _index_cache_key(
            user_id=user_id, scope='cust', scope_id=customer_id,
            source='divar', fingerprint=fp, dataset_id=ds,
            extra=user_divar_listings_catalog_extra(user, dataset_id),
        )
        divar_refs, _ = get_or_build_index(
            divar_key,
            lambda: build_divar_index(
                customer, user, min_score=divar_min_score, dataset_id=dataset_id,
            ),
            rebuild=rebuild_index,
        )
        divar_total = len(divar_refs)
        divar_slice = slice_refs(divar_refs, divar_page, page_size)
        divar_out = hydrate_divar_matches(
            customer, user, divar_slice,
            min_score=divar_min_score, dataset_id=dataset_id,
        )

    return {
        'crm_matches': crm_out,
        'divar_matches': divar_out,
        'crm_total_count': crm_total,
        'divar_total_count': divar_total,
        'total_count': crm_total + divar_total,
        'crm_page': crm_page,
        'divar_page': divar_page,
        'match_page_size': page_size,
        'crm_has_more': page_has_more(crm_total, crm_page, page_size),
        'divar_has_more': page_has_more(divar_total, divar_page, page_size),
    }


def collect_property_contact_matches(
    prop,
    user,
    *,
    page: int = 1,
    page_size: int = MATCH_PAGE_SIZE_DEFAULT,
    rebuild_index: bool = False,
) -> Dict[str, Any]:
    from workspace.services.crm_matching import (
        _customer_match_candidates_filtered_qs,
        _score_customer_for_property,
    )
    from workspace.services.crm_matching_index import (
        get_or_build_index,
        page_has_more,
        slice_refs,
    )

    fp = property_match_fingerprint(prop)
    user_id = int(user.pk)
    prop_id = int(prop.pk)

    def _build() -> List[ScoredRef]:
        refs: List[ScoredRef] = []
        qs = _customer_match_candidates_filtered_qs(prop, user).order_by('pk')
        for cust in qs.iterator(chunk_size=MATCH_ITERATOR_CHUNK_SIZE):
            item = _score_customer_for_property(cust, prop)
            if item:
                refs.append(ScoredRef(int(item['score']), int(cust.pk)))
        return refs

    cache_key = _index_cache_key(
        user_id=user_id, scope='prop', scope_id=prop_id,
        source='contacts', fingerprint=fp,
        extra=user_contacts_catalog_extra(user),
    )
    refs, _ = get_or_build_index(cache_key, _build, rebuild=rebuild_index)
    total = len(refs)
    slice_rows = slice_refs(refs, page, page_size)

    from workspace.models import Customer

    ids = [r.item_id for r in slice_rows]
    customers = {c.pk: c for c in Customer.objects.filter(user=user, pk__in=ids)}

    page_items = []
    for ref in slice_rows:
        cust = customers.get(ref.item_id)
        if not cust:
            continue
        scored = _score_customer_for_property(cust, prop)
        if scored:
            page_items.append(scored)

    return {
        'matches': page_items,
        'total_count': total,
        'match_page': page,
        'match_page_size': page_size,
        'has_more': page_has_more(total, page, page_size),
    }


# سازگاری با تست‌ها و فراخوانی‌های قدیمی
def collect_crm_property_matches(customer: Customer, user, *, min_score: int) -> List[Dict[str, Any]]:
    refs = build_crm_index(customer, user, min_score=min_score)
    return hydrate_crm_matches(customer, user, refs, min_score=min_score)


def collect_divar_listing_matches(
    customer: Customer,
    user,
    *,
    min_score: int,
    dataset_id=None,
) -> List[Dict[str, Any]]:
    refs = build_divar_index(
        customer, user, min_score=min_score, dataset_id=dataset_id,
    )
    return hydrate_divar_matches(
        customer, user, refs, min_score=min_score, dataset_id=dataset_id,
    )


def paginate_match_list(items, *, page: int, page_size: int):
    total = len(items)
    if page < 1:
        page = 1
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total
