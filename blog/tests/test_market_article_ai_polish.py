"""تست پولیش AI مقالات سیستماتیک."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from blog.services.market_article_ai_polish import (
    AIPolishError,
    AIPolishRecoverableError,
    polish_market_article_run,
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

    @patch('blog.services.market_article_ai_polish._call_llm')
    def test_polish_applies_valid_json(self, mock_llm):
        run = build_preview(self.ds, self.staff)
        original = run.content_html
        payload = json.dumps(
            {'title': 'تحلیل بازار', 'excerpt': 'خلاصه', 'content_html': original},
            ensure_ascii=False,
        )
        mock_llm.return_value = (payload, 'mock', 'mock-model', 10)
        result = polish_market_article_run(run)
        self.assertTrue(result.applied)
        run.refresh_from_db()
        self.assertIn('mk-market', run.content_html)

    @patch('blog.services.market_article_ai_polish._call_llm')
    def test_polish_rejects_invalid_output(self, mock_llm):
        run = build_preview(self.ds, self.staff)
        mock_llm.return_value = (
            '{"title": "x", "excerpt": "y", "content_html": "<p>lorem ipsum</p>"}',
            'mock',
            'm',
            5,
        )
        with self.assertRaises(AIPolishError):
            polish_market_article_run(run)

    @patch('blog.services.market_article_ai_polish._call_llm', side_effect=AIPolishRecoverableError('down'))
    def test_polish_propagates_recoverable(self, _mock):
        run = build_preview(self.ds, self.staff)
        with self.assertRaises(AIPolishRecoverableError):
            polish_market_article_run(run)
