"""لیست و فیلتر دیتاست‌های واجد شرایط برای مقالات سیستماتیک."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.urls import reverse

from blog.models import MarketArticleLink, MarketArticleRun
from blog.utils import persian_to_slug
from workspace.models import Dataset

MIN_ROW_COUNT = 100
PAGE_SIZE = 20

ARTICLE_STATUS_NONE = 'none'
ARTICLE_STATUS_DRAFT = 'draft'
ARTICLE_STATUS_READY = 'ready'
ARTICLE_STATUS_BUILDING = 'building'
ARTICLE_STATUS_PUBLISHED = 'published'
ARTICLE_STATUS_STALE = 'stale'

STATUS_LABELS = {
    ARTICLE_STATUS_NONE: 'ساخته نشده',
    ARTICLE_STATUS_DRAFT: 'پیش‌نویس',
    ARTICLE_STATUS_READY: 'آماده بررسی',
    ARTICLE_STATUS_BUILDING: 'در حال ساخت',
    ARTICLE_STATUS_PUBLISHED: 'منتشرشده',
    ARTICLE_STATUS_STALE: 'نیازمند به‌روزرسانی',
}

SORT_CHOICES = {
    'rows': ('-row_count',),
    'rows_asc': ('row_count',),
    'date': ('-created_at',),
    'date_asc': ('created_at',),
    'updated': ('-updated_at',),
    'name': ('name',),
    'confidence': ('-row_count',),  # fallback; enriched sort applied in Python when needed
    'quality': ('-row_count',),
}


def build_market_key(
    *,
    city: str,
    district: str,
    transaction_type: str,
    subcategory: str,
) -> str:
    parts = [
        persian_to_slug(city) or 'city',
        persian_to_slug(district) or 'district',
        persian_to_slug(transaction_type) or 'tx',
        persian_to_slug(subcategory) or 'type',
    ]
    return f"tahlil-bazar-{'-'.join(parts)}"


def market_key_for_dataset(dataset: Dataset) -> str:
    district = (dataset.district or '').strip()
    if not district:
        district = _dominant_neighborhood(dataset) or 'region'
    return build_market_key(
        city=(dataset.city or '').strip(),
        district=district,
        transaction_type=(dataset.transaction_type or '').strip(),
        subcategory=(dataset.subcategory or '').strip(),
    )


def _dominant_neighborhood(dataset: Dataset) -> str:
    from django.db.models import Count

    top = (
        dataset.listings.exclude(neighborhood='')
        .values('neighborhood')
        .annotate(c=Count('id'))
        .order_by('-c')
        .first()
    )
    return (top or {}).get('neighborhood') or ''


def eligible_datasets_qs() -> QuerySet[Dataset]:
    """دیتاست‌های سطح‌محله و سطح‌شهر (بدون district) هر دو واجد شرایط‌اند."""
    return (
        Dataset.objects.filter(
            is_active=True,
            row_count__gte=MIN_ROW_COUNT,
        )
        .exclude(city='')
        .exclude(transaction_type='')
        .exclude(subcategory='')
        .select_related('user')
    )


def count_eligible_datasets() -> int:
    return eligible_datasets_qs().count()


def _article_status_for_dataset(
    dataset: Dataset,
    *,
    links_by_key: dict[str, MarketArticleLink],
    runs_by_dataset: dict[Any, MarketArticleRun],
) -> tuple[str, MarketArticleLink | None, MarketArticleRun | None]:
    market_key = market_key_for_dataset(dataset)
    link = links_by_key.get(market_key)
    run = runs_by_dataset.get(dataset.pk)

    if link and link.post_id:
        post = link.post
        stale = False
        if link.last_generated_at and dataset.updated_at and dataset.updated_at > link.last_generated_at:
            stale = True
        if stale:
            return ARTICLE_STATUS_STALE, link, run
        if post.is_published:
            return ARTICLE_STATUS_PUBLISHED, link, run
        return ARTICLE_STATUS_DRAFT, link, run

    if run and run.status == MarketArticleRun.Status.BUILDING:
        return ARTICLE_STATUS_BUILDING, link, run
    if run and run.status == MarketArticleRun.Status.PREVIEW:
        return ARTICLE_STATUS_READY, link, run
    if run and run.status == MarketArticleRun.Status.DRAFT_LINKED and run.post_id:
        if run.post.is_published:
            return ARTICLE_STATUS_PUBLISHED, link, run
        return ARTICLE_STATUS_DRAFT, link, run

    return ARTICLE_STATUS_NONE, link, run


def list_eligible_datasets(
    *,
    city: str = '',
    district: str = '',
    transaction_type: str = '',
    subcategory: str = '',
    article_status: str = '',
    min_rows: int = MIN_ROW_COUNT,
    sort: str = 'rows',
    page: int = 1,
    page_size: int = PAGE_SIZE,
) -> dict[str, Any]:
    qs = eligible_datasets_qs()
    if min_rows and min_rows > MIN_ROW_COUNT:
        qs = qs.filter(row_count__gte=min_rows)
    if city:
        qs = qs.filter(city__icontains=city.strip())
    if district:
        qs = qs.filter(
            Q(district__icontains=district.strip())
            | Q(listings__neighborhood__icontains=district.strip())
        ).distinct()
    if transaction_type:
        qs = qs.filter(transaction_type__icontains=transaction_type.strip())
    if subcategory:
        qs = qs.filter(subcategory__icontains=subcategory.strip())

    order = SORT_CHOICES.get(sort, SORT_CHOICES['rows'])
    qs = qs.order_by(*order)

    # Prefetch links/runs for status (bounded by page after pagination when possible)
    # For status filter we need enrichment first — paginate then filter is imperfect;
    # apply status filter after building rows for the current sort window.
    all_ids = list(qs.values_list('pk', flat=True)[:500])
    datasets = list(Dataset.objects.filter(pk__in=all_ids).select_related('user'))
    # Preserve order
    by_id = {d.pk: d for d in datasets}
    ordered = [by_id[i] for i in all_ids if i in by_id]

    keys = [market_key_for_dataset(d) for d in ordered]
    links = {
        link.market_key: link
        for link in MarketArticleLink.objects.filter(market_key__in=keys).select_related('post', 'last_run')
    }
    runs = {
        run.dataset_id: run
        for run in (
            MarketArticleRun.objects.filter(dataset_id__in=all_ids)
            .exclude(status=MarketArticleRun.Status.DISCARDED)
            .order_by('dataset_id', '-created_at')
            .distinct('dataset_id')
            if _supports_distinct_on()
            else _latest_runs_fallback(all_ids)
        )
    }

    rows: list[dict[str, Any]] = []
    for dataset in ordered:
        status, link, run = _article_status_for_dataset(
            dataset, links_by_key=links, runs_by_dataset=runs,
        )
        if article_status and status != article_status:
            continue
        market_key = market_key_for_dataset(dataset)
        district_label = (
            (dataset.district or '').strip()
            or _dominant_neighborhood(dataset)
            or 'کل شهر'
        )
        rows.append({
            'id': str(dataset.pk),
            'name': dataset.name,
            'city': dataset.city or '—',
            'district': district_label,
            'transaction_type': dataset.transaction_type or '—',
            'subcategory': dataset.subcategory or '—',
            'row_count': dataset.row_count,
            'valid_count': run.valid_count if run else None,
            'raw_count': run.raw_count if run else dataset.row_count,
            'data_from': run.data_from if run else None,
            'data_to': run.data_to if run else None,
            'confidence_score': run.confidence_score if run else None,
            'quality_pct': run.quality_pct if run else None,
            'article_status': status,
            'article_status_label': STATUS_LABELS.get(status, status),
            'market_key': market_key,
            'last_generated_at': (
                (link.last_generated_at if link else None)
                or (run.updated_at if run else None)
            ),
            'run_id': str(run.pk) if run else '',
            'post_id': link.post_id if link else (run.post_id if run else None),
            'post_url': (
                link.post.get_absolute_url()
                if link and link.post_id
                else (run.post.get_absolute_url() if run and run.post_id else '')
            ),
            'post_admin_url': (
                f'/admin/blog/post/{link.post_id}/change/'
                if link and link.post_id
                else (
                    f'/admin/blog/post/{run.post_id}/change/'
                    if run and run.post_id
                    else ''
                )
            ),
            'is_published': bool(link and link.post_id and link.post.is_published),
            'analyze_url': reverse(
                'admin_panel_blog_systematic_analyze',
                kwargs={'dataset_id': dataset.pk},
            ),
            'created_at': dataset.created_at,
            'updated_at': dataset.updated_at,
            'owner': dataset.user.get_full_name() or dataset.user.username,
        })

    if sort == 'confidence':
        rows.sort(key=lambda r: (r['confidence_score'] is not None, r['confidence_score'] or 0), reverse=True)
    elif sort == 'quality':
        rows.sort(key=lambda r: (r['quality_pct'] is not None, r['quality_pct'] or 0), reverse=True)

    paginator = Paginator(rows, page_size)
    page_obj = paginator.get_page(page)

    filter_values = {
        'city': city,
        'district': district,
        'transaction_type': transaction_type,
        'subcategory': subcategory,
        'article_status': article_status,
        'min_rows': min_rows,
        'sort': sort,
    }

    return {
        'page_obj': page_obj,
        'rows': list(page_obj.object_list),
        'total': paginator.count,
        'filter_values': filter_values,
        'status_choices': STATUS_LABELS,
        'sort_choices': {
            'rows': 'بیشترین رکورد',
            'rows_asc': 'کمترین رکورد',
            'date': 'جدیدترین',
            'updated': 'آخرین به‌روزرسانی دیتاست',
            'confidence': 'امتیاز اعتماد',
            'quality': 'کیفیت داده',
            'name': 'نام',
        },
        'querystring': urlencode({k: v for k, v in filter_values.items() if v not in ('', None, MIN_ROW_COUNT) or k == 'sort'}),
    }


def filter_options() -> dict[str, list[str]]:
    qs = eligible_datasets_qs()
    cities = list(
        qs.exclude(city='')
        .order_by('city')
        .values_list('city', flat=True)
        .distinct()[:80]
    )
    districts = list(
        qs.exclude(district='')
        .order_by('district')
        .values_list('district', flat=True)
        .distinct()[:120]
    )
    txs = list(
        qs.exclude(transaction_type='')
        .order_by('transaction_type')
        .values_list('transaction_type', flat=True)
        .distinct()[:40]
    )
    types = list(
        qs.exclude(subcategory='')
        .order_by('subcategory')
        .values_list('subcategory', flat=True)
        .distinct()[:80]
    )
    return {
        'cities': cities,
        'districts': districts,
        'transaction_types': txs,
        'subcategories': types,
    }


def _supports_distinct_on() -> bool:
    from django.db import connection
    return connection.vendor == 'postgresql'


def _latest_runs_fallback(dataset_ids: list) -> list[MarketArticleRun]:
    seen: set = set()
    result: list[MarketArticleRun] = []
    for run in (
        MarketArticleRun.objects.filter(dataset_id__in=dataset_ids)
        .exclude(status=MarketArticleRun.Status.DISCARDED)
        .order_by('-created_at')
    ):
        if run.dataset_id in seen:
            continue
        seen.add(run.dataset_id)
        result.append(run)
    return result
