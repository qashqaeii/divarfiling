"""Tests for Phase A SEO articles."""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils.html import strip_tags

from blog.models import Post
from blog.phase_a_content import PHASE_A_ARTICLES
from blog.post_seo_extras import get_post_seo_extras

User = get_user_model()

PHASE_A_SLUGS = list(PHASE_A_ARTICLES.keys())


@override_settings(
    SITE_URL='https://divarfiling.ir',
    ALLOWED_HOSTS=['testserver'],
)
class PhaseAArticleContentTests(TestCase):
    def test_word_count_in_range(self):
        for slug, article in PHASE_A_ARTICLES.items():
            words = len(strip_tags(article['content']).split())
            self.assertGreaterEqual(
                words, 1200,
                msg=f'{slug}: {words} words (min 1200)',
            )
            self.assertLessEqual(
                words, 1800,
                msg=f'{slug}: {words} words (max 1800)',
            )

    def test_each_has_faq_section(self):
        for slug, article in PHASE_A_ARTICLES.items():
            self.assertIn('سوالات متداول', article['content'], slug)
            self.assertGreaterEqual(
                article['content'].count('<h3>'), 5,
                msg=f'{slug} needs FAQ h3 items',
            )

    def test_seo_extras_pillar_and_related(self):
        for slug in PHASE_A_SLUGS:
            extras = get_post_seo_extras(slug)
            self.assertIn('pillar_url_name', extras, slug)
            self.assertIn('related_slugs', extras, slug)
            self.assertTrue(extras['related_slugs'], slug)


@override_settings(
    SITE_URL='https://divarfiling.ir',
    ALLOWED_HOSTS=['testserver'],
)
class PhaseAArticleViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_superuser(username='admin', password='pass', email='a@b.c')
        call_command('seed_phase_a_articles', '--publish', '--force', '--author-username', 'admin')

    def test_all_phase_a_urls_return_200(self):
        for slug in PHASE_A_SLUGS:
            resp = self.client.get(f'/blog/{slug}/')
            self.assertEqual(resp.status_code, 200, slug)

    def test_pillar_cta_on_crm_article(self):
        resp = self.client.get('/blog/crm-amlak-raygan-rahnama/')
        html = resp.content.decode('utf-8')
        self.assertIn('CRM مشاور املاک', html)
        self.assertIn('/real-estate-crm/', html)
        self.assertIn('author/hossein-qashqaeii', html)

    def test_toc_and_schema_on_phase_a_post(self):
        post = Post.objects.get(slug='chetor-agahi-divar-download')
        resp = self.client.get(post.get_absolute_url())
        html = resp.content.decode('utf-8')
        self.assertIn('"@type": "Article"', html)
        self.assertIn('"@type": "FAQPage"', html)
        self.assertIn('mk-blog-toc', html)

    def test_related_posts_from_extras(self):
        resp = self.client.get('/blog/crm-amlak-online-vs-excel/')
        html = resp.content.decode('utf-8')
        self.assertIn('crm-amlak-raygan-rahnama', html)
        self.assertIn('peigiri-moshtari-moshaver-amlak', html)
