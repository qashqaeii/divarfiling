"""تست Quality Gateهای انتشار خودکار مقالات سیستماتیک."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from blog.models import MarketArticleRun
from blog.services.market_article_autopublish_config import get_autopublish_settings
from blog.services.market_article_numeric_truth import build_market_truth_registry
from blog.services.market_article_qa_remediation import remediate_unverified_numeric_sentences
from blog.services.market_article_quality_gates import (
    build_snapshot_allowed_values,
    find_invented_public_claims,
    find_unverified_numeric_claims,
    public_content_surfaces,
    run_quality_gates,
)

User = get_user_model()


class NumericQATests(SimpleTestCase):
    def test_missing_snapshot_integers_not_critical_invention(self):
        allowed = build_snapshot_allowed_values(
            {'median_price_fmt': '۱۲,۵۰۰,۰۰۰ تومان'},
            {'valid_count': 1371},
            MarketArticleRun(valid_count=1371),
        )
        public = 'میانگین قیمت ۱۲,۵۰۰,۰۰۰ تومان بر اساس ۱۳۷۱ آگهی'
        invented = find_invented_public_claims(public, allowed)
        self.assertEqual(invented, [])

    def test_invented_price_is_detected(self):
        allowed = build_snapshot_allowed_values(
            {'median_price_fmt': '۱۰,۰۰۰,۰۰۰ تومان'},
            {},
            MarketArticleRun(),
        )
        public = 'قیمت میانگین ۹۹,۹۹۹,۹۹۹ میلیون تومان'
        invented = find_invented_public_claims(public, allowed)
        self.assertTrue(invented)

    def test_amenity_fraction_percent_verified(self):
        run = MarketArticleRun(
            valid_count=500,
            raw_count=520,
            quality_pct=96.0,
            report_json={
                'metrics': {'valid_count': 500},
                'report': {
                    'amenities_coverage': {
                        'استخر و جکوزی': {'pct': 1.9},
                    },
                },
            },
            content_html='<p>حدود ۱٫۹٪ از واحدها استخر یا جکوزی دارند.</p>',
            seo_json={'title': 't', 'excerpt': 'e'},
        )
        self.assertEqual(find_unverified_numeric_claims(run), [])

    def test_remediate_drops_sentence_with_fake_percent(self):
        run = MarketArticleRun(
            valid_count=100,
            raw_count=100,
            report_json={'metrics': {'valid_count': 100}, 'report': {'insights': ['x']}},
            content_html='<p>جمله اول. سهم بازار ۹۹٫۹٪ غیرواقعی است. جمله سوم.</p>',
            seo_json={'title': 't', 'excerpt': 'e'},
        )
        tokens = find_unverified_numeric_claims(run)
        self.assertTrue(tokens)
        with patch.object(run, 'save'):
            remediate_unverified_numeric_sentences(run, tokens)
        self.assertNotIn('۹۹٫۹٪', run.content_html or '')
        self.assertIn('جمله اول', run.content_html or '')

    def test_percentile_band_80_verified_when_range_present(self):
        run = MarketArticleRun(
            valid_count=800,
            raw_count=800,
            report_json={
                'metrics': {'valid_count': 800},
                'report': {
                    'price_per_sqm': {
                        'median_fmt': '۱۲۰ میلیون',
                        'range_80_fmt': '۱۰۰ تا ۱۴۰ میلیون',
                    },
                },
            },
            content_html='<p>۸۰٪ فایل‌ها بین ۱۰۰ تا ۱۴۰ میلیون قیمت‌گذاری شده‌اند.</p>',
            seo_json={'title': 't', 'excerpt': 'e'},
        )
        self.assertEqual(find_unverified_numeric_claims(run), [])
        registry = build_market_truth_registry(run)
        self.assertIn(80.0, registry.percent_values)

    def test_attr_numbers_not_counted_as_public_claims(self):
        run = MarketArticleRun(
            content_html='<img src="/media/chart_1371.png" class="w-100" alt="نمودار"><p>قیمت ۱۰ میلیون</p>',
            seo_json={'title': 'تحلیل', 'excerpt': 'خلاصه'},
        )
        public = public_content_surfaces(run)
        self.assertNotIn('1371.png', public)
        self.assertIn('۱۰ میلیون', public)


class PrivacyQATests(TestCase):
    def test_internal_report_token_not_public_critical(self):
        run = MarketArticleRun(
            report_json={'internal': 'share_token=abc123'},
            content_html='<div class="mk-market"><section class="mk-market-section" id="executive-summary"></section></div>',
            seo_json={'title': 'تحلیل بازار پونک', 'excerpt': 'خلاصه مقاله'},
        )
        qa = run_quality_gates(run, get_autopublish_settings())
        privacy = next(c for c in qa.checks if c.key == 'privacy')
        internal = next(c for c in qa.checks if c.key == 'privacy_internal_storage')
        self.assertTrue(privacy.passed)
        self.assertFalse(privacy.critical and not privacy.passed)
        self.assertFalse(internal.passed)

    def test_phone_in_public_content_fails_privacy(self):
        run = MarketArticleRun(
            content_html='<p>تماس 09121234567</p>',
            seo_json={'title': 'x', 'excerpt': 'y'},
        )
        qa = run_quality_gates(run, get_autopublish_settings())
        privacy = next(c for c in qa.checks if c.key == 'privacy')
        self.assertFalse(privacy.passed)
        self.assertTrue(privacy.critical)


class ContentStructureTests(TestCase):
    def test_composer_section_ids_counted(self):
        html = '''
        <div class="mk-market">
        <section class="mk-market-section" id="executive-summary"></section>
        <section class="mk-market-section" id="market-kpis"></section>
        <section class="mk-market-section" id="market-status"></section>
        <section class="mk-market-section" id="faq"></section>
        <section class="mk-market-section" id="verdict"></section>
        <section class="mk-market-section" id="extra"></section>
        <section class="mk-market-section" id="more"></section>
        </div>
        '''
        run = MarketArticleRun(content_html=html, seo_json={'title': 't', 'excerpt': 'e'})
        qa = run_quality_gates(run, get_autopublish_settings())
        structure = next(c for c in qa.checks if c.key == 'content_structure')
        self.assertTrue(structure.passed)
