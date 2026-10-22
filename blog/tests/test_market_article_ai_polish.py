"""تست پولیش AI مقالات سیستماتیک."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from blog.services.market_article_ai_polish import (
    AIPolishError,
    AIPolishRecoverableError,
    apply_polished_texts,
    polish_market_article_run,
    split_html_parts,
    text_segment_payload,
    validate_markup_unchanged,
    validate_polished_html,
)
from blog.services.market_article_pipeline import build_preview
from blog.tests.test_market_articles import _seed_dataset

User = get_user_model()


@override_settings(MARKET_ARTICLE_SKIP_MAP_TILES=True, MARKET_ARTICLE_SKIP_ACCESS=True)
class MarketArticleAIPolishTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='polish_u', password='pass1234', phone='09120004001',
        )
        self.staff = User.objects.create_user(
            username='polish_admin', password='pass1234', phone='09120004002', is_staff=True,
        )
        self.ds = _seed_dataset(self.user, n=160, city='تبریز', district='ولیعصر')

    def test_validate_rejects_missing_numbers(self):
        errors = validate_polished_html(
            original_html='<p>قیمت ۱۲,۵۰۰,۰۰۰ تومان</p>',
            polished_html='<p>قیمت بالا</p>',
            protected_numbers=['۱۲,۵۰۰,۰۰۰'],
        )
        self.assertTrue(errors)

    def test_validate_accepts_preserved_structure(self):
        html = '<div class="mk-market"><p>۱,۲۰۰,۰۰۰ تومان</p><img src="/m.png" alt="نقشه"></div>'
        errors = validate_polished_html(
            original_html=html,
            polished_html=html.replace('تومان', 'تومان برای هر متر'),
            protected_numbers=['۱,۲۰۰,۰۰۰'],
        )
        self.assertEqual(errors, [])

    def test_markup_change_rejected(self):
        orig = '<a href="/blog/x" class="x">متن</a>'
        bad = '<a href="/blog/y" class="x">متن</a>'
        errors = validate_markup_unchanged(orig, bad)
        self.assertTrue(errors)

    @patch('blog.services.market_article_ai_polish.repair_polished_map_numeric_safety')
    @patch('blog.services.market_article_ai_polish.run_quality_gates')
    @patch('blog.services.market_article_ai_polish._polish_text_batch')
    @patch('blog.services.market_article_ai_polish._polish_seo')
    def test_polish_applies_valid_json(self, mock_seo, mock_batch, mock_qa, mock_repair):
        from blog.services.market_article_quality_gates import QAReport

        mock_qa.return_value = QAReport()
        mock_qa.return_value.total_score = 90
        mock_qa.return_value.critical_errors = 0

        run = build_preview(self.ds, self.staff)
        parts = split_html_parts(run.content_html)
        segments = text_segment_payload(parts)
        title = (run.seo_json or {}).get('title') or 't'
        excerpt = (run.seo_json or {}).get('excerpt') or 'e'
        mock_seo.return_value = (title, excerpt, 'mock', 'mock-model', 10, [])

        def batch_side_effect(batch_index, batch, **kwargs):
            return ({int(s['id']): s['text'] for s in batch}, 'mock', 'mock-model', 5, [])

        mock_batch.side_effect = batch_side_effect
        mock_repair.side_effect = lambda _segments, _orig, polished, **_: polished
        result = polish_market_article_run(run, resume=False)
        self.assertTrue(result.applied)
        run.refresh_from_db()
        self.assertIn('mk-market', run.content_html)

    @patch('blog.services.market_article_ai_polish._polish_seo')
    def test_polish_rejects_invalid_output(self, mock_seo):
        run = build_preview(self.ds, self.staff)
        mock_seo.side_effect = AIPolishError('SEO invalid')
        with self.assertRaises(AIPolishError):
            polish_market_article_run(run, resume=False)
        run.refresh_from_db()
        self.assertNotEqual(run.content_html, '')

    @patch('blog.services.market_article_ai_polish._polish_seo', side_effect=AIPolishRecoverableError('down'))
    def test_polish_propagates_recoverable(self, _mock):
        run = build_preview(self.ds, self.staff)
        before = run.content_html
        with self.assertRaises(AIPolishRecoverableError):
            polish_market_article_run(run, resume=False)
        run.refresh_from_db()
        self.assertEqual(run.content_html, before)

    def test_apply_polished_texts_keeps_markup(self):
        parts = split_html_parts('<p class="a">سلام</p>')
        out = apply_polished_texts(parts, {1: 'درود'})
        self.assertEqual(out, '<p class="a">درود</p>')

    @patch('blog.services.market_article_ai_polish.repair_polished_map_numeric_safety')
    @patch('blog.services.market_article_ai_polish.run_quality_gates')
    @patch('blog.services.market_article_ai_polish._polish_text_batch')
    @patch('blog.services.market_article_ai_polish._polish_seo')
    def test_polish_dry_run_does_not_persist_html(self, mock_seo, mock_batch, mock_qa, mock_repair):
        from blog.services.market_article_quality_gates import QAReport

        mock_qa.return_value = QAReport()
        mock_qa.return_value.total_score = 90
        mock_qa.return_value.critical_errors = 0
        run = build_preview(self.ds, self.staff)
        before = run.content_html
        seo = run.seo_json or {}
        mock_seo.return_value = (
            seo.get('title') or 't',
            seo.get('excerpt') or 'e',
            'mock',
            'm',
            1,
            [],
        )
        mock_batch.side_effect = lambda _i, batch, **_: (
            {int(s['id']): s['text'] for s in batch},
            'mock',
            'm',
            1,
            [],
        )
        mock_repair.side_effect = lambda _segments, _orig, polished, **_: polished
        result = polish_market_article_run(run, resume=False, persist=False)
        self.assertTrue(result.applied)
        self.assertFalse(result.report.get('persisted'))
        run.refresh_from_db()
        self.assertEqual(run.content_html, before)
