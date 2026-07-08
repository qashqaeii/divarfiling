"""ایجاد پنج مقاله موج C — فیچرهای جدید CRM و فایلینگ."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.models import Category, Post, Tag
from blog.utils import persian_to_slug, unique_post_slug
from blog.wave_c_content import WAVE_C_ARTICLES

User = get_user_model()


class Command(BaseCommand):
    help = 'ایجاد یا به‌روزرسانی پنج مقاله موج C فایلینگ دیوار'

    def add_arguments(self, parser):
        parser.add_argument('--author-username', type=str, default='qashqaeii')
        parser.add_argument('--publish', action='store_true')
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        publish = options['publish']
        force = options['force']

        try:
            author = User.objects.get(username=options['author_username'])
        except User.DoesNotExist:
            author = User.objects.filter(is_superuser=True).order_by('pk').first()
            if not author:
                self.stdout.write(self.style.ERROR('نویسنده یافت نشد.'))
                return

        created = updated = 0
        for article in WAVE_C_ARTICLES:
            cat_data = article['category']
            category, _ = Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data.get('description', ''),
                    'order': cat_data.get('order', 0),
                },
            )
            tags = []
            for tag_name in article['tags']:
                tag, _ = Tag.objects.get_or_create(
                    name=tag_name,
                    defaults={'slug': persian_to_slug(tag_name) or f'tag-{Tag.objects.count() + 1}'},
                )
                tags.append(tag)

            slug_base = article['slug_base']
            existing = Post.objects.filter(slug=slug_base).first()
            slug = existing.slug if existing else unique_post_slug(slug_base)
            defaults = {
                'title': article['title'],
                'author': author,
                'category': category,
                'content': article['content'].strip(),
                'excerpt': article['excerpt'][:300],
                'is_published': publish,
                'published_at': timezone.now() if publish else None,
            }
            if existing and not force:
                self.stdout.write(self.style.WARNING(f'رد شد (موجود): {existing.title}'))
                post = existing
            elif existing:
                for key, val in defaults.items():
                    setattr(existing, key, val)
                existing.save()
                post = existing
                updated += 1
                self.stdout.write(self.style.SUCCESS(f'به‌روز شد: {post.title}'))
            else:
                post = Post.objects.create(slug=slug, **defaults)
                created += 1
                self.stdout.write(self.style.SUCCESS(f'ایجاد شد: {post.title}'))
            post.tags.set(tags)

        self.stdout.write(self.style.SUCCESS(f'✅ {created} ایجاد، {updated} به‌روزرسانی'))
        if not publish:
            self.stdout.write(self.style.WARNING('برای انتشار: --publish'))
