"""Views for platform marketing pages."""
from __future__ import annotations

from django.http import Http404
from django.views.generic import TemplateView

from blog.models import Post
from shop.platform.content.phase1 import build_page_content
from shop.platform.registry import get_page
from shop.platform.schema import (
    build_breadcrumbs,
    combine_schemas,
    schema_faq_from_pairs,
    schema_webpage,
)


class PlatformFeaturesView(TemplateView):
    template_name = 'platform/page.html'

    def dispatch(self, request, *args, **kwargs):
        slug_path = kwargs.get('slug_path', '').strip('/')
        if not get_page('features', slug_path):
            raise Http404('صفحه یافت نشد')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        slug_path = kwargs.get('slug_path', '').strip('/')
        page = get_page('features', slug_path)
        return _build_platform_context(self.request, page, ctx)


class PlatformSolutionsView(TemplateView):
    template_name = 'platform/page.html'

    def dispatch(self, request, *args, **kwargs):
        slug = kwargs.get('slug', '').strip('/')
        if not get_page('solutions', slug):
            raise Http404('صفحه یافت نشد')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        slug = kwargs.get('slug', '').strip('/')
        page = get_page('solutions', slug)
        return _build_platform_context(self.request, page, ctx)


def _build_platform_context(request, page, ctx: dict) -> dict:
    content = build_page_content(page.content_key)
    page_url = request.build_absolute_uri(page.url_path)
    breadcrumbs = build_breadcrumbs(page)

    faq = content.get('faq', [])
    schema_parts = [
        schema_webpage(page, page_url),
        schema_faq_from_pairs(faq, page, page_url) if faq else '',
    ]

    ctx.update({
        'platform_page': page,
        'platform_content': content,
        'breadcrumbs': breadcrumbs,
        'meta_title': page.seo.title,
        'meta_description': page.seo.description,
        'meta_keywords': page.seo.keywords,
        'og_type': 'website',
        'schema_data': combine_schemas(*schema_parts),
        'related_posts': _related_posts(page),
    })
    return ctx


def _related_posts(page) -> list[Post]:
    slugs = page.related_articles
    if not slugs:
        return []
    posts = Post.objects.filter(is_published=True, slug__in=slugs).select_related('category')
    by_slug = {p.slug: p for p in posts}
    return [by_slug[s] for s in slugs if s in by_slug]
