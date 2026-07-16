"""Tests for platform marketing pages — phase 1."""
from django.test import TestCase, override_settings

from shop.platform.registry import all_pages, get_page


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class PlatformRegistryTests(TestCase):
    def test_phase1_page_count(self):
        published = [p for p in all_pages() if p.is_published]
        self.assertEqual(len(published), 5)

    def test_all_pages_have_seo(self):
        for page in all_pages():
            self.assertTrue(page.seo.title)
            self.assertTrue(page.seo.description)
            self.assertTrue(page.seo.h1 or page.seo.title)

    def test_get_page_features_crm_reminders(self):
        page = get_page('features', 'crm/reminders')
        self.assertIsNotNone(page)
        self.assertEqual(page.variant, 'feature')


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class PlatformPageViewTests(TestCase):
    def test_features_hub(self):
        resp = self.client.get('/features/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'نقشه امکانات')
        self.assertContains(resp, 'fhub-hero')
        self.assertContains(resp, 'fhub-pillars')
        self.assertContains(resp, 'fhub-lifecycle')
        self.assertContains(resp, 'help-crm-dashboard.png')
        self.assertContains(resp, '/features/crm/')
        self.assertContains(resp, '/solutions/customer-follow-up/')
        self.assertContains(resp, '<h1', count=1)
        self.assertContains(resp, 'application/ld+json')
        self.assertContains(resp, 'BreadcrumbList')
        self.assertContains(resp, 'plat-faq__item', count=6)

    def test_crm_product_line(self):
        resp = self.client.get('/features/crm/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'CRM املاک')
        self.assertContains(resp, 'یک میزکار نگه دارید')
        self.assertContains(resp, 'crm-chaos')
        self.assertContains(resp, 'حریم خصوصی')
        self.assertContains(resp, 'help-crm-contacts.png')
        self.assertContains(resp, '/real-estate-crm/')
        self.assertContains(resp, 'plat-faq__item', count=7)

    def test_crm_reminders_feature(self):
        resp = self.client.get('/features/crm/reminders/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'یادآور')
        self.assertContains(resp, 'rem-timeline')
        self.assertContains(resp, 'help-crm-reminders.png')
        self.assertContains(resp, 'customer-follow-up')
        self.assertContains(resp, 'plat-faq__item', count=8)

    def test_solutions_hub(self):
        resp = self.client.get('/solutions/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'از مشکل شما شروع')
        self.assertContains(resp, 'shub-hero')
        self.assertContains(resp, 'shub-showcase')
        self.assertContains(resp, 'shub-map')
        self.assertContains(resp, '/solutions/customer-follow-up/')
        self.assertContains(resp, '/features/')
        self.assertContains(resp, 'plat-faq__item', count=6)

    def test_customer_follow_up_solution(self):
        resp = self.client.get('/solutions/customer-follow-up/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'تماس دوم را از دست ندهید')
        self.assertContains(resp, 'sol-hero__story')
        self.assertContains(resp, 'sol-framework')
        self.assertContains(resp, 'sol-timeline')
        self.assertContains(resp, 'help-crm-today.png')
        self.assertContains(resp, '/features/crm/reminders/')
        self.assertContains(resp, 'plat-faq__item', count=8)

    def test_unknown_feature_404(self):
        resp = self.client.get('/features/crm/unknown-feature/')
        self.assertEqual(resp.status_code, 404)

    def test_unknown_solution_404(self):
        resp = self.client.get('/solutions/unknown-slug/')
        self.assertEqual(resp.status_code, 404)

    def test_nav_mega_menu(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'mkFeaturesMenuBtn')
        self.assertContains(resp, 'امکانات')
        self.assertContains(resp, '/features/crm/')

    def test_sitemap_includes_platform(self):
        resp = self.client.get('/sitemap-platform.xml')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('/features/', body)
        self.assertIn('/features/crm/reminders/', body)
        self.assertIn('/solutions/customer-follow-up/', body)

    def test_meta_canonical_present(self):
        resp = self.client.get('/features/crm/reminders/')
        self.assertContains(resp, 'rel="canonical"')
        self.assertContains(resp, 'meta name="description"')
