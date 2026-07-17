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
    '/solutions/',
    '/solutions/customer-follow-up/',
    '/solutions/fast-property-search/',
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
        self.assertContains(hub, 'shub-map__soon')
        self.assertContains(hub, 'به‌زودی')
        # coming rows are spans, not links to empty urls
        body = hub.content.decode('utf-8')
        self.assertIn('shub-map__row--coming', body)
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
