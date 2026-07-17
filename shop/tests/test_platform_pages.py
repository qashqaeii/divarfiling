"""Tests for platform marketing pages — phase 1."""
import json
import re

from django.test import TestCase, override_settings

from shop.platform.registry import all_pages, get_page

PLATFORM_URLS = [
    '/features/',
    '/features/crm/',
    '/features/crm/reminders/',
    '/solutions/',
    '/solutions/customer-follow-up/',
]

SCHEMA_DOUBLE_WRAP = '<script type="application/ld+json"><script type="application/ld+json">'


def _extract_ld_json_blocks(html: str) -> list[str]:
    return re.findall(
        r'<script type="application/ld\+json">(.*?)</script>',
        html,
        re.DOTALL,
    )


def _assert_platform_seo_health(test_case, url: str) -> None:
    resp = test_case.client.get(url)
    test_case.assertEqual(resp.status_code, 200, url)
    body = resp.content.decode('utf-8')
    test_case.assertNotIn(SCHEMA_DOUBLE_WRAP, body, url)
    test_case.assertEqual(body.count('<h1'), 1, url)
    test_case.assertIn('rel="canonical"', body, url)
    test_case.assertIn('meta name="description"', body, url)
    test_case.assertIn('"@type": "WebPage"', body, url)
    test_case.assertIn('"@type": "FAQPage"', body, url)
    test_case.assertIn('"@type": "BreadcrumbList"', body, url)
    test_case.assertIn('"@type": "Organization"', body, url)
    test_case.assertIn('"@type": "SoftwareApplication"', body, url)
    test_case.assertIn('plat-sticky-cta', body, url)
    test_case.assertIn('image/webp', body, url)
    test_case.assertIn('fetchpriority', body, url)

    blocks = _extract_ld_json_blocks(body)
    test_case.assertGreaterEqual(len(blocks), 4, url)
    for block in blocks:
        json.loads(block.strip())


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
        self.assertContains(resp, 'fhub-outcomes')
        self.assertContains(resp, 'fhub-pillars')
        self.assertContains(resp, 'fhub-lifecycle')
        self.assertContains(resp, 'fhub-next')
        self.assertContains(resp, 'fhub-ico')
        self.assertContains(resp, 'help-crm-dashboard.png')
        self.assertContains(resp, 'help-crm-today.png')
        self.assertContains(resp, 'help-crm-deals.png')
        self.assertContains(resp, '/features/crm/')
        self.assertContains(resp, '/solutions/customer-follow-up/')
        self.assertContains(resp, '<h1', count=1)
        self.assertContains(resp, 'application/ld+json')
        self.assertContains(resp, 'BreadcrumbList')
        self.assertContains(resp, 'plat-faq__item', count=7)

    def test_crm_product_line(self):
        resp = self.client.get('/features/crm/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'CRM املاک')
        self.assertContains(resp, 'یک میزکار نگه دارید')
        self.assertContains(resp, 'crm-story')
        self.assertContains(resp, 'crm-outcomes')
        self.assertContains(resp, 'crm-flow-h')
        self.assertContains(resp, 'crm-next')
        self.assertContains(resp, 'crm-ico')
        self.assertContains(resp, 'fa-address-book')
        self.assertContains(resp, 'fa-bell')
        self.assertContains(resp, 'حریم خصوصی')
        self.assertContains(resp, 'help-crm-contacts.png')
        self.assertContains(resp, 'help-crm-today.png')
        self.assertContains(resp, 'help-crm-deals.png')
        self.assertContains(resp, '/real-estate-crm/')
        self.assertContains(resp, '/features/crm/reminders/')
        self.assertContains(resp, '/solutions/customer-follow-up/')
        self.assertContains(resp, 'plat-faq__item', count=7)

    def test_crm_reminders_feature(self):
        resp = self.client.get('/features/crm/reminders/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'یادآور')
        self.assertContains(resp, 'rem-timeline')
        self.assertContains(resp, 'rem-outcomes')
        self.assertContains(resp, 'rem-flow-h')
        self.assertContains(resp, 'rem-next')
        self.assertContains(resp, 'rem-ico')
        self.assertContains(resp, 'help-crm-reminders.png')
        self.assertContains(resp, 'help-crm-today.png')
        self.assertContains(resp, 'customer-follow-up')
        self.assertContains(resp, '/features/crm/')
        self.assertContains(resp, 'plat-faq__item', count=8)

    def test_solutions_hub(self):
        resp = self.client.get('/solutions/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'چالش دفتر املاک')
        self.assertContains(resp, 'shub-hero')
        self.assertContains(resp, 'shub-brand')
        self.assertContains(resp, 'shub-outcomes')
        self.assertContains(resp, 'shub-audience')
        self.assertContains(resp, 'shub-feature')
        self.assertContains(resp, 'shub-map')
        self.assertContains(resp, 'shub-next')
        self.assertContains(resp, 'shub-ico')
        self.assertContains(resp, 'plat-sticky-cta')
        self.assertContains(resp, '/solutions/customer-follow-up/')
        self.assertContains(resp, 'من مشاورم')
        self.assertContains(resp, 'من مدیر آژانسم')
        self.assertContains(resp, 'help-crm-today.png')
        self.assertContains(resp, 'help-crm-reminders.png')
        self.assertContains(resp, '/features/')
        self.assertContains(resp, 'plat-faq__item', count=7)
        self.assertNotContains(resp, 'Feature-first')
        self.assertNotContains(resp, 'Outcome-first')

    def test_customer_follow_up_solution(self):
        resp = self.client.get('/solutions/customer-follow-up/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'تماس دوم را از دست ندهید')
        self.assertContains(resp, 'sol-hero__story')
        self.assertContains(resp, 'sol-outcomes')
        self.assertContains(resp, 'sol-framework')
        self.assertContains(resp, 'sol-timeline')
        self.assertContains(resp, 'sol-next')
        self.assertContains(resp, 'sol-ico')
        self.assertContains(resp, 'help-crm-today.png')
        self.assertContains(resp, 'help-crm-reminders.png')
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
        self.assertContains(resp, 'mk-mega-panel__scroll')
        self.assertContains(resp, 'mk-mega-featured--compact')
        self.assertContains(resp, 'customer-follow-up')

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

    def test_schema_json_ld_not_double_wrapped(self):
        resp = self.client.get('/features/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertNotIn(
            '<script type="application/ld+json"><script type="application/ld+json">',
            body,
        )
        self.assertIn('"@type": "WebPage"', body)
        self.assertIn('"@type": "FAQPage"', body)
        self.assertIn('"@type": "BreadcrumbList"', body)
        self.assertIn('"@type": "SoftwareApplication"', body)
        self.assertIn('"@type": "Organization"', body)

    def test_crm_product_schema_entities(self):
        resp = self.client.get('/features/crm/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('"@type": "SoftwareApplication"', body)
        self.assertIn('"@type": "Product"', body)
        self.assertIn('CRM املاک', body)
        self.assertIn('"price": "0"', body)
        self.assertNotIn('AggregateRating', body)

    def test_reminders_and_follow_up_have_product(self):
        for url in ('/features/crm/reminders/', '/solutions/customer-follow-up/'):
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                body = resp.content.decode('utf-8')
                self.assertIn('"@type": "Product"', body)
                self.assertIn('"@type": "SoftwareApplication"', body)

    def test_all_platform_pages_schema_and_seo_health(self):
        for url in PLATFORM_URLS:
            with self.subTest(url=url):
                _assert_platform_seo_health(self, url)

    def test_sitemap_includes_all_platform_pages(self):
        resp = self.client.get('/sitemap-platform.xml')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        for url in PLATFORM_URLS:
            self.assertIn(url, body)
