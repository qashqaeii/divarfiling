"""Tests for blog post SEO meta tags and structured data."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from blog.models import Category, Post, Tag
from blog.seo_helpers import format_iso_datetime

User = get_user_model()

FAQ_CONTENT = """
<h2>مقدمه</h2>
<p>متن نمونه.</p>
<h2>سوالات متداول</h2>
<h3>CRM رایگان است؟</h3>
<p>بله، میزکار CRM رایگان دارد.</p>
"""


@override_settings(
    SITE_URL='https://divarfiling.ir',
    ALLOWED_HOSTS=['testserver'],
    TWITTER_SITE='divarfiling',
)
class BlogPostSeoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='author', password='pass')
        self.category = Category.objects.create(
            slug='crm',
            name='CRM املاک',
        )
        self.post = Post.objects.create(
            title='نرم افزار CRM املاک',
            slug='narm-afzar-crm-amlak-rahnama-kamel',
            author=self.user,
            category=self.category,
            content=FAQ_CONTENT,
            excerpt='راهنمای CRM املاک',
            is_published=True,
            published_at=timezone.now(),
        )
        self.post.tags.add(Tag.objects.create(name='CRM', slug='crm'))

    def test_post_detail_article_meta_times(self):
        resp = self.client.get(self.post.get_absolute_url())
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn('property="article:published_time"', html)
        self.assertIn('property="article:modified_time"', html)
        published = format_iso_datetime(self.post.published_at)
        self.assertIn(f'content="{published}"', html)

    def test_post_detail_og_image_from_seed(self):
        resp = self.client.get(self.post.get_absolute_url())
        html = resp.content.decode('utf-8')
        self.assertIn('property="og:image"', html)
        self.assertIn('/static/images/og/blog/crm-amlak.jpg', html)

    def test_post_detail_twitter_site(self):
        resp = self.client.get(self.post.get_absolute_url())
        html = resp.content.decode('utf-8')
        self.assertIn('name="twitter:site" content="@divarfiling"', html)

    def test_post_detail_article_schema(self):
        resp = self.client.get(self.post.get_absolute_url())
        html = resp.content.decode('utf-8')
        self.assertIn('"@type": "Article"', html)
        self.assertIn('"datePublished"', html)
        self.assertIn('"dateModified"', html)
        self.assertIn('"wordCount"', html)
        self.assertIn('"articleSection": "CRM املاک"', html)
        self.assertIn('"keywords": "CRM"', html)

    def test_post_detail_faq_schema(self):
        resp = self.client.get(self.post.get_absolute_url())
        html = resp.content.decode('utf-8')
        self.assertIn('"@type": "FAQPage"', html)
        self.assertIn('"name": "نرم افزار CRM املاک"', html)
        self.assertIn('CRM رایگان است؟', html)
        self.assertIn('"isPartOf"', html)

    @override_settings(TWITTER_SITE='')
    def test_twitter_site_omitted_when_unset(self):
        resp = self.client.get(self.post.get_absolute_url())
        html = resp.content.decode('utf-8')
        self.assertNotIn('name="twitter:site"', html)
