"""تست پنل مدیریت مقالات."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from blog.models import Category, Post
from blog.services.article_import import import_article_from_payload, validate_article_payload

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
