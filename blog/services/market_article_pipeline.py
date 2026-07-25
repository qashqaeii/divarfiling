"""پایپ‌لاین ساخت پیش‌نمایش و Draft مقاله سیستماتیک."""
from __future__ import annotations

from typing import Any

from datetime import date, datetime
import json
import logging
import re
import threading

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.serializers.json import DjangoJSONEncoder
from django.db import close_old_connections, transaction
from django.utils import timezone

from blog.models import Category, MarketArticleLink, MarketArticleRun, Post
from blog.services.market_article_analyze import (
    extract_quality_metrics,
    run_dataset_analysis,
    sanitize_report_for_public,
)
from blog.services.market_article_access import analyze_district_access
from blog.services.market_article_assets import render_article_maps, render_featured_image
from blog.services.market_article_charts import render_article_charts
from blog.services.market_article_composer import compose_market_article
from blog.services.market_article_eligibility import market_key_for_dataset
from blog.utils import get_or_create_tag
from workspace.models import Dataset

User = get_user_model()
logger = logging.getLogger(__name__)

CATEGORY_SLUG = 'tahlil-bazar'
CATEGORY_NAME = 'تحلیل بازار'


class MarketArticleError(Exception):
    pass


# مراحل ساخت پیش‌نمایش — برای نوار پیشرفت زنده در پنل ادمین
BUILD_PROGRESS_STEPS: list[dict[str, Any]] = [
    {'key': 'queued', 'label': 'آماده‌سازی صف ساخت', 'pct': 3},
    {'key': 'analyze', 'label': 'تحلیل داده و آمار بازار', 'pct': 18},
    {'key': 'featured', 'label': 'ساخت تصویر شاخص نقشه', 'pct': 32},
    {'key': 'access', 'label': 'امتیاز امکانات و دسترسی منطقه', 'pct': 48},
    {'key': 'maps', 'label': 'رندر نقشه‌های شهری و ماهواره‌ای', 'pct': 68},
    {'key': 'charts', 'label': 'ساخت نمودارهای تحلیلی', 'pct': 82},
    {'key': 'compose', 'label': 'تولید متن و ساختار مقاله', 'pct': 92},
    {'key': 'save', 'label': 'ذخیره پیش‌نمایش نهایی', 'pct': 100},
]

_BUILD_STEP_BY_KEY = {s['key']: s for s in BUILD_PROGRESS_STEPS}


def build_progress_payload(chart_assets: dict | None) -> dict[str, Any]:
    """وضعیت پیشرفت برای API و قالب پیش‌نمایش."""
    chart = chart_assets if isinstance(chart_assets, dict) else {}
    step = chart.get('build_step') or 'queued'
    meta = _BUILD_STEP_BY_KEY.get(step) or _BUILD_STEP_BY_KEY['queued']
    done = [k for k in (chart.get('build_steps_done') or []) if k in _BUILD_STEP_BY_KEY]
    try:
        pct = int(chart.get('build_pct') if chart.get('build_pct') is not None else meta['pct'])
    except (TypeError, ValueError):
        pct = int(meta['pct'])
    return {
        'pct': max(0, min(100, pct)),
        'step': step,
        'label': chart.get('build_label') or meta['label'],
        'detail': chart.get('build_detail') or '',
        'done': done,
        'steps': BUILD_PROGRESS_STEPS,
    }


def _set_build_progress(
    run: MarketArticleRun,
    *,
    step: str,
    detail: str = '',
    pct: int | None = None,
) -> None:
    meta = _BUILD_STEP_BY_KEY.get(step) or {'key': step, 'label': step, 'pct': pct or 0}
    chart = dict(run.chart_assets or {})
    done = list(chart.get('build_steps_done') or [])
    if step not in done:
        done.append(step)
    chart.update({
        'build_step': step,
        'build_label': meta['label'],
        'build_pct': max(0, min(100, int(pct if pct is not None else meta['pct']))),
        'build_detail': (detail or '')[:220],
        'build_steps_done': done,
        'build_updated_at': timezone.now().isoformat(),
    })
    run.chart_assets = chart
    run.save(update_fields=['chart_assets', 'updated_at'])


def _validate_dataset_for_article(dataset: Dataset) -> None:
    if dataset.row_count < 100:
        raise MarketArticleError('حداقل ۱۰۰ رکورد برای ساخت مقاله لازم است.')
    if not (dataset.city and dataset.transaction_type and dataset.subcategory):
        raise MarketArticleError('شهر، نوع معامله و نوع ملک باید مشخص باشند.')


def _create_building_run(dataset: Dataset, user) -> MarketArticleRun:
    market_key = market_key_for_dataset(dataset)
    district = (dataset.district or '').strip() or 'منطقه'
    city = (dataset.city or '').strip()
    return MarketArticleRun.objects.create(
        dataset=dataset,
        market_key=market_key,
        status=MarketArticleRun.Status.BUILDING,
        seo_json={
            'title': f'در حال ساخت تحلیل بازار {district} {city}'.strip()[:200],
            'slug': market_key[:200],
            'excerpt': 'تولید نقشه و متن در پس‌زمینه انجام می‌شود؛ این صفحه به‌صورت خودکار به‌روز می‌شود.',
            'tags': [],
        },
        content_html='',
        faq_json=[],
        chart_assets={
            'build_step': 'queued',
            'build_label': _BUILD_STEP_BY_KEY['queued']['label'],
            'build_pct': 3,
            'build_detail': f'{district} · {city}'.strip(' ·'),
            'build_steps_done': ['queued'],
            'build_updated_at': timezone.now().isoformat(),
        },
        created_by=user if getattr(user, 'is_authenticated', False) else None,
        source_dataset_updated_at=dataset.updated_at,
    )


def _mark_run_failed(run_id, exc: BaseException) -> None:
    try:
        run = MarketArticleRun.objects.filter(pk=run_id).first()
        if not run:
            return
        chart = dict(run.chart_assets or {})
        chart['build_error'] = str(exc)[:500]
        run.status = MarketArticleRun.Status.FAILED
        run.chart_assets = chart
        run.save(update_fields=['status', 'chart_assets', 'updated_at'])
    except Exception:
        logger.exception('failed to mark market article run as failed run=%s', run_id)


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
    """ساخت هم‌زمان پیش‌نمایش (تست‌ها / فراخوانی مستقیم)."""
    _validate_dataset_for_article(dataset)
    run = _create_building_run(dataset, user)
    return _complete_preview_build(run)


def enqueue_preview_build(
    dataset: Dataset,
    user,
    *,
    discard_run: MarketArticleRun | None = None,
) -> MarketArticleRun:
    """شروع ساخت در پس‌زمینه — پاسخ HTTP فوری (جلوگیری از 502 گانیکورن/nginx)."""
    _validate_dataset_for_article(dataset)
    run = _create_building_run(dataset, user)
    if discard_run is not None:
        discard_run.status = MarketArticleRun.Status.DISCARDED
        discard_run.save(update_fields=['status', 'updated_at'])

    run_id = run.pk

    def _worker():
        close_old_connections()
        try:
            target = MarketArticleRun.objects.select_related('dataset').get(pk=run_id)
            _complete_preview_build(target)
        except Exception as exc:
            logger.exception('market article preview build failed run=%s', run_id)
            _mark_run_failed(run_id, exc)
        finally:
            close_old_connections()

    threading.Thread(
        target=_worker,
        name=f'market-preview-{run_id}',
        daemon=True,
    ).start()
    return run


def _complete_preview_build(run: MarketArticleRun) -> MarketArticleRun:
    dataset = run.dataset
    place_hint = f'{(dataset.district or "").strip() or "منطقه"} · {(dataset.city or "").strip()}'.strip(' ·')

    _set_build_progress(run, step='analyze', detail=f'خواندن و پاک‌سازی فایل‌های {place_hint}')
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
    valid_n = int(metrics.get('valid_count') or 0)

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

    _set_build_progress(
        run,
        step='featured',
        detail=f'{valid_n} فایل معتبر · {len(geo or [])} نقطه مکانی',
    )
    image_file, featured_meta = render_featured_image(
        city=meta.get('city') or '',
        district=meta.get('district') or '',
        tx_label=tx_label,
        metric_label=metric_label,
        metric_fmt=metric_fmt,
        trend_fmt=trend_fmt,
        valid_count=valid_n,
        confidence_score=conf.get('display_score') or conf.get('score') or '—',
        geo_points=geo,
    )

    _set_build_progress(
        run,
        step='access',
        detail='استعلام امکانات شهری از OpenStreetMap',
    )
    district_access = analyze_district_access(geo)
    # همیشه به report وصل شود تا بخش HTML امکانات/دسترسی در پیش‌نمایش ساخته شود
    if isinstance(report, dict) and isinstance(district_access, dict):
        report = {**report, 'district_access': district_access}
    access_detail = ''
    if district_access.get('ok'):
        access_detail = (
            f'امتیاز {district_access.get("score")} · '
            f'{district_access.get("total_pois") or 0} نقطه خدماتی'
        )
    elif district_access.get('reason'):
        access_detail = f'وضعیت: {district_access.get("reason")}'

    _set_build_progress(
        run,
        step='maps',
        detail=access_detail or 'دانلود کاشی نقشه و لایه‌های هیت‌مپ',
    )
    extra_maps = render_article_maps(
        city=meta.get('city') or '',
        district=meta.get('district') or '',
        tx_label=tx_label,
        metric_label=metric_label,
        metric_fmt=metric_fmt,
        valid_count=valid_n,
        confidence_score=conf.get('display_score') or conf.get('score') or '—',
        geo_points=geo,
        access_markers=district_access.get('map_markers') if district_access.get('ok') else None,
    )

    _set_build_progress(
        run,
        step='charts',
        detail=f'{len(extra_maps)} نقشه آماده · در حال ساخت نمودارها',
    )
    chart_files = render_article_charts(
        report=report if isinstance(report, dict) else {},
        city=meta.get('city') or '',
        district=meta.get('district') or '',
        is_rent=is_rent,
    )

    related = _related_market_posts(city=meta.get('city') or '', exclude_slug=market_key)

    _set_build_progress(
        run,
        step='compose',
        detail=f'{len(chart_files)} نمودار · نوشتن متن چندمخاطبه',
    )
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

    _set_build_progress(run, step='save', detail='ذخیره تصویر، نقشه‌ها و HTML نهایی')
    with transaction.atomic():
        run.market_key = market_key
        run.status = MarketArticleRun.Status.PREVIEW
        run.report_json = _json_safe({
            'report': report,
            'dataset_meta': meta,
            'metrics': metrics,
            'district_access': district_access,
        })
        run.seo_json = seo
        run.content_html = composed['content_html']
        run.faq_json = composed['faq']
        run.quality_score = metrics.get('quality_score')
        run.confidence_score = metrics.get('confidence_score')
        run.valid_count = valid_n
        run.raw_count = int(metrics.get('raw_count') or 0)
        run.quality_pct = metrics.get('quality_pct')
        run.data_from = metrics.get('data_from')
        run.data_to = metrics.get('data_to')
        run.source_dataset_updated_at = dataset.updated_at
        run.chart_assets = {
            'geo_count': len(geo or []),
            'access_score': district_access.get('score') if district_access.get('ok') else None,
            'access_grade': district_access.get('grade') if district_access.get('ok') else None,
            'build_step': 'save',
            'build_label': _BUILD_STEP_BY_KEY['save']['label'],
            'build_pct': 100,
            'build_detail': 'آماده',
            'build_steps_done': [s['key'] for s in BUILD_PROGRESS_STEPS],
            **featured_meta,
        }
        run.featured_image.save(image_file.name, image_file, save=False)
        run.save()

        asset_urls = _save_extra_maps(run, {**extra_maps, **chart_files})
        composed2 = compose_market_article(
            report=report,
            dataset_meta=meta,
            map_image_url=asset_urls.get('featured') or (run.featured_image.url if run.featured_image else ''),
            map_assets=asset_urls,
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


def _ensure_run_ready(run: MarketArticleRun) -> None:
    if run.status == MarketArticleRun.Status.BUILDING:
        raise MarketArticleError('پیش‌نمایش هنوز در حال ساخت است. چند لحظه صبر کنید.')
    if run.status == MarketArticleRun.Status.FAILED:
        raise MarketArticleError('ساخت پیش‌نمایش ناموفق بود. دوباره تولید کنید.')
    if run.status == MarketArticleRun.Status.DISCARDED:
        raise MarketArticleError('این پیش‌نمایش لغو شده است.')


@transaction.atomic
def create_draft(run: MarketArticleRun, user=None) -> Post:
    _ensure_run_ready(run)
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
        content=_ensure_access_section_in_html(run),
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
    _ensure_run_ready(run)
    link = get_existing_link(run.market_key)
    if not link:
        raise MarketArticleError('مقاله قبلی برای این ترکیب بازار یافت نشد.')

    post = link.post
    seo = run.seo_json or {}
    post.title = (seo.get('title') or post.title)[:200]
    post.excerpt = (seo.get('excerpt') or post.excerpt)[:300]
    post.content = _ensure_access_section_in_html(run)
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
        'featured',
        'street_heat', 'street_grid', 'street_value', 'street_hotspots', 'street_dots',
        'satellite_heat', 'satellite_value', 'satellite', 'price',
        'map_sat_heat', 'map_sat_value', 'map_sat_hotspots', 'map_sat_grid', 'map_sat_dots',
        'map_dark_heat', 'map_dark_value', 'map_dark_hotspots', 'map_dark_dots',
        'map_light_heat', 'map_light_value', 'map_light_grid', 'map_light_hotspots',
        'map_street_heat', 'map_street_value', 'map_street_hotspots', 'map_street_grid', 'map_street_dots',
        'chart_price_ladder', 'chart_area_share', 'chart_market_depth', 'chart_access', 'chart_amenities',
    }
    is_building = run.status == MarketArticleRun.Status.BUILDING
    is_failed = run.status == MarketArticleRun.Status.FAILED
    ready = run.status in (
        MarketArticleRun.Status.PREVIEW,
        MarketArticleRun.Status.DRAFT_LINKED,
    )
    content_html = _ensure_access_section_in_html(run)
    return {
        'run': run,
        'seo': seo,
        'title': seo.get('title') or '',
        'slug': seo.get('slug') or run.market_key,
        'excerpt': seo.get('excerpt') or '',
        'content_html': content_html,
        'faq': run.faq_json or [],
        'featured_image_url': run.featured_image.url if run.featured_image else '',
        'map_assets': {
            k: v for k, v in chart.items()
            if k in map_keys and isinstance(v, str) and v
        },
        'existing_link': link,
        'is_building': is_building,
        'is_failed': is_failed,
        'build_error': chart.get('build_error') or '',
        'build_progress': build_progress_payload(chart),
        'can_create_draft': link is None and ready,
        'can_update': link is not None and ready,
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


def _ensure_access_section_in_html(run: MarketArticleRun) -> str:
    """اگر HTML ذخیره‌شده بخش دسترسی را ندارد، از report_json تزریق کن."""
    content = run.content_html or ''
    if 'mk-access-section' in content and 'mk-access-tally' in content:
        return content
    blob = run.report_json if isinstance(run.report_json, dict) else {}
    access = blob.get('district_access')
    if not isinstance(access, dict):
        report = blob.get('report') if isinstance(blob.get('report'), dict) else {}
        access = report.get('district_access') if isinstance(report, dict) else None
    if not isinstance(access, dict) or not access:
        return content

    meta = blob.get('dataset_meta') if isinstance(blob.get('dataset_meta'), dict) else {}
    city = meta.get('city') or ''
    district = meta.get('district') or ''
    from blog.services.market_article_access_html import render_district_access_section
    section = render_district_access_section(access, city=city, district=district)
    if not section:
        return content

    if 'mk-access-section' in content:
        # نسخه قدیمی بدون tally — جایگزین کن
        updated = re.sub(
            r'<section class="mk-access-section"[^>]*>.*?</section>',
            section,
            content,
            count=1,
            flags=re.DOTALL,
        )
        return updated if updated != content else content

    anchor = '<section class="mk-market-section" id="trends">'
    if anchor in content:
        return content.replace(anchor, section + '\n' + anchor, 1)
    convert = 'id="convert-access"'
    idx = content.find(convert)
    if idx != -1:
        # قبل از convert-access
        start = content.rfind('<aside', 0, idx)
        if start == -1:
            start = content.rfind('<section', 0, idx)
        if start != -1:
            return content[:start] + section + '\n' + content[start:]
    return content + '\n' + section
