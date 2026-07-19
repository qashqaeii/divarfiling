"""آمار و لیست مقالات برای پنل مدیریت."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from blog.models import Category, Post, PostViewDaily, Tag

SCHEMA_VERSION = '1.0'


def get_blog_dashboard_stats() -> dict[str, Any]:
    now = timezone.now()
    month_ago = now - timedelta(days=30)
    week_ago = now - timedelta(days=7)

    qs = Post.objects.all()
    published_qs = qs.filter(is_published=True)

    total_views = qs.aggregate(total=Sum('views_count'))['total'] or 0
    published_views = published_qs.aggregate(total=Sum('views_count'))['total'] or 0

    recent_published = published_qs.filter(published_at__gte=month_ago).count()
    recent_created = qs.filter(created_at__gte=month_ago).count()

    top_posts = list(
        published_qs.select_related('category', 'author')
        .order_by('-views_count')[:8]
        .values(
            'id', 'title', 'slug', 'views_count', 'is_published',
            'published_at', 'category__name',
        )
    )

    categories = list(
        Category.objects.annotate(post_count=Count('post'))
        .order_by('-post_count', 'order', 'name')
        .values('id', 'name', 'slug', 'post_count')[:12]
    )

    tag_count = Tag.objects.count()

    return {
        'posts_total': qs.count(),
        'posts_published': published_qs.count(),
        'posts_draft': qs.filter(is_published=False).count(),
        'views_total': total_views,
        'views_published': published_views,
        'published_month': recent_published,
        'created_month': recent_created,
        'categories_total': Category.objects.count(),
        'tags_total': tag_count,
        'top_posts': top_posts,
        'categories': categories,
        'avg_views': round(published_views / max(published_qs.count(), 1)),
        'week_published': published_qs.filter(published_at__gte=week_ago).count(),
    }


def get_blog_posts_table(*, limit: int = 50, status: str = 'all') -> list[dict[str, Any]]:
    qs = Post.objects.select_related('category', 'author').prefetch_related('tags')
    if status == 'published':
        qs = qs.filter(is_published=True)
    elif status == 'draft':
        qs = qs.filter(is_published=False)

    rows = []
    for post in qs.order_by('-published_at', '-created_at')[:limit]:
        rows.append({
            'id': post.id,
            'title': post.title,
            'slug': post.slug,
            'author': post.author.get_full_name() or post.author.username,
            'category': post.category.name if post.category else '—',
            'category_slug': post.category.slug if post.category else '',
            'is_published': post.is_published,
            'views_count': post.views_count,
            'tag_count': post.tags.count(),
            'excerpt': post.excerpt[:120],
            'created_at': post.created_at,
            'updated_at': post.updated_at,
            'published_at': post.published_at,
            'url': post.get_absolute_url(),
        })
    return rows


def _pct_change(current: int, previous: int) -> float | None:
    if previous > 0:
        return round((current - previous) / previous * 100, 1)
    if current > 0:
        return 100.0
    return None


def _daily_views_map(*, start, end) -> dict:
    rows = (
        PostViewDaily.objects.filter(date__gte=start, date__lte=end)
        .values('date')
        .annotate(total=Sum('views'))
    )
    return {row['date']: row['total'] for row in rows}


def get_blog_traffic_pulse() -> dict[str, Any]:
    """شاخص‌های لحظه‌ای: امروز، دیروز، هفته جاری."""
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=6)
    prev_week_start = today - timedelta(days=13)
    prev_week_end = today - timedelta(days=7)

    today_views = _daily_views_map(start=today, end=today).get(today, 0)
    yesterday_views = _daily_views_map(start=yesterday, end=yesterday).get(yesterday, 0)

    week_map = _daily_views_map(start=week_start, end=today)
    prev_week_map = _daily_views_map(start=prev_week_start, end=prev_week_end)

    week_views = sum(week_map.values())
    prev_week_views = sum(prev_week_map.values())

    month_start = today - timedelta(days=29)
    month_views = sum(_daily_views_map(start=month_start, end=today).values())

    first_tracked = PostViewDaily.objects.order_by('date').values_list('date', flat=True).first()

    return {
        'today': today_views,
        'yesterday': yesterday_views,
        'today_vs_yesterday_pct': _pct_change(today_views, yesterday_views),
        'week': week_views,
        'prev_week': prev_week_views,
        'week_vs_prev_pct': _pct_change(week_views, prev_week_views),
        'month': month_views,
        'avg_daily_month': round(month_views / 30, 1),
        'tracking_since': first_tracked.isoformat() if first_tracked else None,
        'has_tracking_data': PostViewDaily.objects.exists(),
    }


def get_blog_traffic_analytics(*, days: int = 30) -> dict[str, Any]:
    """نمودار بازدید روزانه، مقایسه دوره‌ای و توزیع دسته."""
    days = max(7, min(days, 90))
    today = timezone.localdate()
    since = today - timedelta(days=days - 1)
    prev_since = since - timedelta(days=days)
    prev_until = since - timedelta(days=1)

    current_map = _daily_views_map(start=since, end=today)
    prev_map = _daily_views_map(start=prev_since, end=prev_until)

    labels: list[str] = []
    counts: list[int] = []
    prev_counts: list[int] = []
    for offset in range(days):
        day = since + timedelta(days=offset)
        prev_day = prev_since + timedelta(days=offset)
        labels.append(day.isoformat())
        counts.append(current_map.get(day, 0))
        prev_counts.append(prev_map.get(prev_day, 0))

    period_total = sum(counts)
    prev_period_total = sum(prev_counts)

    categories = list(
        PostViewDaily.objects.filter(date__gte=since, date__lte=today)
        .values('post__category__name', 'post__category__slug')
        .annotate(views=Sum('views'))
        .order_by('-views')[:10]
    )
    for row in categories:
        if not row['post__category__name']:
            row['post__category__name'] = 'بدون دسته'
            row['post__category__slug'] = ''

    top_posts_period = list(
        PostViewDaily.objects.filter(date__gte=since, date__lte=today)
        .values('post__id', 'post__title', 'post__slug')
        .annotate(views=Sum('views'))
        .order_by('-views')[:10]
    )

    return {
        'days': days,
        'period_total': period_total,
        'prev_period_total': prev_period_total,
        'period_delta_pct': _pct_change(period_total, prev_period_total),
        'avg_daily': round(period_total / days, 1) if days else 0,
        'views_daily': {
            'labels': labels,
            'counts': counts,
            'prev_counts': prev_counts,
        },
        'views_by_category': [
            {
                'name': row['post__category__name'],
                'slug': row['post__category__slug'],
                'views': row['views'],
            }
            for row in categories
        ],
        'top_posts_period': [
            {
                'id': row['post__id'],
                'title': row['post__title'],
                'slug': row['post__slug'],
                'views': row['views'],
            }
            for row in top_posts_period
        ],
    }


def get_blog_analytics_chart(days: int = 30) -> dict[str, Any]:
    """داده نمودار — انتشار، بازدید برتر و ترافیک روزانه."""
    days = max(7, min(days, 90))
    since = timezone.now() - timedelta(days=days)

    published_by_day = (
        Post.objects.filter(is_published=True, published_at__gte=since)
        .annotate(day=TruncDate('published_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    daily_labels = []
    daily_counts = []
    for row in published_by_day:
        if row['day']:
            daily_labels.append(row['day'].isoformat())
            daily_counts.append(row['count'])

    top_views = list(
        Post.objects.filter(is_published=True)
        .order_by('-views_count')[:10]
        .values('title', 'slug', 'views_count')
    )

    traffic = get_blog_traffic_analytics(days=days)
    pulse = get_blog_traffic_pulse()

    return {
        'days': days,
        'published_daily': {'labels': daily_labels, 'counts': daily_counts},
        'top_views': top_views,
        'traffic': traffic,
        'pulse': pulse,
    }


def build_blog_stats_json(
    *,
    days: int = 30,
    status: str = 'all',
    posts_limit: int = 1000,
) -> dict[str, Any]:
    """خروجی JSON کامل آمار مقالات برای پنل مدیریت."""
    if status not in ('all', 'published', 'draft'):
        status = 'all'

    now = timezone.now()
    stats = get_blog_dashboard_stats()
    analytics = get_blog_analytics_chart(days=days)
    posts = get_blog_posts_table(limit=posts_limit, status=status)

    return {
        'ok': True,
        'meta': {
            'generated_at': now.isoformat(),
            'source': 'admin_panel_blog',
            'version': SCHEMA_VERSION,
            'analytics_days': analytics['days'],
            'posts_status_filter': status,
            'posts_limit': posts_limit,
            'posts_exported': len(posts),
        },
        'summary': stats,
        'analytics': analytics,
        'traffic': analytics.get('traffic'),
        'pulse': analytics.get('pulse'),
        'posts': posts,
    }
