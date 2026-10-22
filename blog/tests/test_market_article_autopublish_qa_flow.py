"""تست یکپارچه Polish → QA → Remediation در Autopublish."""
from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from blog.models import MarketArticleRun, SystematicArticleAutoPublishConfig, SystematicArticleAutoPublishRun
from blog.services.market_article_ai_polish import PolishResult, validate_polished_article
from blog.services.market_article_autopublish import (
    _run_post_polish_qa_with_remediation,
    _snapshot_pre_polish_content,
    run_systematic_article_autopublish,
)
from blog.services.market_article_candidate_selection import AutoPublishCandidate
from blog.services.market_article_autopublish_config import get_autopublish_settings
from blog.services.market_article_pipeline import build_preview
from blog.tests.test_market_articles import _seed_dataset

User = get_user_model()

_SECTION_IDS = (
    'executive-summary',
    'market-kpis',
    'market-status',
    'price-per-sqm',
    'faq',
    'verdict',
)


def _featured_png() -> SimpleUploadedFile:
    buf = BytesIO()
    Image.new('RGB', (1200, 630), color=(20, 80, 60)).save(buf, format='PNG')
    buf.seek(0)
    return SimpleUploadedFile('featured.png', buf.read(), content_type='image/png')


def _minimal_numeric_clean_run(ds) -> MarketArticleRun:
    """مقاله‌ای که QA کامل (شامل numeric) را بدون ادعای درصد غیرقابل‌تأیید پاس می‌کند."""
    filler = ' '.join(['تحلیل بازار تهران پونک و قیمت هر متر'] * 120)
    sections = ''.join(
        f'<section class="mk-market-section" id="{sid}"><p>{filler}</p></section>'
        for sid in _SECTION_IDS
    )
    html = f'<div class="mk-market"><h1>بازار پونک</h1>{sections}</div>'
    report = {
        'metrics': {'valid_count': 160, 'raw_count': 160},
        'dataset_meta': {'city': 'تهران', 'district': 'پونک'},
        'report': {
            'insights': ['بازار فعال است.', 'نقدشوندگی مناسب.'],
            'price_per_sqm': {'median_fmt': '۵۰ میلیون'},
            'market_depth': {'under_pct': 30, 'fair_pct': 50, 'over_pct': 20},
        },
    }
    return MarketArticleRun.objects.create(
        dataset=ds,
        market_key='tehran-poonak-test',
        valid_count=160,
        raw_count=160,
        quality_pct=95.0,
        report_json=report,
        content_html=html,
        seo_json={
            'title': 'تحلیل بازار پونک تهران',
            'excerpt': 'خلاصه بازار املاک پونک با داده واقعی.',
        },
        chart_assets={
            'chart_price_ladder': '/media/chart.png',
            'street_heat': '/media/heat.png',
        },
        featured_image=_featured_png(),
    )


def _configure_autopublish(**kwargs):
    cfg = SystematicArticleAutoPublishConfig.objects.get(pk=1)
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    cfg.save()
    return cfg


@override_settings(MARKET_ARTICLE_SKIP_MAP_TILES=True, MARKET_ARTICLE_SKIP_ACCESS=True)
class PolishQaRemediationFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='qa_flow_owner', password='pass1234', phone='09120004001',
        )
        self.staff = User.objects.create_user(
            username='qa_flow_admin', password='pass1234', phone='09120004002',
            is_staff=True, is_superuser=True,
        )
        self.ds = _seed_dataset(self.user, n=160, city='تهران', district='پونک')
        _configure_autopublish(
            is_enabled=False,
            shadow_mode=True,
            min_records=150,
            quality_threshold=60,
            min_insights=0,
        )

    def test_validate_polished_article_skips_numeric_claims_qa(self):
        run = build_preview(self.ds, self.staff)
        original_html = run.content_html or ''
        seo = dict(run.seo_json or {})
        bad_html = original_html + '<p>سهم ۱۳.۵٪ و ۱۲۶.۰٪ در متن.</p>'
        errors = validate_polished_article(
            run,
            original_html=original_html,
            polished_html=bad_html,
            original_title=str(seo.get('title') or ''),
            original_excerpt=str(seo.get('excerpt') or ''),
            new_title=str(seo.get('title') or ''),
            new_excerpt=str(seo.get('excerpt') or ''),
        )
        joined = ' '.join(errors)
        self.assertNotIn('۱۳.۵', joined)
        self.assertNotIn('126', joined)
        self.assertNotIn('ادعای عددی', joined)

    def test_post_polish_remediation_then_pass(self):
        run = _minimal_numeric_clean_run(self.ds)
        autopublish = SystematicArticleAutoPublishRun.objects.create(
            run_date=run.created_at.date(),
            publish_mode=SystematicArticleAutoPublishRun.PublishMode.SHADOW,
            status=SystematicArticleAutoPublishRun.Status.QA_RUNNING,
            market_article_run=run,
        )
        _snapshot_pre_polish_content(run)
        before = run.content_html
        run.content_html = (before or '') + (
            '<p>بند اضافی: سهم ۱۳.۵٪ و ۱۲۶.۰٪ غیرقابل‌تأیید.</p>'
        )
        run.save(update_fields=['content_html', 'updated_at'])
        settings = get_autopublish_settings()
        ok, qa = _run_post_polish_qa_with_remediation(autopublish, run, settings)
        self.assertTrue(ok, msg=(qa.failure_reasons if qa else []))
        self.assertIsNotNone(qa)
        self.assertNotIn('۱۳.۵٪', run.content_html or '')
        self.assertNotIn('۱۲۶.۰٪', run.content_html or '')

    def test_post_polish_qa_fails_when_remediation_cannot_fix_seo(self):
        run = build_preview(self.ds, self.staff)
        autopublish = SystematicArticleAutoPublishRun.objects.create(
            run_date=run.created_at.date(),
            publish_mode=SystematicArticleAutoPublishRun.PublishMode.SHADOW,
            status=SystematicArticleAutoPublishRun.Status.QA_RUNNING,
            market_article_run=run,
        )
        _snapshot_pre_polish_content(run)
        original_html = run.content_html
        seo = dict(run.seo_json or {})
        seo['excerpt'] = (seo.get('excerpt') or '') + ' سهم ۱۳.۵٪ بازار.'
        run.seo_json = seo
        run.save(update_fields=['seo_json', 'updated_at'])
        settings = get_autopublish_settings()
        ok, qa = _run_post_polish_qa_with_remediation(autopublish, run, settings)
        self.assertFalse(ok)
        self.assertIsNotNone(qa)
        self.assertTrue(any(c.key == 'data_numeric_claims' and not c.passed for c in qa.checks))

    def test_shadow_pipeline_polish_numeric_remediation(self):
        clean = _minimal_numeric_clean_run(self.ds)

        def _polish_inject_bad(run, **kwargs):
            run.content_html = (clean.content_html or '') + (
                '<p>بند موقت: سهم ۱۳.۵٪ و ۱۲۶.۰٪.</p>'
            )
            run.save(update_fields=['content_html', 'updated_at'])
            return PolishResult(
                applied=True,
                provider='test',
                model='test',
                latency_ms=1,
                report={'ok': True, 'fallback_ratio': 0.0},
            )

        candidate = AutoPublishCandidate(
            dataset_id=str(self.ds.pk),
            dataset_name=self.ds.name,
            city='تهران',
            district='پونک',
            transaction_type='فروش',
            subcategory='آپارتمان',
            row_count=160,
            valid_count=160,
            quality_pct=95.0,
            article_status='none',
            market_key='tehran-poonak',
            opportunity_score=88.0,
            action_hint='create',
            score_breakdown={'quality': 88.0},
            has_direct_duplicate=False,
            freshness_days=3,
        )
        with patch(
            'blog.services.market_article_autopublish.pick_best_candidate',
            return_value=candidate,
        ):
            with patch(
                'blog.services.market_article_autopublish.build_preview_for_autopublish',
                return_value=clean,
            ):
                with patch(
                    'blog.services.market_article_autopublish.polish_market_article_run',
                    side_effect=_polish_inject_bad,
                ):
                    ap_run = run_systematic_article_autopublish(shadow=True, force=True)
        self.assertEqual(ap_run.status, SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW)
        market_run = ap_run.market_article_run
        self.assertNotIn('۱۳.۵٪', market_run.content_html or '')
        summary = (ap_run.qa_report or {}).get('summary') or {}
        self.assertEqual(summary.get('publish_result'), 'shadow_ok')
