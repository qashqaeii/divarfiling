"""حذف آگهی از فایلینگ — با/بدون سرکوب کاربر."""
from __future__ import annotations

from django.db import transaction

from workspace.models import Dataset, Listing
from workspace.services.listing_personal_status import DIVAR_SOURCE_PLATFORM
from workspace.services.listing_suppression import REASON_USER_DELETED, suppress_listing


def hard_delete_filing_copies_for_token(user, token: str) -> int:
    """حذف همه نسخه‌های فایلینگ یک توکن برای کاربر — بدون سرکوب."""
    token = str(token or '').strip()
    if not token:
        return 0
    qs = Listing.objects.filter(token=token, dataset__user=user).select_related('dataset')
    dataset_ids: set = set()
    deleted = 0
    for row in list(qs):
        dataset_ids.add(row.dataset_id)
        row.delete()
        deleted += 1
    if dataset_ids:
        for ds_id in dataset_ids:
            Dataset.objects.filter(pk=ds_id).update(
                row_count=Listing.objects.filter(dataset_id=ds_id).count(),
            )
    return deleted


def delete_divar_listing_from_filing(user, token: str) -> dict:
    """
    حذف عمدی کاربر از فایلینگ:
    - ثبت سرکوب per-user
    - حذف همه copies فایلینگ همان توکن
    - CRMProperty دست نخورده
    """
    token = str(token or '').strip()
    if not token:
        return {
            'token': '',
            'title': '',
            'deleted': False,
            'deleted_count': 0,
            'suppressed': False,
        }
    with transaction.atomic():
        suppress_listing(user, DIVAR_SOURCE_PLATFORM, token, REASON_USER_DELETED)
        deleted_count = hard_delete_filing_copies_for_token(user, token)
    return {
        'token': token,
        'title': '',
        'deleted': deleted_count > 0,
        'deleted_count': deleted_count,
        'suppressed': True,
    }
