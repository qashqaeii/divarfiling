"""
ویوهای بلاگ
"""
from django.db.models import Count, Q
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags
from django.views.generic import ListView, DetailView
from .models import Post, Category
from .services.view_tracking import record_post_view
from .post_seo_extras import get_post_seo_extras
from .seo_helpers import (
    format_iso_datetime,
    post_modified_at,
    post_og_image_url,
    post_published_at,
)


def _reading_time_minutes(html_content: str) -> int:
    words = len(strip_tags(html_content or '').split())
    return max(1, round(words / 200))


def _meta_description(post: Post, limit: int = 160) -> str:
    if post.excerpt:
        return post.excerpt[:limit]
    plain = strip_tags(post.content or '')
    return plain[:limit].rsplit(' ', 1)[0] if len(plain) > limit else plain


class PostListView(ListView):
    model = Post
    template_name = 'blog/post_list.html'
    context_object_name = 'posts'
    paginate_by = 12

    def get_queryset(self):
        queryset = (
            Post.objects.filter(is_published=True)
            .select_related('category', 'author')
            .prefetch_related('tags')
        )
        category_slug = self.kwargs.get('category_slug') or self.request.GET.get('cat')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        posts = context.get('posts')
        page_obj = context.get('page_obj')
        active_cat = self.request.GET.get('cat', '')

        context['categories'] = (
            Category.objects.annotate(post_count=Count('post', filter=Q(post__is_published=True)))
            .filter(post_count__gt=0)
            .order_by('order', 'name')
        )
        context['active_category'] = active_cat
        context['total_posts'] = Post.objects.filter(is_published=True).count()
        context['meta_title'] = 'مقالات تخصصی املاک و فایلینگ دیوار'
        context['meta_description'] = (
            'راهنماهای CRM، تحلیل بازار، استخراج دیوار و گردش کار حرفه‌ای '
            'برای مشاوران و آژانس‌های املاک — فایلینگ دیوار'
        )
        context['meta_keywords'] = (
            'مقالات املاک, CRM مشاور, تحلیل بازار دیوار, فایلینگ دیوار, ربات استخراج'
        )

        if page_obj and page_obj.number == 1 and posts:
            post_list = list(posts)
            context['featured_post'] = post_list[0]
            context['grid_posts'] = post_list[1:]
            context['reveal_start_index'] = 0
        else:
            context['featured_post'] = None
            context['grid_posts'] = posts
            if page_obj:
                per_page = self.paginate_by or 12
                context['reveal_start_index'] = (page_obj.number - 1) * per_page
            else:
                context['reveal_start_index'] = 0

        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get('partial') == '1':
            page_obj = context.get('page_obj')
            html = render_to_string(
                'blog/includes/post_grid_items.html',
                {
                    'grid_posts': context.get('grid_posts'),
                    'reveal_start_index': context.get('reveal_start_index', 0),
                },
                request=self.request,
            )
            return JsonResponse({
                'html': html,
                'has_next': bool(page_obj and page_obj.has_next()),
                'next_page': page_obj.next_page_number() if page_obj and page_obj.has_next() else None,
            })
        return super().render_to_response(context, **response_kwargs)


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        qs = (
            Post.objects.select_related('category', 'author')
            .prefetch_related('tags')
        )
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return qs
        return qs.filter(is_published=True)

    def get_object(self):
        obj = super().get_object()
        if obj.is_published:
            obj.views_count += 1
            obj.save(update_fields=['views_count'])
            record_post_view(obj)
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = context['post']
        context['is_draft_preview'] = not post.is_published
        context['reading_time'] = _reading_time_minutes(post.content)
        context['meta_title'] = post.title
        context['meta_description'] = _meta_description(post)
        tag_names = list(post.tags.values_list('name', flat=True))
        if tag_names:
            context['meta_keywords'] = ', '.join(tag_names)
        context['og_type'] = 'article'
        context['published_time'] = format_iso_datetime(post_published_at(post))
        context['modified_time'] = format_iso_datetime(post_modified_at(post))
        og_image = post_og_image_url(post, self.request)
        context['meta_image'] = og_image
        context['og_image'] = og_image
        context['author'] = post.author.get_full_name() or post.author.username
        context['breadcrumb_items'] = [
            {'name': 'خانه', 'url': '/'},
            {'name': 'مقالات', 'url': reverse('blog:post_list')},
        ]
        if post.category:
            context['breadcrumb_items'].append({
                'name': post.category.name,
                'url': f"{reverse('blog:post_list')}?cat={post.category.slug}",
            })
        context['breadcrumb_items'].append({'name': post.title, 'url': post.get_absolute_url()})

        published = Post.objects.filter(is_published=True).order_by('-published_at', '-created_at')
        post_ids = list(published.values_list('pk', flat=True))

        try:
            idx = post_ids.index(post.pk)
            if idx > 0:
                context['newer_post'] = published.filter(pk=post_ids[idx - 1]).first()
            if idx < len(post_ids) - 1:
                context['older_post'] = published.filter(pk=post_ids[idx + 1]).first()
        except ValueError:
            pass

        related_qs = published.exclude(pk=post.pk).select_related('category', 'author')
        extras = get_post_seo_extras(post.slug)
        context['post_seo_extras'] = extras
        if extras.get('related_slugs'):
            slugs = extras['related_slugs']
            related = list(related_qs.filter(slug__in=slugs)[:3])
            slug_order = {s: i for i, s in enumerate(slugs)}
            related.sort(key=lambda p: slug_order.get(p.slug, 99))
            context['related_posts'] = related
        elif post.category_id:
            context['related_posts'] = related_qs.filter(category=post.category)[:3]
        else:
            context['related_posts'] = related_qs[:3]

        return context
