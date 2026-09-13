"""Tests for SEO landing pages (Wave 1)."""
from django.test import TestCase, override_settings

from shop.seo_landings import LANDING_SLUGS, get_landing


@override_settings(SITE_URL='https://divarfiling.ir', ALLOWED_HOSTS=['testserver'])
class SeoLandingPageTests(TestCase):
    def test_wave1_slugs_registered(self):
        self.assertEqual(
            set(LANDING_SLUGS),
            {
                'real-estate-crm',
                'real-estate-software',
                'robot-divar',
                'real-estate-market-analysis',
            },
        )

    def test_all_landings_have_content(self):
        for slug in LANDING_SLUGS:
            landing = get_landing(slug)
            self.assertIsNotNone(landing)
            self.assertTrue(landing['hero']['h1'])
            self.assertTrue(landing['meta_title'])
            self.assertGreaterEqual(len(landing['faq']), 5)
            self.assertIn('visuals', landing)
            self.assertTrue(landing['visuals'].get('hero_image'))
        market = get_landing('real-estate-market-analysis')
        self.assertTrue(market['hero'].get('h1_short'))
        self.assertTrue(market['hero'].get('brand'))
        self.assertGreaterEqual(len(market.get('outcomes') or []), 3)

    def test_real_estate_crm_page(self):
        resp = self.client.get('/real-estate-crm/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'CRM مشاور املاک')
        self.assertContains(resp, 'سوالات متداول')
        self.assertContains(resp, 'شروع رایگان میزکار')
        self.assertContains(resp, 'help-crm-dashboard.png')
        self.assertContains(resp, 'seo-hero-shot')

    def test_real_estate_software_page(self):
        resp = self.client.get('/real-estate-software/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'نرم افزار مشاور املاک')
        self.assertContains(resp, 'help-workspace-home.png')

    def test_robot_divar_page(self):
        resp = self.client.get('/robot-divar/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ربات دیوار')
        self.assertContains(resp, 'divar-extraction-bot')
        self.assertContains(resp, 'help-bot-extract-tab.png')

    def test_real_estate_market_analysis_page(self):
        resp = self.client.get('/real-estate-market-analysis/')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'shop/seo_landing_market.html')
        self.assertContains(resp, 'seo-market')
        self.assertContains(resp, 'ma-sticky-cta')
        self.assertContains(resp, 'تحلیل بازار املاک با داده دیوار')
        self.assertContains(resp, 'سوالات متداول')
        self.assertContains(resp, 'شروع رایگان میزکار')
        self.assertContains(resp, 'ببینید چطور کار می‌کند')
        self.assertContains(resp, 'help-analyze-dashboard.png')
        self.assertContains(resp, 'ma-hero-shot')
        self.assertContains(resp, 'mizkar-seo-market-analysis.css')

    def test_wave1_landings_keep_shared_template(self):
        resp = self.client.get('/real-estate-crm/')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'shop/seo_landing.html')
        self.assertNotContains(resp, 'seo-market-page')

    def test_unknown_landing_404(self):
        resp = self.client.get('/divar-filing/')
        self.assertEqual(resp.status_code, 404)

    def test_home_links_to_crm_landing(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '/real-estate-crm/')
        self.assertContains(resp, 'CRM مشاور املاک')
        self.assertContains(resp, '/real-estate-software/')
        self.assertContains(resp, '/robot-divar/')

    def test_author_page(self):
        resp = self.client.get('/author/hossein-qashqaeii/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'حسین قشقایی')
        self.assertContains(resp, 'application/ld+json')
        self.assertContains(resp, '"@type": "Person"')
        self.assertContains(resp, 'ath-hero')
        self.assertContains(resp, 'ath-expertise')
        self.assertContains(resp, 'آمار زنده از پلتفرم')

    def test_footer_seo_guides(self):
        resp = self.client.get('/')
        self.assertContains(resp, 'راهنماهای تخصصی')
        self.assertContains(resp, 'نرم افزار مشاور املاک')
        self.assertContains(resp, 'تحلیل بازار املاک')

    def test_sitemap_includes_landings(self):
        resp = self.client.get('/sitemap-landings.xml')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('/real-estate-crm/', body)
        self.assertIn('/robot-divar/', body)
        self.assertIn('/real-estate-market-analysis/', body)
