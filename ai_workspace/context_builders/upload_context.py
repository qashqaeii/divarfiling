"""Context Builder — آپلود dataset."""
from __future__ import annotations

from typing import Any, Dict, Optional

from workspace.models import Dataset
from workspace.services.analyzer import compute_outliers_report, compute_statistics, listings_to_dataframe
from workspace.services.formatting import format_toman


def build(
    upload_batch: Dict[str, Any],
    dataset: Optional[Dataset] = None,
) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {
        'total_files': upload_batch.get('total_files') or len(upload_batch.get('imported') or []),
        'total_added': upload_batch.get('total_added') or 0,
        'new_files': upload_batch.get('new_files') or 0,
        'updated_files': upload_batch.get('updated_files') or 0,
        'errors_count': len(upload_batch.get('errors') or []),
        'skipped': upload_batch.get('skipped') or 0,
    }

    version_parts = [
        str(ctx['total_files']),
        str(ctx['total_added']),
        str(ctx['new_files']),
    ]

    if dataset:
        version_parts.append(str(dataset.id))
        df = listings_to_dataframe(dataset.listings.all())
        if len(df) >= 5:
            stats = compute_statistics(df, dataset.transaction_type or '')
            price_stats = stats.get('price') or {}
            if price_stats.get('median'):
                ctx['median_price_label'] = format_toman(price_stats['median'])
            pps = stats.get('price_per_sqm') or {}
            if pps.get('median'):
                ctx['median_per_sqm_label'] = format_toman(pps['median'], per_sqm=True)

            outliers = compute_outliers_report(df, dataset.transaction_type or '')
            ctx['outlier_count'] = len(outliers)

        ctx['duplicate_count'] = _estimate_duplicates(dataset)

    ctx['content_version'] = ':'.join(version_parts)
    ctx['_upload_batch'] = upload_batch
    ctx['_dataset'] = dataset
    return ctx


def _estimate_duplicates(dataset: Dataset) -> int:
    from django.db.models import Count

    dup_qs = (
        dataset.listings.exclude(token='')
        .values('token')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
    )
    return sum(row['c'] - 1 for row in dup_qs)
