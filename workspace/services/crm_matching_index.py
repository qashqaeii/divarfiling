"""ایندکس سبک امتیاز تطبیق — اسکن کامل، نگهداری (score, id) در کش."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from django.core.cache import cache

from workspace.models import Customer

MATCH_INDEX_CACHE_TTL = 600
MATCH_ITERATOR_CHUNK_SIZE = 500


@dataclass(frozen=True)
class ScoredRef:
    score: int
    item_id: int

    def as_tuple(self) -> Tuple[int, int]:
        return (self.score, self.item_id)

    @classmethod
    def from_tuple(cls, raw: Tuple[int, int]) -> ScoredRef:
        return cls(int(raw[0]), int(raw[1]))


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def customer_match_fingerprint(customer: Customer) -> str:
    payload = {
        'tol': customer.matching_tolerance_percent,
        'areas': customer.areas or '',
        'budget_min': customer.budget_min,
        'budget_max': customer.budget_max,
        'deposit_min': customer.deposit_min,
        'deposit_max': customer.deposit_max,
        'rent_min': customer.rent_min,
        'rent_max': customer.rent_max,
        'min_area': customer.min_area,
        'max_area': customer.max_area,
        'property_type': customer.property_type or '',
        'property_types': customer.property_types or [],
        'rooms_min': customer.rooms_min,
        'rooms_max': customer.rooms_max,
        'year_min': customer.year_min,
        'year_max': customer.year_max,
        'floor_min': customer.floor_min,
        'floor_max': customer.floor_max,
        'want_parking': customer.want_parking,
        'want_storage': customer.want_storage,
        'want_elevator': customer.want_elevator,
        'customer_type': customer.customer_type or '',
        'builder_buy_areas': customer.builder_buy_areas or '',
        'builder_buy_budget_min': customer.builder_buy_budget_min,
        'builder_buy_budget_max': customer.builder_buy_budget_max,
        'builder_buy_min_area': customer.builder_buy_min_area,
        'builder_buy_max_area': customer.builder_buy_max_area,
        'builder_buy_property_types': customer.builder_buy_property_types or '',
    }
    digest = hashlib.sha256(_stable_json(payload).encode('utf-8')).hexdigest()
    return digest[:20]


def property_match_fingerprint(prop) -> str:
    payload = {
        'sale': prop.sale_price,
        'deposit': prop.deposit,
        'rent': prop.monthly_rent,
        'area': prop.area,
        'deal': prop.deal_mode or '',
        'type': prop.property_type or '',
        'hood': prop.neighborhood or '',
        'city': prop.city or '',
    }
    digest = hashlib.sha256(_stable_json(payload).encode('utf-8')).hexdigest()
    return digest[:20]


def _catalog_token(raw: str) -> str:
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return digest[:12]


def user_contacts_catalog_extra(user) -> str:
    """برای ایندکس ملک→مخاطب — وقتی پرونده مخاطبین عوض می‌شود."""
    from django.db.models import Count, Max

    from workspace.models import Customer

    row = Customer.objects.filter(user=user).aggregate(
        n=Count('pk'),
        mx=Max('updated_at'),
        mp=Max('pk'),
    )
    return _catalog_token(
        f"ct:{row['n'] or 0}:{row['mx'] or ''}:{row['mp'] or 0}",
    )


def user_crm_properties_catalog_extra(user) -> str:
    """برای ایندکس مخاطب→فایل شخصی."""
    from django.db.models import Count, Max

    from workspace.services.crm_scope import properties_qs

    row = properties_qs(user).aggregate(
        n=Count('pk'),
        mx=Max('updated_at'),
        mp=Max('pk'),
    )
    return _catalog_token(
        f"pr:{row['n'] or 0}:{row['mx'] or ''}:{row['mp'] or 0}",
    )


def user_divar_listings_catalog_extra(user, dataset_id=None) -> str:
    """برای ایندکس مخاطب→دیوار."""
    from django.db.models import Count, Max

    from workspace.services.crm_matching import _divar_listings_base_qs

    qs = _divar_listings_base_qs(user, dataset_id=dataset_id)
    row = qs.aggregate(
        n=Count('pk'),
        mp=Max('pk'),
        mx_created=Max('created_at'),
        mx_published=Max('published_at'),
    )
    return _catalog_token(
        f"dv:{dataset_id or ''}:{row['n'] or 0}:{row['mp'] or 0}:"
        f"{row['mx_created'] or ''}:{row['mx_published'] or ''}",
    )


def _index_cache_key(
    *,
    user_id: int,
    scope: str,
    scope_id: int,
    source: str,
    fingerprint: str,
    dataset_id: str = '',
    extra: str = '',
) -> str:
    ds = dataset_id or '-'
    ex = extra or '-'
    return f'crm_match_idx:v1:{user_id}:{scope}:{scope_id}:{source}:{fingerprint}:{ds}:{ex}'


def invalidate_customer_match_index(user_id: int, customer_id: int) -> None:
    cache.delete_many([
        _index_cache_key(
            user_id=user_id, scope='c', scope_id=customer_id,
            source='crm', fingerprint='*',
        ),
    ])


def _sort_refs(refs: List[ScoredRef]) -> None:
    refs.sort(key=lambda r: (-r.score, -r.item_id))


def _refs_to_cache(refs: Sequence[ScoredRef]) -> List[Tuple[int, int]]:
    return [r.as_tuple() for r in refs]


def _refs_from_cache(raw: List[Tuple[int, int]]) -> List[ScoredRef]:
    return [ScoredRef.from_tuple(t) for t in raw]


def slice_refs(refs: Sequence[ScoredRef], page: int, page_size: int) -> List[ScoredRef]:
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 24
    start = (page - 1) * page_size
    end = start + page_size
    return list(refs[start:end])


def page_has_more(total: int, page: int, page_size: int) -> bool:
    if page < 1:
        page = 1
    return (page * page_size) < total


def get_or_build_index(
    cache_key: str,
    builder: Callable[[], List[ScoredRef]],
    *,
    rebuild: bool = False,
) -> Tuple[List[ScoredRef], bool]:
    """برگشت: (refs, از_کش)."""
    if not rebuild:
        cached = cache.get(cache_key)
        if cached is not None:
            return _refs_from_cache(cached), True
    refs = builder()
    _sort_refs(refs)
    cache.set(cache_key, _refs_to_cache(refs), MATCH_INDEX_CACHE_TTL)
    return refs, False


def build_crm_index(customer: Customer, user, *, min_score: int) -> List[ScoredRef]:
    from workspace.services.crm_matching import (
        _crm_match_candidates_filtered_qs,
        _crm_match_compatible,
        _score_crm_property,
    )

    refs: List[ScoredRef] = []
    qs = _crm_match_candidates_filtered_qs(customer, user).order_by('pk')
    for prop in qs.iterator(chunk_size=MATCH_ITERATOR_CHUNK_SIZE):
        if not _crm_match_compatible(customer, prop):
            continue
        item = _score_crm_property(customer, prop)
        if not item:
            continue
        score = int(item.get('score') or 0)
        if score >= min_score:
            refs.append(ScoredRef(score, int(prop.pk)))
    return refs


def build_divar_index(
    customer: Customer,
    user,
    *,
    min_score: int,
    dataset_id=None,
) -> List[ScoredRef]:
    from workspace.services.crm_matching import (
        _divar_match_candidates_filtered_qs,
        _listing_is_genuine_owner,
        _listing_match_compatible,
        _score_listing,
    )

    refs: List[ScoredRef] = []
    qs = _divar_match_candidates_filtered_qs(
        customer, user, dataset_id=dataset_id,
    ).order_by('pk')
    for listing in qs.iterator(chunk_size=MATCH_ITERATOR_CHUNK_SIZE):
        if not _listing_is_genuine_owner(listing):
            continue
        if not _listing_match_compatible(customer, listing):
            continue
        item = _score_listing(customer, listing)
        if not item:
            continue
        score = int(item.get('score') or 0)
        if score >= min_score:
            refs.append(ScoredRef(score, int(listing.pk)))
    return refs


def hydrate_crm_matches(
    customer: Customer,
    user,
    refs: Sequence[ScoredRef],
) -> List[Dict[str, Any]]:
    from workspace.services.crm_matching import _score_crm_property
    from workspace.services.crm_scope import properties_qs

    if not refs:
        return []
    ids = [r.item_id for r in refs]
    props = {
        p.pk: p
        for p in properties_qs(user).filter(pk__in=ids)
    }
    out: List[Dict[str, Any]] = []
    for ref in refs:
        prop = props.get(ref.item_id)
        if not prop:
            continue
        item = _score_crm_property(customer, prop)
        if item and int(item.get('score') or 0) >= ref.score:
            out.append(item)
    return out


def hydrate_divar_matches(
    customer: Customer,
    user,
    refs: Sequence[ScoredRef],
) -> List[Dict[str, Any]]:
    from workspace.models import Listing
    from workspace.services.crm_matching import _score_listing

    if not refs:
        return []
    ids = [r.item_id for r in refs]
    listings = {
        lst.pk: lst
        for lst in Listing.objects.filter(pk__in=ids).select_related('dataset')
    }
    out: List[Dict[str, Any]] = []
    for ref in refs:
        listing = listings.get(ref.item_id)
        if not listing:
            continue
        item = _score_listing(customer, listing)
        if item and int(item.get('score') or 0) >= ref.score:
            out.append(item)
    return out


def iter_scored_crm_for_notify(
    customer: Customer,
    user,
    *,
    min_score: int,
    engine_min_score: int,
) -> Iterator[Dict[str, Any]]:
    """اسکن کامل — yield فقط موارد قوی بدون نگهداری همه در RAM."""
    from workspace.services.crm_matching import (
        _crm_match_candidates_filtered_qs,
        _crm_match_compatible,
        _score_crm_property,
    )

    qs = _crm_match_candidates_filtered_qs(customer, user).order_by('pk')
    for prop in qs.iterator(chunk_size=MATCH_ITERATOR_CHUNK_SIZE):
        if not _crm_match_compatible(customer, prop):
            continue
        item = _score_crm_property(customer, prop)
        if not item:
            continue
        score = int(item.get('score') or 0)
        if score < engine_min_score or score < min_score:
            continue
        yield item


def iter_scored_divar_for_notify(
    customer: Customer,
    user,
    *,
    min_score: int,
    engine_min_score: int,
    dataset_id=None,
) -> Iterator[Dict[str, Any]]:
    from workspace.services.crm_matching import (
        _divar_match_candidates_filtered_qs,
        _listing_is_genuine_owner,
        _listing_match_compatible,
        _score_listing,
    )

    qs = _divar_match_candidates_filtered_qs(
        customer, user, dataset_id=dataset_id,
    ).order_by('pk')
    for listing in qs.iterator(chunk_size=MATCH_ITERATOR_CHUNK_SIZE):
        if not _listing_is_genuine_owner(listing):
            continue
        if not _listing_match_compatible(customer, listing):
            continue
        item = _score_listing(customer, listing)
        if not item:
            continue
        score = int(item.get('score') or 0)
        if score < engine_min_score or score < min_score:
            continue
        yield item


def collect_notify_candidates(
    customer: Customer,
    user,
    *,
    divar_enabled: bool,
    min_score: int,
    crm_engine_min: int,
    divar_engine_min: int,
    skip_keys: set,
    max_hold: int = 48,
    dataset_id=None,
) -> List[Dict[str, Any]]:
    """بهترین پیشنهادهای جدید — اسکن کامل، نگهداری acot."""
    held: List[Dict[str, Any]] = []

    def _match_key(match: Dict[str, Any]) -> str:
        if match.get('source') == 'crm':
            return f'crm:{match.get("property_id")}'
        return f'divar:{match.get("token")}'

    def consider(item: Dict[str, Any]) -> None:
        if int(item.get('score') or 0) < min_score:
            return
        if _match_key(item) in skip_keys:
            return
        held.append(item)
        if len(held) > max_hold:
            held.sort(key=lambda x: -int(x.get('score') or 0))
            del held[max_hold:]

    for item in iter_scored_crm_for_notify(
        customer, user, min_score=min_score, engine_min_score=crm_engine_min,
    ):
        consider(item)
    if divar_enabled:
        for item in iter_scored_divar_for_notify(
            customer, user,
            min_score=min_score,
            engine_min_score=divar_engine_min,
            dataset_id=dataset_id,
        ):
            consider(item)
    held.sort(key=lambda x: -int(x.get('score') or 0))
    return held
