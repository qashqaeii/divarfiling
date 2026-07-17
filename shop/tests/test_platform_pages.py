"""Tests for platform marketing pages — phase 1."""
import json
import re

from django.test import TestCase, override_settings

from shop.platform.registry import all_pages, get_page

PLATFORM_URLS = [
    '/features/',
    '/features/crm/',
    '/features/crm/reminders/',
    '/features/filing/',
    '/features/market-intelligence/',
    '/features/agency/',
    '/features/extraction/',
    '/solutions/',
    '/solutions/customer-follow-up/',
    '/solutions/fast-property-search/',
    '/solutions/build-property-database/',
    '/solutions/property-pricing/',
    '/solutions/agency-management/',
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
        self.assertGreaterEqual(len(published), 7)
        self.assertIsNotNone(get_page('features', 'filing'))
        self.assertIsNotNone(get_page('solutions', 'fast-property-search'))
        # Draft features exist but are not routable
        self.assertIsNone(get_page('features', 'filing/search'))
        drafts = [p for p in all_pages() if p.status == 'draft']
        self.assertGreaterEqual(len(drafts), 3)

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


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class PlatformNavigationPhaseDTests(TestCase):
    """Phase D: path, breadcrumb, active menu, guest/auth, exactly 3 next paths."""

    def test_exactly_three_next_paths_on_all_pages(self):
        from shop.platform.content.phase1 import build_page_content
        from shop.platform.registry import all_pages

        for page in all_pages():
            if not page.is_published:
                continue
            content = build_page_content(page.content_key)
            items = content['next_path']['items']
            self.assertEqual(len(items), 3, page.content_key)
            if page.content_key == 'build_property_database':
                # Sprint 8: conversion stays in Final CTA; next_path is product→product→solution.
                self.assertFalse(any(i.get('convert') for i in items), page.content_key)
            else:
                self.assertTrue(items[-1].get('convert'), page.content_key)

    def test_context_bar_and_journey_on_follow_up(self):
        resp = self.client.get('/solutions/customer-follow-up/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'plat-nav-bar')
        self.assertContains(resp, 'راه‌حل پیگیری مشتری')
        self.assertContains(resp, 'plat-nav-bar__journey')
        self.assertContains(resp, 'بازگشت به راه‌حل‌ها')
        self.assertContains(resp, 'لندینگ معرفی CRM')
        self.assertContains(resp, '/real-estate-crm/')

    def test_breadcrumb_present_and_short(self):
        resp = self.client.get('/features/crm/reminders/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'mk-platform-bc')
        self.assertContains(resp, 'mk-platform-bc__link')
        body = resp.content.decode('utf-8')
        # Current crumb should not be a long colon-title dump
        self.assertIn('aria-current="page"', body)

    def test_active_menu_state_on_crm_page(self):
        resp = self.client.get('/features/crm/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'mk-nav-link--mega is-active')
        self.assertContains(resp, 'mk-mega-card--rose is-active')
        self.assertContains(resp, 'جزئیات محصول CRM')
        self.assertContains(resp, 'لندینگ معرفی CRM')

    def test_guest_vs_authenticated_cta(self):
        from django.urls import reverse

        guest = self.client.get('/features/crm/')
        guest_body = guest.content.decode('utf-8')
        self.assertIn('شروع رایگان میزکار', guest_body)
        self.assertIn(reverse('register'), guest_body)
        # Primary convert lane for guests is register (cta_pair + sticky)
        self.assertRegex(
            guest_body,
            r'plat-cta-pair[\s\S]{0,400}' + re.escape(reverse('register')),
        )
        self.assertNotRegex(
            guest_body,
            r'plat-cta-pair[\s\S]{0,400}' + re.escape(reverse('workspace:home')),
        )

        from accounts.models import User
        user = User.objects.create_user(
            username='platnav', phone='09120001122', password='x',
        )
        self.client.force_login(user)
        auth = self.client.get('/features/crm/')
        auth_body = auth.content.decode('utf-8')
        self.assertIn('ورود به میزکار', auth_body)
        self.assertRegex(
            auth_body,
            r'plat-cta-pair[\s\S]{0,400}' + re.escape(reverse('workspace:home')),
        )
        self.assertNotIn('شروع رایگان میزکار', auth_body)

    def test_scenario_google_follow_up_to_convert(self):
        """Google → follow-up → CRM → reminders → register path."""
        follow = self.client.get('/solutions/customer-follow-up/')
        self.assertEqual(follow.status_code, 200)
        self.assertContains(follow, '/features/crm/')
        self.assertContains(follow, '/features/crm/reminders/')
        self.assertContains(follow, '/register/')
        self.assertContains(follow, 'plat-nav-bar__loc')

        crm = self.client.get('/features/crm/')
        self.assertContains(crm, '/features/crm/reminders/')
        self.assertContains(crm, '/solutions/customer-follow-up/')

        rem = self.client.get('/features/crm/reminders/')
        self.assertContains(rem, '/solutions/customer-follow-up/')
        self.assertContains(rem, '/register/')
        self.assertContains(rem, 'بازگشت به CRM')

    def test_scenario_features_hub_to_feature_back(self):
        hub = self.client.get('/features/')
        self.assertContains(hub, '/features/crm/')
        crm = self.client.get('/features/crm/')
        self.assertContains(crm, 'بازگشت به امکانات')
        rem = self.client.get('/features/crm/reminders/')
        self.assertContains(rem, 'بازگشت به CRM')
        self.assertContains(rem, 'همه امکانات')

    def test_scenario_solutions_hub_to_tool_to_convert(self):
        hub = self.client.get('/solutions/')
        self.assertContains(hub, '/solutions/customer-follow-up/')
        self.assertContains(hub, '/solutions/property-pricing/')
        self.assertContains(hub, '/solutions/agency-management/')
        body = hub.content.decode('utf-8')
        self.assertIn('shub-map__row--published', body)
        self.assertNotIn('href=""', body)

        sol = self.client.get('/solutions/customer-follow-up/')
        self.assertContains(sol, '/features/crm/reminders/')
        self.assertContains(sol, '/register/')

    def test_no_redirect_chains_on_platform_urls(self):
        for url in PLATFORM_URLS:
            with self.subTest(url=url):
                resp = self.client.get(url, follow=False)
                self.assertEqual(resp.status_code, 200, url)

    def test_crm_vs_landing_labels_distinct(self):
        resp = self.client.get('/features/crm/')
        self.assertContains(resp, 'لندینگ معرفی CRM')
        self.assertContains(resp, '/features/crm/')
        self.assertContains(resp, '/real-estate-crm/')
        self.assertContains(resp, 'جزئیات محصول')


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class PlatformFeelingPhaseETests(TestCase):
    """Phase E: shared chrome, product frame, CTA tiers, affiliation."""

    def test_product_frame_and_affiliation_on_all_pages(self):
        for url in PLATFORM_URLS:
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, 'plat-page--feel')
                self.assertContains(resp, 'plat-product-frame')
                self.assertContains(resp, 'میزکار فایلینگ دیوار')
                self.assertContains(resp, 'بخشی از میزکار فایلینگ دیوار')
                self.assertContains(resp, 'plat-affiliate')
                self.assertContains(resp, 'mizkar-platform-feel.css')

    def test_cta_tiers_present(self):
        resp = self.client.get('/features/crm/')
        self.assertContains(resp, 'plat-btn--convert')
        self.assertContains(resp, 'plat-btn--product')
        self.assertContains(resp, 'plat-btn--explore')

    def test_personalities_still_distinct(self):
        mapping = {
            '/features/': 'fhub-hero',
            '/features/crm/': 'plat-crm-hero',
            '/features/crm/reminders/': 'rem-hero',
            '/features/filing/': 'fil-hero',
            '/solutions/': 'shub-hero',
            '/solutions/customer-follow-up/': 'sol-hero',
            '/solutions/fast-property-search/': 'sol-hero',
        }
        for url, marker in mapping.items():
            with self.subTest(url=url):
                resp = self.client.get(url)
                self.assertContains(resp, marker)

    def test_feel_css_budget(self):
        """Shared feel CSS must stay lean (no redesign dump)."""
        from pathlib import Path
        feel = Path(__file__).resolve().parents[2] / 'static' / 'css' / 'mizkar-platform-feel.css'
        size = feel.stat().st_size
        self.assertLess(size, 18_000, f'feel.css too large: {size} bytes')
        text = feel.read_text(encoding='utf-8')
        self.assertIn('--plat-radius', text)
        self.assertIn('--plat-shadow-frame', text)
        self.assertIn('plat-btn--convert', text)
        # No extreme glow language
        self.assertNotIn('text-shadow', text)
        self.assertLess(text.count('box-shadow'), 12)


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class PlatformFilingPhase2Tests(TestCase):
    """Phase 2 sprint 1: /features/filing/ product line."""

    def test_filing_page_renders(self):
        resp = self.client.get('/features/filing/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'fil-hero')
        self.assertContains(resp, 'fil-outcomes')
        self.assertContains(resp, 'fil-next')
        self.assertContains(resp, 'fil-ico')
        self.assertContains(resp, 'help-dataset-table')
        self.assertContains(resp, 'help-upload-bulk')
        self.assertContains(resp, 'help-map-view')
        self.assertContains(resp, '/features/crm/')
        self.assertContains(resp, 'plat-faq__item', count=7)
        self.assertContains(resp, 'لایسنس')
        self.assertContains(resp, 'بخشی از میزکار فایلینگ دیوار')
        self.assertContains(resp, '<h1', count=1)

    def test_filing_schema_licensed_not_fake_free(self):
        resp = self.client.get('/features/filing/')
        body = resp.content.decode('utf-8')
        self.assertIn('"@type": "SoftwareApplication"', body)
        self.assertIn('"@type": "Product"', body)
        self.assertIn('فایلینگ دیوار', body)
        self.assertIn('لایسنس ربات', body)
        self.assertNotIn('AggregateRating', body)
        # Must not claim price 0 like CRM free core
        self.assertNotRegex(body, r'"@type": "Product"[\s\S]{0,800}"price": "0"')

    def test_filing_next_path_exactly_three(self):
        from shop.platform.content.filing_hub import filing_product_line_content
        items = filing_product_line_content()['next_path']['items']
        self.assertEqual(len(items), 3)
        self.assertTrue(items[-1].get('convert'))

    def test_features_hub_links_to_filing(self):
        resp = self.client.get('/features/')
        self.assertContains(resp, '/features/filing/')

    def test_filing_seo_health(self):
        _assert_platform_seo_health(self, '/features/filing/')


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class PlatformFastSearchPhase2Tests(TestCase):
    """Phase 2 sprint 2: /solutions/fast-property-search/ vertical slice."""

    def test_fast_search_page_renders(self):
        resp = self.client.get('/solutions/fast-property-search/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'sol-hero')
        self.assertContains(resp, 'sol-outcomes')
        self.assertContains(resp, 'sol-framework')
        self.assertContains(resp, 'sol-next')
        self.assertContains(resp, 'help-dataset-table')
        self.assertContains(resp, 'help-upload-bulk')
        self.assertContains(resp, 'help-map-view')
        self.assertContains(resp, '/features/filing/')
        self.assertContains(resp, 'plat-btn--convert')
        self.assertContains(resp, 'plat-btn--product')
        self.assertContains(resp, 'plat-faq__item', count=8)
        self.assertContains(resp, 'دفتر')
        self.assertContains(resp, 'یادداشت')
        self.assertContains(resp, 'اکسل')
        self.assertContains(resp, 'واتساپ')
        self.assertContains(resp, '<h1', count=1)

    def test_fast_search_draft_features_not_public(self):
        for path in ('filing/search', 'filing/filter', 'filing/saved-search'):
            with self.subTest(path=path):
                self.assertIsNone(get_page('features', path))
                resp = self.client.get(f'/features/{path}/')
                self.assertEqual(resp.status_code, 404)

    def test_fast_search_schema_licensed(self):
        resp = self.client.get('/solutions/fast-property-search/')
        body = resp.content.decode('utf-8')
        self.assertIn('"@type": "SoftwareApplication"', body)
        self.assertIn('"@type": "Product"', body)
        self.assertIn('"@type": "FAQPage"', body)
        self.assertIn('پیدا کردن سریع', body)
        self.assertNotIn('AggregateRating', body)
        self.assertNotRegex(body, r'"@type": "Product"[\s\S]{0,800}"price": "0"')

    def test_fast_search_next_path_three(self):
        from shop.platform.content.fast_property_search import fast_property_search_content
        items = fast_property_search_content()['next_path']['items']
        self.assertEqual(len(items), 3)
        self.assertTrue(items[-1].get('convert'))

    def test_vertical_slice_links(self):
        sol = self.client.get('/solutions/fast-property-search/')
        self.assertContains(sol, '/features/filing/')
        self.assertContains(sol, '/products/')
        filing = self.client.get('/features/filing/')
        self.assertContains(filing, '/solutions/fast-property-search/')
        hub = self.client.get('/solutions/')
        self.assertContains(hub, '/solutions/fast-property-search/')
        self.assertContains(hub, 'shub-map__row--published')

    def test_fast_search_seo_health(self):
        _assert_platform_seo_health(self, '/solutions/fast-property-search/')


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class PlatformMarketIntelligencePhase2Tests(TestCase):
    """Phase 2 sprint 3: /features/market-intelligence/ product line."""

    def test_market_page_renders(self):
        resp = self.client.get('/features/market-intelligence/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'mi-hero')
        self.assertContains(resp, 'mi-outcomes')
        self.assertContains(resp, 'mi-next')
        self.assertContains(resp, 'fil-ico')
        self.assertContains(resp, 'help-analyze-dashboard')
        self.assertContains(resp, 'help-map-view')
        self.assertContains(resp, 'help-compare-files')
        self.assertContains(resp, 'help-tools-panel')
        self.assertContains(resp, '/features/filing/')
        self.assertContains(resp, 'plat-faq__item', count=7)
        self.assertContains(resp, 'Value Score')
        self.assertContains(resp, 'لایسنس')
        self.assertContains(resp, '<h1', count=1)

    def test_market_schema_licensed_not_fake_free(self):
        resp = self.client.get('/features/market-intelligence/')
        body = resp.content.decode('utf-8')
        self.assertIn('"@type": "SoftwareApplication"', body)
        self.assertIn('"@type": "Product"', body)
        self.assertIn('تحلیل بازار', body)
        self.assertIn('لایسنس', body)
        self.assertNotIn('AggregateRating', body)
        self.assertNotRegex(body, r'"@type": "Product"[\s\S]{0,800}"price": "0"')

    def test_market_next_path_exactly_three(self):
        from shop.platform.content.market_intelligence_hub import (
            market_intelligence_product_line_content,
        )
        items = market_intelligence_product_line_content()['next_path']['items']
        self.assertEqual(len(items), 3)
        self.assertTrue(items[-1].get('convert'))

    def test_features_hub_links_to_market(self):
        resp = self.client.get('/features/')
        self.assertContains(resp, '/features/market-intelligence/')

    def test_market_seo_health(self):
        _assert_platform_seo_health(self, '/features/market-intelligence/')


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class PlatformPropertyPricingPhase2Tests(TestCase):
    """Phase 2 sprint 4: /solutions/property-pricing/ vertical slice."""

    def test_pricing_page_renders(self):
        resp = self.client.get('/solutions/property-pricing/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'sol-hero')
        self.assertContains(resp, 'sol-outcomes')
        self.assertContains(resp, 'sol-framework')
        self.assertContains(resp, 'sol-next')
        self.assertContains(resp, 'pp-conseq')
        self.assertContains(resp, 'pp-limits')
        self.assertContains(resp, 'help-analyze-dashboard')
        self.assertContains(resp, 'help-dataset-table')
        self.assertContains(resp, 'help-map-view')
        self.assertContains(resp, 'help-tools-panel')
        self.assertContains(resp, '/features/market-intelligence/')
        self.assertContains(resp, '/features/filing/')
        self.assertContains(resp, 'plat-btn--convert')
        self.assertContains(resp, 'plat-btn--product')
        self.assertContains(resp, 'plat-faq__item', count=10)
        self.assertContains(resp, 'میانه')
        self.assertContains(resp, 'Value Score')
        self.assertContains(resp, 'قیمت قطعی')
        self.assertContains(resp, '<h1', count=1)

    def test_pricing_honesty_no_guaranteed_price_claim(self):
        resp = self.client.get('/solutions/property-pricing/')
        body = resp.content.decode('utf-8')
        self.assertIn('قیمت قطعی', body)
        self.assertIn('جای کارشناس', body)
        self.assertNotIn('قیمت دقیق ملک را به شما می‌دهیم', body)

    def test_pricing_draft_features_not_public(self):
        drafts = (
            'market-intelligence/price-analysis',
            'market-intelligence/value-score',
            'market-intelligence/map-analysis',
            'market-intelligence/comparison',
            'market-intelligence/pricing-tools',
        )
        for path in drafts:
            with self.subTest(path=path):
                self.assertIsNone(get_page('features', path))
                resp = self.client.get(f'/features/{path}/')
                self.assertEqual(resp.status_code, 404)

    def test_pricing_schema_licensed(self):
        resp = self.client.get('/solutions/property-pricing/')
        body = resp.content.decode('utf-8')
        self.assertIn('"@type": "SoftwareApplication"', body)
        self.assertIn('"@type": "Product"', body)
        self.assertIn('"@type": "FAQPage"', body)
        self.assertIn('قیمت', body)
        self.assertIn('market-intelligence', body)
        self.assertNotIn('AggregateRating', body)
        self.assertNotRegex(body, r'"@type": "Product"[\s\S]{0,800}"price": "0"')

    def test_pricing_next_path_three(self):
        from shop.platform.content.property_pricing import property_pricing_content
        items = property_pricing_content()['next_path']['items']
        self.assertEqual(len(items), 3)
        self.assertTrue(items[-1].get('convert'))
        self.assertEqual(items[0]['url_kwargs']['slug_path'], 'market-intelligence')

    def test_pricing_hub_and_menu_links(self):
        hub = self.client.get('/solutions/')
        self.assertContains(hub, '/solutions/property-pricing/')
        self.assertContains(hub, 'shub-map__row--published')
        mi = self.client.get('/features/market-intelligence/')
        self.assertContains(mi, '/solutions/property-pricing/')

    def test_pricing_seo_health(self):
        _assert_platform_seo_health(self, '/solutions/property-pricing/')


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class PlatformAgencyPhase2Tests(TestCase):
    """Phase 2 sprint 5: /features/agency/ product line."""

    def test_agency_page_renders(self):
        resp = self.client.get('/features/agency/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ag-hero')
        self.assertContains(resp, 'ag-outcomes')
        self.assertContains(resp, 'ag-roles-title')
        self.assertContains(resp, 'ag-privacy')
        self.assertContains(resp, 'ag-next')
        self.assertContains(resp, 'Agency TV')
        self.assertContains(resp, 'help-crm-team')
        self.assertContains(resp, 'help-crm-today')
        self.assertContains(resp, 'help-crm-dashboard')
        self.assertContains(resp, '/features/crm/')
        self.assertContains(resp, 'plat-faq__item', count=12)
        self.assertContains(resp, 'رایگان')
        self.assertContains(resp, 'مالک')
        self.assertContains(resp, 'منشی')
        self.assertContains(resp, '<h1', count=1)

    def test_agency_schema_free_not_rating(self):
        resp = self.client.get('/features/agency/')
        body = resp.content.decode('utf-8')
        self.assertIn('"@type": "SoftwareApplication"', body)
        self.assertIn('"@type": "Product"', body)
        self.assertIn('مدیریت آژانس', body)
        self.assertIn('"price": "0"', body)
        self.assertNotIn('AggregateRating', body)

    def test_agency_next_path_three(self):
        from shop.platform.content.agency_hub import agency_product_line_content
        items = agency_product_line_content()['next_path']['items']
        self.assertEqual(len(items), 3)
        self.assertTrue(items[-1].get('convert'))
        self.assertEqual(items[0]['url_kwargs']['slug_path'], 'crm')

    def test_agency_draft_features_not_public(self):
        drafts = (
            'agency/team-management',
            'agency/roles-permissions',
            'agency/team-inbox',
            'agency/activity-feed',
            'agency/reports',
            'agency/tv-dashboard',
            'agency/announcements',
        )
        for path in drafts:
            with self.subTest(path=path):
                self.assertIsNone(get_page('features', path))
                resp = self.client.get(f'/features/{path}/')
                self.assertEqual(resp.status_code, 404)

    def test_agency_management_solution_published(self):
        page = get_page('solutions', 'agency-management')
        self.assertIsNotNone(page)
        self.assertEqual(page.status, 'published')
        resp = self.client.get('/solutions/agency-management/')
        self.assertEqual(resp.status_code, 200)

    def test_agency_hero_h1_not_duplicated(self):
        resp = self.client.get('/features/agency/')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertEqual(body.count('<h1'), 1)
        h1 = 'مدیریت تیم آژانس؛ بدون گزارش‌های پراکنده و پیگیری‌های گمشده'
        hero_start = body.find('ag-hero')
        hero_end = body.find('</header>', hero_start)
        self.assertGreater(hero_start, -1)
        self.assertGreater(hero_end, hero_start)
        hero_html = body[hero_start:hero_end]
        self.assertEqual(hero_html.count('<h1'), 1)
        self.assertEqual(hero_html.count(h1), 1)
        self.assertIn('نقش‌ها، صندوق سرنخ و گزارش تیم', hero_html)
        self.assertNotIn(h1, hero_html.replace(h1, '', 1))

    def test_features_hub_and_crm_link_agency(self):
        hub = self.client.get('/features/')
        self.assertContains(hub, '/features/agency/')
        crm = self.client.get('/features/crm/')
        self.assertContains(crm, '/features/agency/')
        self.assertContains(crm, '/solutions/agency-management/')

    def test_agency_links_solution(self):
        resp = self.client.get('/features/agency/')
        self.assertContains(resp, '/solutions/agency-management/')

    def test_agency_honesty_limits(self):
        resp = self.client.get('/features/agency/')
        body = resp.content.decode('utf-8')
        self.assertIn('جایگزین کامل', body)
        self.assertIn('چندشعبه', body)
        self.assertIn('وب‌سوکت', body)
        self.assertIn('تضمین ایمنی بی‌نقص ادعا نمی‌شود', body)
        self.assertNotIn('امنیت مطلق', body)

    def test_agency_seo_health(self):
        _assert_platform_seo_health(self, '/features/agency/')


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class PlatformAgencyManagementPhase2Tests(TestCase):
    """Phase 2 sprint 6: /solutions/agency-management/."""

    def test_agency_management_page_renders(self):
        resp = self.client.get('/solutions/agency-management/')
        self.assertEqual(resp.status_code, 200)
        page = get_page('solutions', 'agency-management')
        self.assertEqual(page.status, 'published')
        self.assertContains(resp, 'sol-hero')
        self.assertContains(resp, 'am-conseq')
        self.assertContains(resp, 'am-check-title')
        self.assertContains(resp, 'sol-framework-title')
        self.assertContains(resp, 'am-conn-title')
        self.assertContains(resp, 'am-mgr-title')
        self.assertContains(resp, 'am-limits-title')
        self.assertContains(resp, 'am-tv-title')
        self.assertContains(resp, 'help-crm-team')
        self.assertContains(resp, 'help-crm-today')
        self.assertContains(resp, 'help-crm-contacts')
        self.assertContains(resp, 'help-crm-dashboard')
        self.assertContains(resp, '/features/agency/')
        self.assertContains(resp, '/features/crm/')
        self.assertContains(resp, '/solutions/customer-follow-up/')
        self.assertContains(resp, 'plat-nav-bar')
        self.assertContains(resp, 'plat-affiliate')
        self.assertContains(resp, 'plat-faq__item', count=14)
        self.assertContains(resp, 'رایگان')
        self.assertContains(resp, 'چند شعبه')
        self.assertContains(resp, 'polling')
        self.assertContains(resp, '<h1', count=1)
        h1 = 'مدیریت آژانس املاک؛ بدانید کار دست چه کسی است'
        body = resp.content.decode('utf-8')
        hero_start = body.find('sol-hero')
        hero_end = body.find('</header>', hero_start)
        self.assertGreater(hero_start, -1)
        self.assertGreater(hero_end, hero_start)
        hero_html = body[hero_start:hero_end]
        self.assertEqual(hero_html.count(h1), 1)
        self.assertEqual(hero_html.count('<h1'), 1)
        self.assertContains(resp, 'نرم‌افزار مدیر آژانس نیست')

    def test_agency_management_schema_free(self):
        resp = self.client.get('/solutions/agency-management/')
        body = resp.content.decode('utf-8')
        self.assertIn('"@type": "SoftwareApplication"', body)
        self.assertIn('"@type": "Product"', body)
        self.assertIn('"@type": "FAQPage"', body)
        self.assertIn('"@type": "WebPage"', body)
        self.assertIn('مدیریت آژانس', body)
        self.assertIn('/features/agency/', body)
        self.assertIn('/features/crm/', body)
        self.assertIn('"price": "0"', body)
        self.assertNotIn('AggregateRating', body)

    def test_agency_management_next_path_three(self):
        from shop.platform.content.agency_management import agency_management_content
        items = agency_management_content()['next_path']['items']
        self.assertEqual(len(items), 3)
        self.assertTrue(items[-1].get('convert'))
        self.assertEqual(items[0]['url_kwargs']['slug_path'], 'agency')
        self.assertEqual(items[1]['url_kwargs']['slug'], 'customer-follow-up')
        self.assertEqual(items[2].get('auth_url_name'), 'workspace:crm_team')

    def test_agency_management_hub_and_menu(self):
        hub = self.client.get('/solutions/')
        self.assertContains(hub, '/solutions/agency-management/')
        self.assertContains(hub, 'shub-map__row--published')
        self.assertContains(hub, 'مدیریت آژانس')
        agency = self.client.get('/features/agency/')
        self.assertContains(agency, '/solutions/agency-management/')

    def test_agency_management_guest_and_auth_cta(self):
        guest = self.client.get('/solutions/agency-management/')
        self.assertContains(guest, 'ساخت میزکار رایگان')
        self.assertContains(guest, 'ثبت‌نام و ایجاد تیم')
        from accounts.models import User
        user = User.objects.create_user(
            username='am_mgr', phone='09120009988', password='x',
        )
        self.client.force_login(user)
        auth = self.client.get('/solutions/agency-management/')
        self.assertContains(auth, 'ورود به صفحه تیم')
        self.assertContains(auth, '/workspace/crm/team/')
    def test_agency_management_draft_features_still_404(self):
        drafts = (
            'agency/team-management',
            'agency/roles-permissions',
            'agency/team-inbox',
            'agency/activity-feed',
            'agency/reports',
            'agency/tv-dashboard',
            'agency/announcements',
        )
        for path in drafts:
            with self.subTest(path=path):
                self.assertIsNone(get_page('features', path))
                resp = self.client.get(f'/features/{path}/')
                self.assertEqual(resp.status_code, 404)

    def test_agency_management_unknown_slug_404(self):
        resp = self.client.get('/solutions/agency-management-xyz/')
        self.assertEqual(resp.status_code, 404)

    def test_agency_management_seo_health(self):
        _assert_platform_seo_health(self, '/solutions/agency-management/')

    def test_agency_management_forbidden_claims(self):
        resp = self.client.get('/solutions/agency-management/')
        body = resp.content.decode('utf-8')
        self.assertNotIn('کنترل کامل همه اعضا', body)
        self.assertNotIn('نظارت صددرصدی', body)
        self.assertNotIn('افزایش تضمینی فروش', body)
        self.assertNotIn('امنیت مطلق', body)
        self.assertNotIn('Real-time', body)
        self.assertNotIn('real-time', body)
        self.assertIn('جایگزین کامل واتساپ یا تماس', body)
        self.assertIn('چند شعبه مستقل', body)
        self.assertIn('polling', body)

@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class PlatformExtractionPhase2Tests(TestCase):
    """Phase 2 sprint 7: /features/extraction/ product line."""

    def test_extraction_page_renders(self):
        resp = self.client.get('/features/extraction/')
        self.assertEqual(resp.status_code, 200)
        page = get_page('features', 'extraction')
        self.assertIsNotNone(page)
        self.assertEqual(page.status, 'published')
        self.assertContains(resp, 'ex-hero')
        self.assertContains(resp, 'ex-outcomes')
        self.assertContains(resp, 'ex-flow-title')
        self.assertContains(resp, 'ex-filters-title')
        self.assertContains(resp, 'ex-dedup-title')
        self.assertContains(resp, 'ex-out-title')
        self.assertContains(resp, 'ex-license-title')
        self.assertContains(resp, 'ex-limits-title')
        self.assertContains(resp, 'help-bot-extract-tab')
        self.assertContains(resp, 'help-bot-license')
        self.assertContains(resp, 'help-bot-output-folder')
        self.assertContains(resp, 'help-upload-bulk')
        self.assertContains(resp, '/features/filing/')
        self.assertContains(resp, '/features/market-intelligence/')
        self.assertContains(resp, 'plat-nav-bar')
        self.assertContains(resp, 'plat-affiliate')
        self.assertContains(resp, 'plat-faq__item', count=17)
        self.assertContains(resp, 'ویندوز')
        self.assertContains(resp, 'لایسنس')
        self.assertContains(resp, 'یک‌روزه')
        self.assertContains(resp, 'Excel')
        self.assertContains(resp, 'CSV')
        self.assertContains(resp, 'JSON')
        self.assertContains(resp, 'شناسه')
        self.assertContains(resp, 'ex-advisor-title')
        self.assertContains(resp, 'فقط شخصی')
        self.assertContains(resp, 'پارکینگ')
        self.assertContains(resp, '<h1', count=1)

    def test_extraction_schema_licensed_windows(self):
        resp = self.client.get('/features/extraction/')
        body = resp.content.decode('utf-8')
        self.assertIn('"@type": "SoftwareApplication"', body)
        self.assertIn('"@type": "Product"', body)
        self.assertIn('"@type": "FAQPage"', body)
        self.assertIn('"operatingSystem": "Windows"', body)
        self.assertIn('filing', body)
        self.assertIn('market-intelligence', body)
        self.assertNotIn('AggregateRating', body)
        self.assertNotRegex(body, r'"@type": "Product"[\s\S]{0,800}"price": "0"')

    def test_extraction_next_path_three(self):
        from shop.platform.content.extraction_hub import extraction_product_line_content
        items = extraction_product_line_content()['next_path']['items']
        self.assertEqual(len(items), 3)
        self.assertTrue(items[-1].get('convert'))
        self.assertEqual(items[0]['url_kwargs']['slug'], 'build-property-database')
        self.assertEqual(items[1]['url_kwargs']['slug_path'], 'filing')

    def test_extraction_guest_and_auth_cta(self):
        guest = self.client.get('/features/extraction/')
        self.assertContains(guest, 'مشاهده لایسنس ربات')
        self.assertContains(guest, '/products/divar-extraction-bot/')
        from accounts.models import User
        user = User.objects.create_user(
            username='ex_user', phone='09120007766', password='x',
        )
        self.client.force_login(user)
        auth = self.client.get('/features/extraction/')
        self.assertContains(auth, 'مدیریت حساب و لایسنس')
        self.assertContains(auth, '/dashboard/')

    def test_extraction_hub_and_menu_links(self):
        hub = self.client.get('/features/')
        self.assertContains(hub, '/features/extraction/')
        filing = self.client.get('/features/filing/')
        self.assertContains(filing, '/features/extraction/')

    def test_extraction_draft_features_404(self):
        drafts = (
            'extraction/location-filter',
            'extraction/category-filter',
            'extraction/deduplication',
            'extraction/export',
            'extraction/license-management',
            'extraction/dataset-builder',
            'extraction/advertiser-signals',
        )
        for path in drafts:
            with self.subTest(path=path):
                self.assertIsNone(get_page('features', path))
                resp = self.client.get(f'/features/{path}/')
                self.assertEqual(resp.status_code, 404)

    def test_extraction_unknown_slug_404(self):
        resp = self.client.get('/features/extraction-unknown/')
        self.assertEqual(resp.status_code, 404)

    def test_extraction_seo_health(self):
        _assert_platform_seo_health(self, '/features/extraction/')

    def test_extraction_forbidden_claims(self):
        resp = self.client.get('/features/extraction/')
        body = resp.content.decode('utf-8')
        self.assertNotIn('استخراج نامحدود', body)
        self.assertNotIn('بدون نیاز به لایسنس', body)
        self.assertNotIn('مالک واقعی قطعی', body)
        self.assertNotIn('تضمین استخراج همه', body)
        self.assertIn('محصول رسمی دیوار', body)
        self.assertIn('Worker', body)

    def test_extraction_resume_not_marketed_as_feature(self):
        resp = self.client.get('/features/extraction/')
        body = resp.content.decode('utf-8')
        self.assertNotIn('قابلیت Resume', body)
        self.assertNotIn('ادامه خودکار کامل', body)
        self.assertIn('ادامه خودکار پس از توقف', body)


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class PlatformBuildPropertyDatabasePhase2Tests(TestCase):
    """Phase 2 sprint 8: /solutions/build-property-database/."""

    def test_build_property_database_renders(self):
        resp = self.client.get('/solutions/build-property-database/')
        self.assertEqual(resp.status_code, 200)
        page = get_page('solutions', 'build-property-database')
        self.assertIsNotNone(page)
        self.assertEqual(page.status, 'published')
        self.assertEqual(page.accent, 'orange')
        self.assertContains(resp, 'sol-hero')
        self.assertContains(resp, 'bpd-conseq')
        self.assertContains(resp, 'bpd-checklist')
        self.assertContains(resp, 'sol-framework')
        self.assertContains(resp, 'bpd-conn')
        self.assertContains(resp, 'bpd-maint')
        self.assertContains(resp, 'help-bot-extract-tab')
        self.assertContains(resp, 'help-bot-output-folder')
        self.assertContains(resp, 'help-upload-bulk')
        self.assertContains(resp, 'help-dataset-table')
        self.assertContains(resp, 'help-map-view')
        self.assertContains(resp, '/features/extraction/')
        self.assertContains(resp, '/features/filing/')
        self.assertContains(resp, '/solutions/fast-property-search/')
        self.assertContains(resp, 'plat-nav-bar')
        self.assertContains(resp, 'plat-affiliate')
        self.assertContains(resp, 'plat-faq__item', count=16)
        self.assertContains(resp, 'شناسه')
        self.assertContains(resp, '۵۰۰')
        self.assertContains(resp, 'لایسنس')
        self.assertContains(resp, '<h1', count=1)

    def test_build_property_database_schema_licensed(self):
        resp = self.client.get('/solutions/build-property-database/')
        body = resp.content.decode('utf-8')
        self.assertIn('"@type": "SoftwareApplication"', body)
        self.assertIn('"@type": "Product"', body)
        self.assertIn('"@type": "FAQPage"', body)
        self.assertIn('extraction', body)
        self.assertIn('filing', body)
        self.assertIn('fast-property-search', body)
        self.assertNotIn('AggregateRating', body)
        self.assertNotRegex(body, r'"@type": "Product"[\s\S]{0,800}"price": "0"')

    def test_build_property_database_next_path_three(self):
        from shop.platform.content.build_property_database import (
            build_property_database_content,
        )
        items = build_property_database_content()['next_path']['items']
        self.assertEqual(len(items), 3)
        self.assertFalse(any(i.get('convert') for i in items))
        self.assertEqual(items[0]['url_kwargs']['slug_path'], 'extraction')
        self.assertEqual(items[1]['url_kwargs']['slug_path'], 'filing')
        self.assertEqual(items[2]['url_kwargs']['slug'], 'fast-property-search')

    def test_build_property_database_guest_and_auth_cta(self):
        guest = self.client.get('/solutions/build-property-database/')
        self.assertContains(guest, 'مشاهده لایسنس ربات')
        self.assertContains(guest, '/products/divar-extraction-bot/')
        self.assertContains(guest, 'خط محصول استخراج')
        from accounts.models import User
        user = User.objects.create_user(
            username='bpd_user', phone='09120008877', password='x',
        )
        self.client.force_login(user)
        auth = self.client.get('/solutions/build-property-database/')
        self.assertContains(auth, 'مدیریت حساب و لایسنس')
        self.assertContains(auth, '/dashboard/')

    def test_build_property_database_hub_menu_and_backlinks(self):
        from shop.platform.registry.menu import platform_mega_menu
        hub = self.client.get('/solutions/')
        self.assertContains(hub, '/solutions/build-property-database/')
        self.assertContains(hub, 'shub-map__row--published')
        labels = [s['url_kwargs']['slug'] for s in platform_mega_menu()['solution_highlights']]
        self.assertIn('build-property-database', labels)
        extraction = self.client.get('/features/extraction/')
        self.assertContains(extraction, '/solutions/build-property-database/')
        filing = self.client.get('/features/filing/')
        self.assertContains(filing, '/solutions/build-property-database/')
        fast = self.client.get('/solutions/fast-property-search/')
        self.assertContains(fast, '/solutions/build-property-database/')

    def test_build_property_database_honesty(self):
        resp = self.client.get('/solutions/build-property-database/')
        body = resp.content.decode('utf-8')
        forbidden = (
            'کامل‌ترین بانک فایل ایران',
            'همه فایل‌های منطقه',
            'بانک فایل بدون تکراری',
            'فایل‌های صددرصد معتبر',
            'مالک واقعی تضمینی',
            'اطلاعات همیشه به‌روز',
            'استخراج نامحدود',
            'افزایش تضمینی معامله',
            'جایگزینی کامل فایل‌یاب',
            'خودکارسازی کامل بدون بررسی انسان',
            'تأیید یا همکاری رسمی دیوار',
            'AggregateRating',
        )
        for phrase in forbidden:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, body)
        self.assertIn('بررسی انسانی', body)
        self.assertIn('شناسه', body)

    def test_build_property_database_unknown_slug_404(self):
        resp = self.client.get('/solutions/build-property-database-xyz/')
        self.assertEqual(resp.status_code, 404)

    def test_build_property_database_seo_health(self):
        _assert_platform_seo_health(self, '/solutions/build-property-database/')


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class PlatformExtractionHonestyDocsTests(TestCase):
    """Sprint 8 pre-fix: INFO_BEFORE / Resume honesty."""

    def test_info_before_has_no_overclaims(self):
        from pathlib import Path
        repo = Path(__file__).resolve().parents[3]
        paths = [
            repo / 'installer' / 'INFO_BEFORE.txt',
            repo / 'extractor-app' / 'release' / 'docs' / 'INFO_BEFORE.txt',
        ]
        banned_legacy = (
            'Interactive map display',
            'Commission calculator',
            'Comprehensive data analysis tools',
            'No information is sent to external servers',
            'Automatic extraction of real estate listing data',
            'Parallel processing for higher speed',
            'Beautiful and intuitive graphical user interface',
        )
        for path in paths:
            with self.subTest(path=str(path)):
                self.assertTrue(path.exists(), msg=f'missing {path}')
                text = path.read_text(encoding='utf-8')
                for phrase in banned_legacy:
                    self.assertNotIn(phrase, text)
                self.assertIn('چه چیزی تضمین یا ادعا نمی‌شود', text)
                self.assertIn('۵۰۰', text)
                self.assertIn('Resume', text)
                self.assertIn('وعده داده نمی‌شود', text)
                self.assertIn('لایسنس', text)
                features = text.split('چه چیزی تضمین یا ادعا نمی‌شود')[0]
                self.assertNotIn('استخراج نامحدود', features)
                self.assertNotIn('ادامه خودکار کامل', features)
