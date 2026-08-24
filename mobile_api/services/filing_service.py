"""فایلینگ workspace برای API موبایل."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Min, Q
from django.utils import timezone

from mobile_api.serializers import dataset_to_dict, listing_detail_to_dict, listing_to_dict, resolve_dataset_covers_batch
from workspace.models import Dataset, Listing
from workspace.services.access import has_active_bot_license
from workspace.services.filters import (
    apply_advertiser_signal_filter,
    apply_amenity_filters,
    apply_listing_filters,
    apply_value_filter,
    get_neighborhoods_qs,
    needs_advertiser_signal_filter,
    sort_queryset,
)


def _datasets_qs(user):
    return Dataset.objects.filter(user=user, is_active=True).order_by('-created_at')


def list_datasets(user, *, page: int = 1, page_size: int = 20) -> Tuple[List[dict], dict]:
    if not has_active_bot_license(user):
        return [], {'page': page, 'page_size': page_size, 'total': 0}
    paginator = Paginator(_datasets_qs(user), page_size)
    page_obj = paginator.get_page(page)
    datasets = list(page_obj.object_list)
    covers_map = resolve_dataset_covers_batch([ds.pk for ds in datasets])
    return [
        dataset_to_dict(ds, cover_urls=covers_map.get(ds.pk, []))
        for ds in datasets
    ], {
        'page': page,
        'page_size': page_size,
        'total': paginator.count,
    }


def get_dataset(user, dataset_id: str) -> Dataset | None:
    if not has_active_bot_license(user):
        return None
    return _datasets_qs(user).filter(pk=dataset_id).first()


def delete_dataset(user, dataset_id: str) -> bool:
    """حذف نرم فایل و آگهی‌های وابسته."""
    ds = get_dataset(user, dataset_id)
    if not ds:
        return False
    with transaction.atomic():
        Listing.objects.filter(dataset=ds).delete()
        Dataset.objects.filter(pk=ds.pk, user=user).update(is_active=False)
    return True


def dataset_detail_payload(user, dataset_id: str) -> Optional[dict]:
    ds = get_dataset(user, dataset_id)
    if not ds:
        return None
    ds.touch()
    return dataset_to_dict(ds, include_stats=True)


def rename_dataset(user, dataset_id: str, name: str) -> Tuple[Optional[dict], Optional[str]]:
    ds = get_dataset(user, dataset_id)
    if not ds:
        return None, 'NOT_FOUND'
    cleaned = (name or '').strip()
    if not cleaned:
        return None, 'INVALID_NAME'
    if len(cleaned) > 255:
        return None, 'INVALID_NAME'
    ds.name = cleaned
    ds.mark_updated()
    ds.save(update_fields=['name', 'updated_at'])
    return dataset_to_dict(ds, include_stats=True), None


def delete_dataset_consultants(user, dataset_id: str) -> Tuple[Optional[dict], Optional[str], int]:
    from workspace.services.columns import consultant_q

    ds = get_dataset(user, dataset_id)
    if not ds:
        return None, 'NOT_FOUND', 0
    qs = consultant_q(ds.listings.all())
    deleted = qs.count()
    if deleted:
        qs.delete()
        ds.sync_row_count()
    return dataset_to_dict(ds, include_stats=True), None, deleted


def delete_dataset_disguised_consultants(user, dataset_id: str) -> Tuple[Optional[dict], Optional[str], int]:
    from workspace.services.advertiser_signal import disguised_consultant_listing_ids

    ds = get_dataset(user, dataset_id)
    if not ds:
        return None, 'NOT_FOUND', 0
    ids = disguised_consultant_listing_ids(ds.listings.all())
    deleted = len(ids)
    if ids:
        ds.listings.filter(pk__in=ids).delete()
        ds.sync_row_count()
    return dataset_to_dict(ds, include_stats=True), None, deleted


def _default_sort_for_dataset(ds: Optional[Dataset]) -> str:
    if not ds:
        return '-created_at'
    tx = (ds.transaction_type or '').lower()
    if 'rent' in tx or 'اجاره' in (ds.transaction_type or ''):
        return '-deposit'
    return '-price'


def _apply_unique_filter(qs):
    keep_ids = qs.values('token').annotate(keep_id=Min('id')).values_list('keep_id', flat=True)
    return qs.filter(pk__in=list(keep_ids))


def _apply_duplicates_only(qs, base_qs):
    dup_tokens = (
        base_qs.values('token')
        .annotate(c=Count('token'))
        .filter(c__gt=1)
        .values_list('token', flat=True)
    )
    return qs.filter(token__in=list(dup_tokens))


def _apply_new_only(qs, ds: Optional[Dataset]):
    since = None
    if ds is not None:
        since = getattr(ds, 'last_opened_at', None) or getattr(ds, 'last_viewed_at', None)
    if since is None:
        since = timezone.now() - timedelta(days=3)
    return qs.filter(created_at__gte=since)


def _needs_post_filters(filters: Dict[str, Any]) -> bool:
    return any(filters.get(k) for k in (
        'rooms', 'elevator', 'parking', 'storage', 'year_min', 'year_max', 'value',
    )) or needs_advertiser_signal_filter(filters)


def _value_map_for_listings(listings: List) -> Dict[int, Optional[float]]:
    if not listings:
        return {}
    try:
        from workspace.services.analyzer import compute_expected_values, enrich_dataframe
    except Exception:
        return {}
    try:
        enriched = compute_expected_values(enrich_dataframe(listings), mode='sale')
    except Exception:
        return {}
    value_map: Dict[int, Optional[float]] = {}
    for _, r in enriched.iterrows():
        score = r.get('value_score')
        if score is None:
            continue
        try:
            if score != score:
                continue
        except TypeError:
            pass
        try:
            value_map[int(r['listing_id'])] = float(score)
        except (KeyError, TypeError, ValueError):
            continue
    return value_map


def _value_map_for_dataset(ds: Dataset) -> Dict[int, float]:
    """ارزش هر آگهی نسبت به کل فایل — هم‌راستا با میزکار."""
    from workspace.services.analyzer import compute_expected_values, enrich_dataframe
    from workspace.services.display import transaction_profile

    all_listings = list(Listing.objects.filter(dataset=ds))
    if not all_listings:
        return {}
    tx = transaction_profile(ds.transaction_type or '')
    mode = 'rent' if tx.get('is_rent') and not tx.get('show_price') else 'sale'
    try:
        enriched = compute_expected_values(enrich_dataframe(all_listings), mode=mode)
    except Exception:
        return {}
    value_map: Dict[int, float] = {}
    for _, r in enriched.iterrows():
        score = r.get('value_score')
        if score is None:
            continue
        try:
            if score != score:
                continue
        except TypeError:
            pass
        try:
            value_map[int(r['listing_id'])] = float(score)
        except (KeyError, TypeError, ValueError):
            continue
    return value_map


def _listing_dict_with_value(lst: Listing, value_map: Dict[int, float]) -> dict:
    payload = listing_to_dict(lst)
    score = value_map.get(lst.pk)
    if score is None:
        return payload
    from workspace.services.display import market_tier_from_score
    from workspace.services.valuation import value_verdict

    payload['value_score'] = round(score, 1)
    payload['market_tier'] = market_tier_from_score(score)
    payload['verdict'] = value_verdict(score)
    return payload


def filter_listings_queryset(
    user,
    qs,
    filters: Dict[str, Any],
    *,
    dataset: Optional[Dataset] = None,
    default_sort: str = '-created_at',
):
    """اعمال فیلتر عمیق + sort روی QuerySet آگهی."""
    base_qs = qs
    # جستجوی متنی موبایل کمی گسترده‌تر از وب است
    q = (filters.get('q') or '').strip()
    filters_for_db = {**filters, 'q': ''}
    qs = apply_listing_filters(qs, filters_for_db, user)
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(neighborhood__icontains=q)
            | Q(city__icontains=q)
            | Q(token__icontains=q)
        )

    if filters.get('duplicates') == '1':
        qs = _apply_duplicates_only(qs, base_qs)
    if filters.get('unique') == '1':
        qs = _apply_unique_filter(qs)
    if filters.get('new_only') == '1':
        qs = _apply_new_only(qs, dataset)

    sort = filters.get('sort') or default_sort

    if _needs_post_filters(filters):
        filtered = list(qs)
        if needs_advertiser_signal_filter(filters):
            filtered = apply_advertiser_signal_filter(filtered, filters['consultant'])
        filtered = apply_amenity_filters(filtered, filters)
        if filters.get('value'):
            value_map = _value_map_for_listings(filtered)
            filtered = apply_value_filter(filtered, value_map, filters.get('value', ''))
        pk_list = [x.pk for x in filtered]
        qs = Listing.objects.filter(pk__in=pk_list)
        qs = sort_queryset(qs, sort, default_sort)
    else:
        qs = sort_queryset(qs, sort, default_sort)
    return qs


def list_listings(
    user,
    dataset_id: str,
    *,
    page: int = 1,
    page_size: int = 50,
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[dict], dict]:
    ds = get_dataset(user, dataset_id)
    if not ds:
        return [], {'page': page, 'page_size': page_size, 'total': 0, 'neighborhoods': []}

    filters = filters or {}
    default_sort = _default_sort_for_dataset(ds)
    qs = Listing.objects.filter(dataset=ds)
    qs = filter_listings_queryset(
        user, qs, filters, dataset=ds, default_sort=default_sort,
    )
    neighborhoods = get_neighborhoods_qs(Listing.objects.filter(dataset=ds))
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    value_map = _value_map_for_dataset(ds)
    items = [_listing_dict_with_value(lst, value_map) for lst in page_obj.object_list]
    return items, {
        'page': page,
        'page_size': page_size,
        'total': paginator.count,
        'neighborhoods': neighborhoods,
        'sort': filters.get('sort') or default_sort,
    }


def get_listing_detail(user, token: str, request=None) -> Optional[dict]:
    if not has_active_bot_license(user):
        return None
    lst = Listing.objects.filter(
        dataset__user=user,
        token=token,
    ).select_related('dataset').first()
    if not lst:
        return None
    return listing_detail_to_dict(lst, user=user, request=request)


def get_listing_public_share(user, token: str, request=None) -> Optional[dict]:
    if not has_active_bot_license(user):
        return None
    lst = Listing.objects.filter(dataset__user=user, token=token).first()
    if not lst:
        return None
    from workspace.services.listing_public_share import (
        get_or_create_listing_share,
        listing_public_share_to_dict,
    )
    share = get_or_create_listing_share(user, lst)
    return listing_public_share_to_dict(share, request)


def update_listing_public_share(user, token: str, payload: dict, request=None) -> Optional[dict]:
    if not has_active_bot_license(user):
        return None
    lst = Listing.objects.filter(dataset__user=user, token=token).first()
    if not lst:
        return None
    from workspace.services.listing_public_share import (
        get_or_create_listing_share,
        listing_public_share_to_dict,
        update_listing_public_share as _update_share,
    )
    share = get_or_create_listing_share(user, lst)
    _update_share(share, payload)
    return listing_public_share_to_dict(share, request)


def update_listing(user, token: str, payload: dict, request=None) -> Optional[dict]:
    if not has_active_bot_license(user):
        return None
    lst = Listing.objects.filter(
        dataset__user=user,
        token=token,
    ).select_related('dataset').first()
    if not lst:
        return None
    from workspace.services.listing_edit import (
        apply_listing_edit_json,
        listing_is_vacant,
        tenant_name_from_listing,
        tenant_phone_from_listing,
    )
    from workspace.services.crm import upsert_listing_tenant, upsert_property_owner

    try:
        apply_listing_edit_json(lst, payload)
        lst.save()
        if 'owner_phone' in payload or 'owner_name' in payload:
            upsert_property_owner(
                user,
                phone=payload.get('owner_phone') or '',
                name=payload.get('owner_name') or '',
                listing=lst,
                source='موبایل',
            )
        if any(k in payload for k in ('tenant_phone', 'tenant_name', 'is_vacant', 'vacancy_date')):
            upsert_listing_tenant(
                user,
                phone=tenant_phone_from_listing(lst),
                name=tenant_name_from_listing(lst),
                listing=lst,
                is_vacant=listing_is_vacant(lst),
                source='موبایل',
            )
    except (ValueError, TypeError):
        return None
    return listing_detail_to_dict(lst, user=user, request=request)


def delete_listing(user, token: str) -> Optional[dict]:
    """حذف آگهی متعلق به کاربر از فایلینگ."""
    if not has_active_bot_license(user):
        return None
    lst = Listing.objects.filter(
        dataset__user=user,
        token=token,
    ).select_related('dataset').first()
    if not lst:
        return None
    dataset = lst.dataset
    title = (lst.title or '')[:80]
    lst.delete()
    if dataset is not None:
        dataset.sync_row_count()
    return {'token': token, 'title': title, 'deleted': True}


def update_listing_meta(user, token: str, payload: dict, request=None) -> Optional[dict]:
    if not has_active_bot_license(user):
        return None
    lst = Listing.objects.filter(dataset__user=user, token=token).select_related('dataset').first()
    if not lst:
        return None
    from workspace.constants import LISTING_TAGS
    from workspace.models import ListingMeta

    meta, _ = ListingMeta.objects.get_or_create(user=user, token=lst.token)
    if 'note' in payload and payload.get('note') is not None:
        meta.note = str(payload.get('note') or '').strip()
    if 'tag' in payload and payload.get('tag') is not None:
        tag = str(payload.get('tag') or '').strip()
        if tag in LISTING_TAGS:
            meta.tag = tag
        elif tag == '':
            meta.tag = ''
    if 'is_favorite' in payload and payload.get('is_favorite') is not None:
        raw = payload.get('is_favorite')
        if isinstance(raw, bool):
            meta.is_favorite = raw
        else:
            meta.is_favorite = str(raw).strip().lower() in ('1', 'true', 'yes', 'on')
    meta.save()
    return listing_detail_to_dict(lst, user=user, request=request)


def toggle_listing_favorite(user, token: str, request=None) -> Optional[dict]:
    if not has_active_bot_license(user):
        return None
    lst = Listing.objects.filter(dataset__user=user, token=token).select_related('dataset').first()
    if not lst:
        return None
    from workspace.models import ListingMeta

    meta, _ = ListingMeta.objects.get_or_create(user=user, token=lst.token)
    meta.is_favorite = not bool(meta.is_favorite)
    meta.save(update_fields=['is_favorite', 'updated_at'])
    return listing_detail_to_dict(lst, user=user, request=request)


def unlink_listing_contact(user, token: str, link_id: int, request=None) -> Optional[dict]:
    if not has_active_bot_license(user):
        return None
    lst = Listing.objects.filter(dataset__user=user, token=token).select_related('dataset').first()
    if not lst:
        return None
    from workspace.services.crm import customers_linked_to_token

    link = customers_linked_to_token(user, token).filter(pk=link_id).first()
    if not link:
        return None
    link.delete()
    return listing_detail_to_dict(lst, user=user, request=request)


def export_dataset_response(user, dataset_id: str, fmt: str):
    from workspace.services.export import export_csv_response, export_excel_response, export_json_response

    if not has_active_bot_license(user):
        return None, 'LICENSE_REQUIRED'

    ds = _datasets_qs(user).filter(pk=dataset_id).first()
    if not ds:
        return None, 'NOT_FOUND'

    listings = ds.listings.all()
    safe_name = (ds.name or str(dataset_id)).replace('/', '-').replace('\\', '-')
    fmt = (fmt or 'xlsx').lower()
    if fmt == 'json':
        return export_json_response(listings, f'{safe_name}.json'), None
    if fmt == 'csv':
        return export_csv_response(listings, f'{safe_name}.csv'), None
    return export_excel_response(listings, f'{safe_name}.xlsx'), None


def search_listings(
    user,
    *,
    page: int = 1,
    page_size: int = 30,
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[dict], dict]:
    if not has_active_bot_license(user):
        return [], {'page': page, 'page_size': page_size, 'total': 0}

    filters = filters or {}
    qs = Listing.objects.filter(dataset__user=user, dataset__is_active=True).select_related('dataset')
    dataset = None
    dataset_id = filters.get('dataset_id')
    if dataset_id:
        qs = qs.filter(dataset_id=dataset_id)
        dataset = get_dataset(user, str(dataset_id))

    default_sort = _default_sort_for_dataset(dataset) if dataset else '-created_at'
    qs = filter_listings_queryset(
        user, qs, filters, dataset=dataset, default_sort=default_sort,
    )
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    items: List[dict] = []
    for lst in page_obj.object_list:
        row = listing_to_dict(lst)
        row['dataset_name'] = lst.dataset.name if lst.dataset else ''
        items.append(row)
    return items, {
        'page': page,
        'page_size': page_size,
        'total': paginator.count,
        'sort': filters.get('sort') or default_sort,
    }
