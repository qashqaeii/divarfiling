"""
ویوهای بلاگ
"""
from django.db.models import Count, Q
from django.utils.html import strip_tags
from django.views.generic import ListView, DetailView
from .models import Post, Category


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
        else:
            context['featured_post'] = None
            context['grid_posts'] = posts

        return context


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/post_detail.html'
    context_object_name = 'post'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return (
            Post.objects.filter(is_published=True)
            .select_related('category', 'author')
            .prefetch_related('tags')
        )

    def get_object(self):
        obj = super().get_object()
        obj.views_count += 1
        obj.save(update_fields=['views_count'])
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        post = context['post']
        context['reading_time'] = _reading_time_minutes(post.content)
        context['meta_title'] = post.title
        context['meta_description'] = _meta_description(post)
        tag_names = list(post.tags.values_list('name', flat=True))
        if tag_names:
            context['meta_keywords'] = ', '.join(tag_names)
        context['og_type'] = 'article'
        if post.published_at:
            context['published_time'] = post.published_at.isoformat()
        context['modified_time'] = post.updated_at.isoformat()
        context['author'] = post.author.get_full_name() or post.author.username

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
        if post.category_id:
            context['related_posts'] = related_qs.filter(category=post.category)[:3]
        else:
            context['related_posts'] = related_qs[:3]

        return context
