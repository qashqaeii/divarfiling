"""پایپ‌لاین ساخت پیش‌نمایش و Draft مقاله سیستماتیک."""
from __future__ import annotations

from typing import Any

from datetime import date, datetime
import json

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone

from blog.models import Category, MarketArticleLink, MarketArticleRun, Post
from blog.services.market_article_analyze import (
    extract_quality_metrics,
    run_dataset_analysis,
    sanitize_report_for_public,
)
from blog.services.market_article_access import analyze_district_access
from blog.services.market_article_assets import render_article_maps, render_featured_image
from blog.services.market_article_composer import compose_market_article
from blog.services.market_article_eligibility import market_key_for_dataset
from blog.utils import get_or_create_tag
from workspace.models import Dataset

User = get_user_model()

CATEGORY_SLUG = 'tahlil-bazar'
CATEGORY_NAME = 'تحلیل بازار'


class MarketArticleError(Exception):
    pass


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder, default=str))


def _save_extra_maps(run: MarketArticleRun, extras: dict) -> dict[str, str]:
    """ذخیره نقشه‌های تکمیلی کنار featured و برگرداندن URLها."""
    urls: dict[str, str] = {}
    chart = dict(run.chart_assets or {})
    for key, content in extras.items():
        field_name = f'{run.pk.hex[:8]}-{content.name}'
        # store via featured_image storage path pattern using ContentFile on chart_assets paths
        path = default_storage.save(f'blog/market-maps/{field_name}', content)
        url = default_storage.url(path)
        urls[key] = url
        chart[key] = url
    if run.featured_image:
        urls['featured'] = run.featured_image.url
        chart['featured'] = run.featured_image.url
    chart['geo_count'] = chart.get('geo_count')
    run.chart_assets = chart
    return urls


def _related_market_posts(*, city: str, exclude_slug: str = '', limit: int = 6) -> list[dict[str, str]]:
    """مقالات مرتبط منتشرشده برای لینک‌سازی داخلی."""
    qs = (
        Post.objects.filter(is_published=True)
        .select_related('category')
        .order_by('-published_at', '-id')
    )
    if exclude_slug:
        qs = qs.exclude(slug=exclude_slug)

    cat_posts = list(qs.filter(category__slug=CATEGORY_SLUG)[:20])
    if city:
        city_hits = [p for p in cat_posts if city in (p.title or '')]
        others = [p for p in cat_posts if p not in city_hits]
        ordered = city_hits + others
    else:
        ordered = cat_posts

    if len(ordered) < limit:
        extras = list(qs.exclude(pk__in=[p.pk for p in ordered])[: limit * 2])
        for p in extras:
            if city and city in (p.title or ''):
                ordered.insert(0, p)
            else:
                ordered.append(p)

    out: list[dict[str, str]] = []
    seen = set()
    for post in ordered:
        if post.slug in seen:
            continue
        seen.add(post.slug)
        out.append({
            'title': post.title,
            'url': post.get_absolute_url(),
        })
        if len(out) >= limit:
            break
    return out


def build_preview(dataset: Dataset, user) -> MarketArticleRun:
    if dataset.row_count < 100:
        raise MarketArticleError('حداقل ۱۰۰ رکورد برای ساخت مقاله لازم است.')
    if not (dataset.city and dataset.transaction_type and dataset.subcategory):
        raise MarketArticleError('شهر، نوع معامله و نوع ملک باید مشخص باشند.')

    analysis = run_dataset_analysis(dataset)
    safe = sanitize_report_for_public(analysis)
    geo = safe.pop('_geo_for_assets', analysis.get('geo_points') or [])
    metrics = extract_quality_metrics(analysis)
    report = safe['report'] if isinstance(safe.get('report'), dict) else (analysis.get('report') or {})
    # Re-sanitize nested leftovers for public article body
    report = sanitize_report_for_public({'report': report}).get('report') or report
    meta = dict(analysis.get('dataset_meta') or {})
    if not meta.get('district'):
        from blog.services.market_article_eligibility import _dominant_neighborhood
        meta['district'] = _dominant_neighborhood(dataset) or 'منطقه'

    market_key = market_key_for_dataset(dataset)
    tx = report.get('tx') or {}
    is_rent = bool(tx.get('is_rent') and not tx.get('is_sale'))
    tx_label = 'اجاره' if is_rent else 'فروش'
    pa = report.get('price_analysis') or {}
    pps = pa.get('price_per_sqm') or {}
    full_dep = pa.get('full_deposit') or {}
    deposit = pa.get('deposit') or {}
    trends = report.get('price_trends') or {}
    conf = report.get('confidence') or {}

    if is_rent:
        metric_label = 'معادل رهن کامل'
        metric_fmt = (
            full_dep.get('median_fmt')
            or deposit.get('median_fmt')
            or pps.get('median_fmt')
            or '—'
        )
        trend_fmt = trends.get('full_deposit_monthly_fmt') or trends.get('pps_monthly_fmt') or '—'
    else:
        metric_label = 'قیمت هر متر'
        metric_fmt = pps.get('median_fmt') or '—'
        trend_fmt = trends.get('pps_monthly_fmt') or '—'

    image_file = render_featured_image(
        city=meta.get('city') or '',
        district=meta.get('district') or '',
        tx_label=tx_label,
        metric_label=metric_label,
        metric_fmt=metric_fmt,
        trend_fmt=trend_fmt,
        valid_count=int(metrics.get('valid_count') or 0),
        confidence_score=conf.get('display_score') or conf.get('score') or '—',
        geo_points=geo,
    )

    district_access = analyze_district_access(geo)
    if isinstance(report, dict) and district_access.get('ok'):
        report = {**report, 'district_access': district_access}

    extra_maps = render_article_maps(
        city=meta.get('city') or '',
        district=meta.get('district') or '',
        tx_label=tx_label,
        metric_label=metric_label,
        metric_fmt=metric_fmt,
        valid_count=int(metrics.get('valid_count') or 0),
        confidence_score=conf.get('display_score') or conf.get('score') or '—',
        geo_points=geo,
        access_markers=district_access.get('map_markers') if district_access.get('ok') else None,
    )

    related = _related_market_posts(city=meta.get('city') or '', exclude_slug=market_key)

    composed = compose_market_article(
        report=report,
        dataset_meta=meta,
        map_image_url='',
        map_assets={},
        map_caption=f'نقشه تراکم بازار {meta.get("district")} {meta.get("city")}',
        related_posts=related,
    )

    seo = {
        'title': composed['title'][:200],
        'slug': market_key[:200],
        'excerpt': composed['excerpt'][:300],
        'tags': composed['tags'],
    }

    with transaction.atomic():
        run = MarketArticleRun(
            dataset=dataset,
            market_key=market_key,
            status=MarketArticleRun.Status.PREVIEW,
            report_json=_json_safe({
                'report': report,
                'dataset_meta': meta,
                'metrics': metrics,
                'district_access': district_access,
            }),
            seo_json=seo,
            content_html=composed['content_html'],
            faq_json=composed['faq'],
            quality_score=metrics.get('quality_score'),
            confidence_score=metrics.get('confidence_score'),
            valid_count=int(metrics.get('valid_count') or 0),
            raw_count=int(metrics.get('raw_count') or 0),
            quality_pct=metrics.get('quality_pct'),
            data_from=metrics.get('data_from'),
            data_to=metrics.get('data_to'),
            source_dataset_updated_at=dataset.updated_at,
            created_by=user if getattr(user, 'is_authenticated', False) else None,
            chart_assets={
                'geo_count': len(geo or []),
                'access_score': district_access.get('score') if district_access.get('ok') else None,
                'access_grade': district_access.get('grade') if district_access.get('ok') else None,
            },
        )
        run.featured_image.save(image_file.name, image_file, save=False)
        run.save()

        map_urls = _save_extra_maps(run, extra_maps)
        composed2 = compose_market_article(
            report=report,
            dataset_meta=meta,
            map_image_url=map_urls.get('featured') or (run.featured_image.url if run.featured_image else ''),
            map_assets=map_urls,
            map_caption=f'نقشه بازار {meta.get("district")} {meta.get("city")}',
            related_posts=related,
        )
        run.content_html = composed2['content_html']
        run.faq_json = composed2['faq']
        run.seo_json = {
            **seo,
            'title': composed2['title'][:200],
            'excerpt': composed2['excerpt'][:300],
            'tags': composed2['tags'],
        }
        run.save(update_fields=['content_html', 'faq_json', 'seo_json', 'chart_assets', 'updated_at'])

    return run


def save_seo_edits(run: MarketArticleRun, *, title: str, excerpt: str, slug: str | None = None) -> MarketArticleRun:
    seo = dict(run.seo_json or {})
    if title:
        seo['title'] = title.strip()[:200]
    if excerpt is not None:
        seo['excerpt'] = excerpt.strip()[:300]
    # slug locked when linked; only allow change before draft
    if slug and run.status == MarketArticleRun.Status.PREVIEW and not run.post_id:
        existing_link = MarketArticleLink.objects.filter(market_key=slug.strip()).exclude(
            post_id=run.post_id,
        ).exists()
        if not existing_link:
            seo['slug'] = slug.strip()[:200]
            run.market_key = seo['slug']
    run.seo_json = seo
    run.save(update_fields=['seo_json', 'market_key', 'updated_at'])
    return run


def get_existing_link(market_key: str) -> MarketArticleLink | None:
    return (
        MarketArticleLink.objects.filter(market_key=market_key)
        .select_related('post', 'primary_dataset', 'last_run')
        .first()
    )


@transaction.atomic
def create_draft(run: MarketArticleRun, user=None) -> Post:
    seo = run.seo_json or {}
    title = (seo.get('title') or run.market_key)[:200]
    excerpt = (seo.get('excerpt') or '')[:300]
    slug = (seo.get('slug') or run.market_key)[:200]
    tags = seo.get('tags') or []

    link = get_existing_link(run.market_key)
    if link:
        raise MarketArticleError(
            'برای این ترکیب بازار مقاله وجود دارد. از «به‌روزرسانی مقاله موجود» استفاده کنید.'
        )
    if Post.objects.filter(slug=slug).exists():
        raise MarketArticleError(f'اسلاگ «{slug}» قبلاً استفاده شده است.')

    category, _ = Category.objects.get_or_create(
        slug=CATEGORY_SLUG,
        defaults={'name': CATEGORY_NAME, 'description': 'تحلیل‌های داده‌محور بازار املاک', 'order': 5},
    )
    author = user if user and getattr(user, 'is_authenticated', False) else run.created_by
    if author is None:
        author = User.objects.filter(is_superuser=True).order_by('pk').first()
    if author is None:
        raise MarketArticleError('نویسنده یافت نشد.')

    post = Post.objects.create(
        title=title,
        slug=slug[:220],
        author=author,
        category=category,
        content=run.content_html,
        excerpt=excerpt,
        is_published=False,
        published_at=None,
    )
    if run.featured_image:
        post.featured_image = run.featured_image
        post.save(update_fields=['featured_image'])

    tag_objs = [get_or_create_tag(name) for name in tags if name]
    if tag_objs:
        post.tags.set(tag_objs)

    run.post = post
    run.status = MarketArticleRun.Status.DRAFT_LINKED
    run.save(update_fields=['post', 'status', 'updated_at'])

    MarketArticleLink.objects.create(
        market_key=run.market_key,
        post=post,
        primary_dataset=run.dataset,
        last_run=run,
        last_generated_at=timezone.now(),
    )
    return post


@transaction.atomic
def update_existing_post(run: MarketArticleRun) -> Post:
    link = get_existing_link(run.market_key)
    if not link:
        raise MarketArticleError('مقاله قبلی برای این ترکیب بازار یافت نشد.')

    post = link.post
    seo = run.seo_json or {}
    post.title = (seo.get('title') or post.title)[:200]
    post.excerpt = (seo.get('excerpt') or post.excerpt)[:300]
    post.content = run.content_html
    # keep slug stable
    if run.featured_image:
        post.featured_image = run.featured_image
    post.save()

    tags = seo.get('tags') or []
    if tags:
        post.tags.set([get_or_create_tag(name) for name in tags if name])

    run.post = post
    run.status = MarketArticleRun.Status.DRAFT_LINKED
    run.save(update_fields=['post', 'status', 'updated_at'])

    link.primary_dataset = run.dataset
    link.last_run = run
    link.last_generated_at = timezone.now()
    link.save(update_fields=['primary_dataset', 'last_run', 'last_generated_at', 'updated_at'])
    return post


def preview_context(run: MarketArticleRun) -> dict[str, Any]:
    seo = run.seo_json or {}
    link = get_existing_link(run.market_key)
    chart = run.chart_assets or {}
    report_blob = run.report_json or {}
    stored_metrics = report_blob.get('metrics') if isinstance(report_blob, dict) else {}
    if not isinstance(stored_metrics, dict):
        stored_metrics = {}
    map_keys = {
        'featured', 'street_heat', 'street_grid', 'street_value', 'street_hotspots',
        'street_dots', 'satellite_heat', 'satellite_value', 'satellite', 'price',
    }
    return {
        'run': run,
        'seo': seo,
        'title': seo.get('title') or '',
        'slug': seo.get('slug') or run.market_key,
        'excerpt': seo.get('excerpt') or '',
        'content_html': run.content_html,
        'faq': run.faq_json or [],
        'featured_image_url': run.featured_image.url if run.featured_image else '',
        'map_assets': {
            k: v for k, v in chart.items()
            if k in map_keys and isinstance(v, str) and v
        },
        'existing_link': link,
        'can_create_draft': link is None,
        'can_update': link is not None,
        'metrics': {
            'confidence_score': run.confidence_score,
            'quality_pct': run.quality_pct,
            'valid_count': run.valid_count,
            'raw_count': run.raw_count,
            'data_from': run.data_from,
            'data_to': run.data_to,
            'date_from_fmt': stored_metrics.get('date_from_fmt') or '',
            'date_to_fmt': stored_metrics.get('date_to_fmt') or '',
        },
    }
