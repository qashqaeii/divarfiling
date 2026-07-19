"""تست پنل مدیریت مقالات."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from blog.models import Category, Post
from blog.services.article_import import import_article_from_payload, validate_article_payload
from accounts.services.admin_blog import build_blog_stats_json

User = get_user_model()

SAMPLE_PAYLOAD = {
    'format_version': '1.0',
    'options': {
        'publish': True,
        'force_update': False,
        'author_username': 'admin',
    },
    'article': {
        'slug_base': 'test-admin-import-article',
        'title': 'مقاله تست درون‌ریزی',
        'excerpt': 'خلاصه کوتاه برای تست.',
        'category': {
            'slug': 'test-cat',
            'name': 'دسته تست',
            'description': '',
            'order': 1,
        },
        'tags': ['تست', 'CRM'],
        'content': '<p>پاراگراف تست.</p><h2>سرتیتر</h2><p>ادامه.</p>',
    },
}


class ArticleImportServiceTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(username='admin', password='pass1234', email='a@test.com')

    def test_validate_ok(self):
        preview = validate_article_payload(SAMPLE_PAYLOAD)
        self.assertTrue(preview.ok)
        self.assertEqual(preview.action, 'create')

    def test_import_creates_post(self):
        post, action = import_article_from_payload(SAMPLE_PAYLOAD)
        self.assertEqual(action, 'created')
        self.assertTrue(post.is_published)
        self.assertEqual(post.tags.count(), 2)
        self.assertEqual(Category.objects.filter(slug='test-cat').count(), 1)

    def test_import_skips_existing(self):
        import_article_from_payload(SAMPLE_PAYLOAD)
        post, action = import_article_from_payload(SAMPLE_PAYLOAD)
        self.assertEqual(action, 'skipped')

    def test_import_force_update(self):
        import_article_from_payload(SAMPLE_PAYLOAD)
        payload = json.loads(json.dumps(SAMPLE_PAYLOAD))
        payload['options']['force_update'] = True
        payload['article']['title'] = 'عنوان به‌روز شده'
        post, action = import_article_from_payload(payload)
        self.assertEqual(action, 'updated')
        self.assertEqual(post.title, 'عنوان به‌روز شده')


class AdminBlogPanelTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staffblog', password='pass1234', phone='09121111111', is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)

    def test_blog_panel_requires_staff(self):
        guest = Client()
        resp = guest.get(reverse('admin_panel_blog'))
        self.assertEqual(resp.status_code, 302)

    def test_blog_panel_loads(self):
        resp = self.client.get(reverse('admin_panel_blog'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'مدیریت مقالات')

    def test_import_api(self):
        User.objects.create_superuser(username='admin', password='pass1234', email='b@test.com')
        resp = self.client.post(
            reverse('admin_panel_blog_import'),
            data=json.dumps(SAMPLE_PAYLOAD),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertTrue(Post.objects.filter(slug='test-admin-import-article').exists())

    def test_preview_api_invalid(self):
        resp = self.client.post(
            reverse('admin_panel_blog_import_preview'),
            data='not json',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_blog_stats_json_requires_staff(self):
        guest = Client()
        resp = guest.get(reverse('admin_panel_blog_stats_json'))
        self.assertEqual(resp.status_code, 302)

    def test_blog_stats_json_returns_payload(self):
        author = User.objects.create_user(username='blogstats', password='pass1234')
        Post.objects.create(
            title='مقاله آمار',
            slug='blog-stats-test',
            author=author,
            content='<p>تست</p>',
            excerpt='خلاصه',
            is_published=True,
        )
        resp = self.client.get(reverse('admin_panel_blog_stats_json'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('summary', data)
        self.assertIn('analytics', data)
        self.assertIn('posts', data)
        self.assertGreaterEqual(data['summary']['posts_total'], 1)

    def test_blog_stats_json_download(self):
        resp = self.client.get(reverse('admin_panel_blog_stats_json'), {'download': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('blog-stats-', resp['Content-Disposition'])


class BlogStatsJsonServiceTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username='blogsvc', password='pass1234')

    def test_build_blog_stats_json_structure(self):
        Post.objects.create(
            title='سرویس آمار',
            slug='blog-stats-service',
            author=self.author,
            content='<p>تست</p>',
            excerpt='خلاصه',
            is_published=True,
        )
        payload = build_blog_stats_json(days=30, status='published', posts_limit=50)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['meta']['analytics_days'], 30)
        self.assertEqual(payload['meta']['posts_status_filter'], 'published')
        self.assertIn('published_daily', payload['analytics'])
        self.assertEqual(len(payload['posts']), 1)


class DraftPostPreviewTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username='blogauth', password='pass1234')
        self.staff = User.objects.create_user(
            username='staffprev', password='pass1234', phone='09123333333', is_staff=True,
        )
        self.draft = Post.objects.create(
            title='پیش‌نویس تست',
            slug='sample-filing-divar-rahnama-kamel',
            author=self.author,
            content='<p>تست</p><h2>بخش</h2>',
            excerpt='خلاصه',
            is_published=False,
        )

    def test_draft_returns_404_for_public(self):
        resp = Client().get(reverse('blog:post_detail', kwargs={'slug': self.draft.slug}))
        self.assertEqual(resp.status_code, 404)

    def test_draft_visible_for_staff(self):
        client = Client()
        client.force_login(self.staff)
        resp = client.get(reverse('blog:post_detail', kwargs={'slug': self.draft.slug}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'پیش‌نویس')
