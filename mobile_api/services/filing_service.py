"""فایلینگ workspace برای API موبایل."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Min, Q
from django.utils import timezone

from mobile_api.serializers import dataset_to_dict, listing_detail_to_dict, listing_to_dict
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
    return [dataset_to_dict(ds) for ds in page_obj.object_list], {
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
    return dataset_to_dict(ds)


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
    return [listing_to_dict(lst) for lst in page_obj.object_list], {
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
    from workspace.services.listing_edit import apply_listing_edit_json
    from workspace.services.crm import upsert_property_owner

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
    except (ValueError, TypeError):
        return None
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
