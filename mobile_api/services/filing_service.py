"""فایلینگ workspace برای API موبایل."""
from __future__ import annotations

from typing import List, Tuple

from django.core.paginator import Paginator
from django.db.models import Q

from mobile_api.serializers import dataset_to_dict, listing_to_dict
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
    return _datasets_qs(user).filter(pk=dataset_id).first()


def list_listings(
    user,
    dataset_id: str,
    *,
    page: int = 1,
    page_size: int = 50,
    q: str = '',
) -> Tuple[List[dict], dict]:
    ds = get_dataset(user, dataset_id)
    if not ds:
        return [], {'page': page, 'page_size': page_size, 'total': 0}
    qs = Listing.objects.filter(dataset=ds).order_by('-created_at')
    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(neighborhood__icontains=q) | Q(token__icontains=q)
        )
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    return [listing_to_dict(lst) for lst in page_obj.object_list], {
        'page': page,
        'page_size': page_size,
        'total': paginator.count,
    }
