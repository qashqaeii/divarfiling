"""
وارد کردن مقالات فاز B — فایلینگ املاک و قیمت‌گذاری

مثال:
    python manage.py seed_phase_b_articles --publish
    python manage.py seed_phase_b_articles --force --publish
    python manage.py seed_phase_b_articles --slug filing-amlak-yani-chi --publish
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from blog.models import Category, Post
from blog.phase_b_content import PHASE_B_ARTICLES
from blog.utils import get_or_create_tag, unique_post_slug

User = get_user_model()


class Command(BaseCommand):
    help = 'وارد کردن مقالات فاز B (فایلینگ املاک و قیمت‌گذاری)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--slug',
            type=str,
            help='فقط یک slug مشخص (مثلاً filing-amlak-yani-chi)',
        )
        parser.add_argument(
            '--author-username',
            type=str,
            default='admin',
            help='نام کاربری نویسنده',
        )
        parser.add_argument('--publish', action='store_true', help='انتشار فوری')
        parser.add_argument('--force', action='store_true', help='بازنویسی در صورت وجود')

    def handle(self, *args, **options):
        slugs = [options['slug']] if options.get('slug') else list(PHASE_B_ARTICLES.keys())
        author = self._resolve_author(options['author_username'])
        publish = options['publish']
        force = options['force']

        for slug_base in slugs:
            if slug_base not in PHASE_B_ARTICLES:
                raise CommandError(f'slug نامعتبر: {slug_base}')
            self._import_article(PHASE_B_ARTICLES[slug_base], author, publish, force)

        self.stdout.write(self.style.SUCCESS(f'\nDone: {len(slugs)} phase B article(s)'))

    def _import_article(self, article, author, publish, force):
        cat_data = article['category']
        category, _ = Category.objects.get_or_create(
            slug=cat_data['slug'],
            defaults={
                'name': cat_data['name'],
                'description': cat_data.get('description', ''),
                'order': cat_data.get('order', 0),
            },
        )

        tags = [get_or_create_tag(tag_name) for tag_name in article['tags']]

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
            self.stdout.write(self.style.WARNING(
                f'Skipped (exists): {existing.slug} — use --force'
            ))
            post = existing
        elif existing:
            for key, val in defaults.items():
                setattr(existing, key, val)
            existing.save()
            post = existing
            self.stdout.write(self.style.SUCCESS(f'Updated: {post.title}'))
        else:
            post = Post.objects.create(slug=slug, **defaults)
            self.stdout.write(self.style.SUCCESS(f'Created: {post.title}'))

        post.tags.set(tags)
        self.stdout.write(f'  → /blog/{post.slug}/')

    def _resolve_author(self, username):
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            author = User.objects.filter(is_superuser=True).order_by('pk').first()
            if not author:
                raise CommandError('superuser یافت نشد — createsuperuser اجرا کنید')
            self.stdout.write(self.style.WARNING(
                f'Using author "{author.username}" (requested user not found)'
            ))
            return author
