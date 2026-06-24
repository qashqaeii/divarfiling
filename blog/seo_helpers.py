"""ابزارهای مشترک SEO برای مقالات بلاگ."""
from __future__ import annotations

from django.conf import settings
from django.utils import timezone


def format_iso_datetime(value) -> str:
    """تبدیل datetime یا رشته ISO به فرمت ISO 8601 برای meta/schema."""
    if value is None:
        return ''
    if hasattr(value, 'isoformat'):
        dt = value
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt.isoformat()
    return str(value).strip()


def absolute_url(path_or_url, request=None) -> str:
    if not path_or_url:
        return ''
    text = str(path_or_url)
    if text.startswith('http'):
        return text
    path = text if text.startswith('/') else f'/{text}'
    if request:
        return request.build_absolute_uri(path)
    site_url = getattr(settings, 'SITE_URL', 'https://divarfiling.ir').rstrip('/')
    return f'{site_url}{path}'


def post_published_at(post):
    return post.published_at or post.created_at


def post_modified_at(post):
    return post.updated_at or post.published_at or post.created_at


def post_og_static_path(post) -> str | None:
    """مسیر static اختصاصی og:image از seed مقاله (در صورت تعریف)."""
    try:
        from blog.seo_article_seed import SEO_ARTICLES
    except ImportError:
        return None

    for article in SEO_ARTICLES.values():
        slug_base = article.get('slug_base', '')
        if post.slug == slug_base or post.slug.startswith(f'{slug_base}-'):
            return article.get('og_image')
    return None


def post_og_image_url(post, request=None) -> str:
    """URL مطلق og:image — اولویت: تصویر شاخص، سپس static اختصاصی، سپس لوگو."""
    if post.featured_image:
        try:
            return absolute_url(post.featured_image.url, request)
        except Exception:
            pass

    static_rel = post_og_static_path(post)
    if static_rel:
        if static_rel.startswith('http'):
            return static_rel
        path = static_rel if static_rel.startswith('/') else f'/static/{static_rel.lstrip("/")}'
        return absolute_url(path, request)

    return absolute_url('/static/logo.png', request)


def post_word_count(post) -> int:
    from django.utils.html import strip_tags

    return len(strip_tags(post.content or '').split())


def post_keywords(post) -> str:
    names = list(post.tags.values_list('name', flat=True))
    return ', '.join(names)
