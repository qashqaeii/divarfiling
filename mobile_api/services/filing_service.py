"""فایلینگ workspace برای API موبایل."""
from __future__ import annotations

from typing import List, Optional, Tuple

from django.core.paginator import Paginator
from django.db.models import Q

from mobile_api.serializers import dataset_to_dict, listing_detail_to_dict, listing_to_dict
from workspace.models import Dataset, Listing
from workspace.services.access import has_active_bot_license


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


def dataset_detail_payload(user, dataset_id: str) -> Optional[dict]:
    ds = get_dataset(user, dataset_id)
    if not ds:
        return None
    return dataset_to_dict(ds)


def list_listings(
    user,
    dataset_id: str,
    *,
    page: int = 1,
    page_size: int = 50,
    q: str = '',
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    area_min: Optional[int] = None,
    area_max: Optional[int] = None,
    rooms: Optional[int] = None,
) -> Tuple[List[dict], dict]:
    ds = get_dataset(user, dataset_id)
    if not ds:
        return [], {'page': page, 'page_size': page_size, 'total': 0}
    qs = Listing.objects.filter(dataset=ds).order_by('-created_at')
    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(neighborhood__icontains=q) | Q(token__icontains=q)
        )
    if price_min is not None:
        qs = qs.filter(price__gte=price_min)
    if price_max is not None:
        qs = qs.filter(price__lte=price_max)
    if area_min is not None:
        qs = qs.filter(area__gte=area_min)
    if area_max is not None:
        qs = qs.filter(area__lte=area_max)
    if rooms is not None:
        qs = qs.filter(rooms__icontains=str(rooms))
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    return [listing_to_dict(lst) for lst in page_obj.object_list], {
        'page': page,
        'page_size': page_size,
        'total': paginator.count,
    }


def get_listing_detail(user, token: str) -> Optional[dict]:
    if not has_active_bot_license(user):
        return None
    lst = Listing.objects.filter(
        dataset__user=user,
        token=token,
    ).select_related('dataset').first()
    if not lst:
        return None
    return listing_detail_to_dict(lst)


def update_listing(user, token: str, payload: dict) -> Optional[dict]:
    if not has_active_bot_license(user):
        return None
    lst = Listing.objects.filter(
        dataset__user=user,
        token=token,
    ).select_related('dataset').first()
    if not lst:
        return None
    from workspace.services.listing_edit import apply_listing_edit_json

    try:
        apply_listing_edit_json(lst, payload)
        lst.save()
    except (ValueError, TypeError):
        return None
    return listing_detail_to_dict(lst)


def export_dataset_response(user, dataset_id: str, fmt: str):
    from workspace.services.export import export_csv_response, export_excel_response, export_json_response

    ds = get_dataset(user, dataset_id)
    if not ds:
        return None
    listings = ds.listings.all()
    safe_name = (ds.name or str(dataset_id)).replace('/', '-').replace('\\', '-')
    fmt = (fmt or 'xlsx').lower()
    if fmt == 'json':
        return export_json_response(listings, f'{safe_name}.json')
    if fmt == 'csv':
        return export_csv_response(listings, f'{safe_name}.csv')
    return export_excel_response(listings, f'{safe_name}.xlsx')


def search_listings(
    user,
    *,
    page: int = 1,
    page_size: int = 30,
    q: str = '',
    dataset_id: Optional[str] = None,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    area_min: Optional[int] = None,
    area_max: Optional[int] = None,
    rooms: Optional[int] = None,
) -> Tuple[List[dict], dict]:
    if not has_active_bot_license(user):
        return [], {'page': page, 'page_size': page_size, 'total': 0}
    qs = (
        Listing.objects.filter(dataset__user=user, dataset__is_active=True)
        .select_related('dataset')
        .order_by('-created_at')
    )
    if dataset_id:
        qs = qs.filter(dataset_id=dataset_id)
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(neighborhood__icontains=q)
            | Q(city__icontains=q)
            | Q(token__icontains=q)
        )
    if price_min is not None:
        qs = qs.filter(price__gte=price_min)
    if price_max is not None:
        qs = qs.filter(price__lte=price_max)
    if area_min is not None:
        qs = qs.filter(area__gte=area_min)
    if area_max is not None:
        qs = qs.filter(area__lte=area_max)
    if rooms is not None:
        qs = qs.filter(rooms__icontains=str(rooms))
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
    }
