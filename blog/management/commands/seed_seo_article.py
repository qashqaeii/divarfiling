"""
وارد کردن مقاله سئو بر اساس شماره کلمه کلیدی در seo-keywords.txt

مثال:
    python manage.py seed_seo_article --keyword 1 --publish
    python manage.py seed_seo_article --keyword 1 --force --publish
    python manage.py seed_seo_article --list
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from blog.models import Category, Post, Tag
from blog.seo_article_seed import SEO_ARTICLES
from blog.utils import persian_to_slug, unique_post_slug

User = get_user_model()


class Command(BaseCommand):
    help = 'وارد کردن یک مقاله سئو حرفه‌ای بر اساس شماره کلمه کلیدی (seo-keywords.txt)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keyword',
            type=int,
            help='شماره کلمه کلیدی (۱ تا ۵۰ مطابق seo-keywords.txt)',
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='نمایش فهرست مقالات آماده برای import',
        )
        parser.add_argument(
            '--author-username',
            type=str,
            default='admin',
            help='نام کاربری نویسنده (پیش‌فرض: admin)',
        )
        parser.add_argument(
            '--publish',
            action='store_true',
            help='مقاله را بلافاصله منتشر کند',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='اگر مقاله با همین slug وجود دارد، محتوا را بازنویسی کند',
        )

    def handle(self, *args, **options):
        if options['list']:
            self._list_articles()
            return

        keyword_num = options.get('keyword')
        if not keyword_num:
            raise CommandError(
                'شماره کلمه کلیدی را مشخص کنید: --keyword 1\n'
                'یا فهرست را ببینید: --list'
            )

        if keyword_num not in SEO_ARTICLES:
            available = ', '.join(str(k) for k in sorted(SEO_ARTICLES))
            raise CommandError(
                f'مقاله برای کلمه #{keyword_num} هنوز آماده نشده.\n'
                f'مقالات موجود: {available or "هیچ"}'
            )

        article = SEO_ARTICLES[keyword_num]
        author = self._resolve_author(options['author_username'])
        publish = options['publish']
        force = options['force']

        self.stdout.write(self.style.SUCCESS(
            f'در حال import مقاله سئو — کلمه #{keyword_num}: «{article["keyword"]}»'
        ))

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
                defaults={
                    'slug': persian_to_slug(tag_name) or f'tag-{Tag.objects.count() + 1}',
                },
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
            self.stdout.write(self.style.WARNING(
                f'مقاله از قبل وجود دارد: «{existing.title}» (slug: {existing.slug})\n'
                'برای بازنویسی از --force استفاده کنید.'
            ))
            post = existing
        elif existing:
            for key, val in defaults.items():
                setattr(existing, key, val)
            existing.save()
            post = existing
            self.stdout.write(self.style.SUCCESS(f'به‌روزرسانی شد: {post.title}'))
        else:
            post = Post.objects.create(slug=slug, **defaults)
            self.stdout.write(self.style.SUCCESS(f'ایجاد شد: {post.title}'))

        post.tags.set(tags)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✅ مقاله سئو با موفقیت وارد سیستم شد'))
        self.stdout.write(f'  شناسه: {post.id}')
        self.stdout.write(f'  عنوان: {post.title}')
        self.stdout.write(f'  slug: {post.slug}')
        self.stdout.write(f'  کلمه کلیدی: {article["keyword"]}')
        self.stdout.write(f'  دسته‌بندی: {category.name}')
        self.stdout.write(f'  وضعیت: {"منتشر شده" if post.is_published else "پیش‌نویس"}')
        if not publish:
            self.stdout.write(self.style.WARNING(
                'برای انتشار عمومی: --publish'
            ))

    def _list_articles(self):
        self.stdout.write(self.style.SUCCESS('مقالات سئو آماده برای import:\n'))
        for num in sorted(SEO_ARTICLES):
            art = SEO_ARTICLES[num]
            self.stdout.write(f'  [{num:2d}] {art["keyword"]}')
            self.stdout.write(f'       → {art["title"][:70]}…')
            self.stdout.write(f'       slug: {art["slug_base"]}\n')

        pending = 50 - len(SEO_ARTICLES)
        if pending > 0:
            self.stdout.write(self.style.WARNING(
                f'({pending} کلمه دیگر هنوز محتوا ندارند — به‌تدریج اضافه می‌شوند)'
            ))

    def _resolve_author(self, username):
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist:
            author = User.objects.filter(is_superuser=True).order_by('pk').first()
            if not author:
                raise CommandError(
                    f'کاربر «{username}» یافت نشد و superuser هم وجود ندارد.\n'
                    'ابتدا createsuperuser اجرا کنید.'
                )
            self.stdout.write(self.style.WARNING(
                f'کاربر «{username}» یافت نشد؛ از «{author.username}» استفاده شد.'
            ))
            return author
