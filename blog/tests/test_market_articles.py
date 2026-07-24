"""تست مقالات سیستماتیک — پنل ادمین و پایپ‌لاین."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from blog.models import MarketArticleLink, MarketArticleRun, Post
from blog.services.market_article_analyze import sanitize_report_for_public
from blog.services.market_article_assets import render_featured_image
from blog.services.market_article_composer import compose_market_article
from blog.services.market_article_eligibility import (
    ARTICLE_STATUS_STALE,
    build_market_key,
    eligible_datasets_qs,
    market_key_for_dataset,
)
from blog.services.market_article_pipeline import (
    MarketArticleError,
    build_preview,
    create_draft,
    update_existing_post,
)
from workspace.models import Dataset, Listing

User = get_user_model()


def _seed_dataset(user, *, n=100, city='اهواز', district='کیانپارس'):
    ds = Dataset.objects.create(
        user=user,
        name='تست بازار کیانپارس',
        original_filename='test.xlsx',
        file_format='xlsx',
        row_count=n,
        city=city,
        district=district,
        transaction_type='فروش',
        subcategory='آپارتمان',
    )
    listings = []
    for i in range(n):
        area = 70 + (i % 40)
        price = int((45_000_000 + (i % 20) * 1_500_000) * area)
        listings.append(Listing(
            dataset=ds,
            token=f'token{i:04d}',
            title=f'آگهی {i}',
            price=price,
            area=float(area),
            rooms=str(1 + (i % 3)),
            neighborhood=district,
            city=city,
            latitude=31.32 + (i % 50) * 0.001,
            longitude=48.67 + (i % 50) * 0.001,
            published_at=timezone.now() - timezone.timedelta(days=i % 40),
            data={'elevator': i % 2 == 0, 'parking': i % 3 == 0},
        ))
    Listing.objects.bulk_create(listings)
    ds.sync_row_count()
    return ds


class MarketArticleEligibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='owner_sys', password='pass1234', phone='09120001001',
        )
        self.staff = User.objects.create_user(
            username='admin_sys', password='pass1234', phone='09120001002', is_staff=True,
        )
        self.ds = _seed_dataset(self.user)

    def test_eligible_queryset_includes_quality_dataset(self):
        self.assertTrue(eligible_datasets_qs().filter(pk=self.ds.pk).exists())

    def test_market_key_stable(self):
        key = market_key_for_dataset(self.ds)
        self.assertTrue(key.startswith('tahlil-bazar-'))
        self.assertEqual(key, build_market_key(
            city='اهواز',
            district='کیانپارس',
            transaction_type='فروش',
            subcategory='آپارتمان',
        ))

    def test_admin_list_requires_staff(self):
        c = Client()
        url = reverse('admin_panel_blog_systematic')
        self.assertNotEqual(c.get(url).status_code, 200)
        c.force_login(self.staff)
        resp = c.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'مقالات')


class MarketArticleSanitizeComposerTests(TestCase):
    def test_sanitize_strips_blocked_keys(self):
        payload = {
            'report': {
                'confidence': {'score': 80},
                'token': 'SECRETTOKEN123',
                'opportunities': {'count': 3, 'items': [{'token': 'abc', 'area_fmt': '۸۰'}]},
            },
            'geo_points': [{'lat': 1.0, 'lng': 2.0, 'w': 1}],
        }
        cleaned = sanitize_report_for_public(payload)
        self.assertNotIn('token', cleaned.get('report', {}))
        self.assertIn('_geo_for_assets', cleaned)

    def test_composer_uses_report_numbers_and_faq(self):
        report = {
            'tx': {'is_sale': True, 'is_rent': False},
            'confidence': {'score': 82, 'display_score': 82, 'level': 'بالا'},
            'data_quality': {'valid_count': 120, 'raw_count': 130, 'removed_count': 10, 'quality_pct': 92},
            'publication_scope': {'date_from_fmt': '۱۴۰۴/۰۱/۰۱', 'date_to_fmt': '۱۴۰۴/۰۳/۰۱', 'analyzed_count': 120},
            'market_sentiment': {'label': 'مناسب خریدار', 'factors': ['۳۵٪ زیر بازار']},
            'liquidity': {'label': 'نقدشوندگی متوسط', 'score': 55},
            'price_analysis': {
                'price_per_sqm': {'median_fmt': '۵۰ میلیون', 'p25_fmt': '۴۰ میلیون', 'p75_fmt': '۶۰ میلیون', 'cv': 18},
                'price': {'median_fmt': '۴ میلیارد'},
            },
            'market_depth': {'under_pct': 30, 'fair_pct': 50, 'over_pct': 20},
            'price_trends': {'has_data': True, 'pps_monthly_fmt': '+۲٪', 'trends': {'monthly': 2}, 'points': 40},
            'area_segments': [{'bucket': '۷۰–۹۰', 'bucket_plain': '۷۰ تا ۹۰ متر', 'count': 40, 'share_pct': 33}],
            'amenities_coverage': {'آسانسور': {'pct': 70}},
            'opportunities': {'count': 5},
            'negotiation': {'target_fmt': '۴۵ میلیون'},
            'insights': ['بازار فضای مذاکره دارد.'],
            'professional_summary': {'intro': 'خلاصه تست بازار.'},
        }
        composed = compose_market_article(
            report=report,
            dataset_meta={
                'city': 'اهواز',
                'district': 'کیانپارس',
                'transaction_type': 'فروش',
                'subcategory': 'آپارتمان',
            },
        )
        self.assertIn('۵۰ میلیون', composed['content_html'])
        self.assertIn('120', composed['content_html'])
        self.assertIn('سوالات متداول', composed['content_html'])
        self.assertIn('اگر خریدار', composed['content_html'])
        self.assertIn('اگر مشاور', composed['content_html'])
        self.assertIn('اگر سرمایه‌گذار', composed['content_html'])
        self.assertIn('اگر سازنده', composed['content_html'])
        self.assertGreaterEqual(len(composed['faq']), 5)
        self.assertNotIn('SECRET', composed['content_html'])

    def test_featured_image_png(self):
        content = render_featured_image(
            city='اهواز',
            district='کیانپارس',
            tx_label='فروش',
            pps_median_fmt='۵۰ میلیون',
            trend_fmt='+۱٪',
            valid_count=100,
            confidence_score=80,
            geo_points=[{'lat': 31.3 + i * 0.001, 'lng': 48.6 + i * 0.001, 'w': 1.0} for i in range(20)],
        )
        self.assertTrue(content.name.endswith('.png'))
        self.assertGreater(len(content.read()), 1000)


@override_settings(MARKET_ARTICLE_SKIP_MAP_TILES=True)
class MarketArticlePipelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='owner_pipe', password='pass1234', phone='09120002001',
        )
        self.staff = User.objects.create_user(
            username='admin_pipe', password='pass1234', phone='09120002002', is_staff=True,
        )
        self.ds = _seed_dataset(self.user, n=100)

    def test_build_preview_draft_update_keeps_slug(self):
        run = build_preview(self.ds, self.staff)
        self.assertEqual(run.status, MarketArticleRun.Status.PREVIEW)
        self.assertTrue(run.content_html)
        self.assertTrue(run.featured_image)
        self.assertGreaterEqual(run.valid_count, 50)

        post = create_draft(run, self.staff)
        self.assertFalse(post.is_published)
        self.assertEqual(post.slug, run.market_key)
        self.assertTrue(MarketArticleLink.objects.filter(market_key=run.market_key, post=post).exists())

        with self.assertRaises(MarketArticleError):
            create_draft(run, self.staff)

        run2 = build_preview(self.ds, self.staff)
        updated = update_existing_post(run2)
        self.assertEqual(updated.pk, post.pk)
        self.assertEqual(updated.slug, post.slug)

    def test_stale_status_when_dataset_newer(self):
        run = build_preview(self.ds, self.staff)
        create_draft(run, self.staff)
        link = MarketArticleLink.objects.get(market_key=run.market_key)
        link.last_generated_at = timezone.now() - timezone.timedelta(days=2)
        link.save(update_fields=['last_generated_at'])
        self.ds.mark_updated()

        from blog.services.market_article_eligibility import list_eligible_datasets
        listing = list_eligible_datasets()
        row = next(r for r in listing['rows'] if r['id'] == str(self.ds.pk))
        self.assertEqual(row['article_status'], ARTICLE_STATUS_STALE)

    def test_preview_page_staff(self):
        run = build_preview(self.ds, self.staff)
        c = Client()
        c.force_login(self.staff)
        resp = c.get(reverse('admin_panel_blog_systematic_preview', kwargs={'run_id': run.pk}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'پیش‌نمایش')
