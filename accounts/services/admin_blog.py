"""آمار و لیست مقالات برای پنل مدیریت."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from blog.models import Category, Post, Tag

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


def get_blog_analytics_chart(days: int = 30) -> dict[str, Any]:
    """داده نمودار — انتشار و بازدید برتر."""
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

    return {
        'days': days,
        'published_daily': {'labels': daily_labels, 'counts': daily_counts},
        'top_views': top_views,
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
        'posts': posts,
    }
