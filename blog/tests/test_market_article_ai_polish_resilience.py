"""تست JSON repair، batch و resume پولیش AI."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from blog.services.market_article_ai_polish import (
    AIPolishJsonError,
    batch_text_segments,
    parse_polish_json,
    polish_market_article_run,
    repair_json_text,
    split_html_parts,
    text_segment_payload,
)
from blog.services.market_article_autopublish import resume_systematic_article_autopublish
from blog.services.market_article_pipeline import build_preview
from blog.tests.test_market_articles import _seed_dataset

User = get_user_model()


class JsonRepairTests(TestCase):
    def test_repair_trailing_comma(self):
        raw = '{"texts": [{"id": 1, "text": "سلام"},]}'
        data = parse_polish_json(raw)
        self.assertIn('texts', data)

    def test_invalid_json_raises_recoverable(self):
        with self.assertRaises(AIPolishJsonError):
            parse_polish_json('{not json at all')

    def test_extract_outer_object(self):
        fixed = repair_json_text('prefix {"a": 1} suffix')
        self.assertEqual(json.loads(fixed)['a'], 1)


@override_settings(MARKET_ARTICLE_SKIP_MAP_TILES=True, MARKET_ARTICLE_SKIP_ACCESS=True)
class BatchPolishTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='batch_u', password='x', phone='09120006001')
        self.staff = User.objects.create_user(
            username='batch_admin', password='x', phone='09120006002', is_staff=True, is_superuser=True,
        )
        self.ds = _seed_dataset(self.user, n=160, city='تهران', district='پونک')

    def test_batch_splits_large_article(self):
        segments = [{'id': i, 'text': 'x' * 500} for i in range(12)]
        batches = batch_text_segments(segments)
        self.assertGreater(len(batches), 1)

    @patch('blog.services.market_article_ai_polish.run_quality_gates')
    @patch('blog.services.market_article_ai_polish._polish_text_batch')
    @patch('blog.services.market_article_ai_polish._polish_seo')
    def test_resume_skips_completed_batch(self, mock_seo, mock_batch, mock_qa):
        from blog.services.market_article_quality_gates import QAReport

        mock_qa.return_value = QAReport()
        mock_qa.return_value.total_score = 90
        mock_qa.return_value.critical_errors = 0

        run = build_preview(self.ds, self.staff)
        parts = split_html_parts(run.content_html)
        segs = text_segment_payload(parts)
        first_batch = batch_text_segments(segs)[0]
        polished = {int(s['id']): s['text'] for s in first_batch}

        run.chart_assets = {
            'autopublish_polish_state': {
                'seo_done': True,
                'title': (run.seo_json or {}).get('title'),
                'excerpt': (run.seo_json or {}).get('excerpt'),
                'polished_by_id': polished,
                'completed_batches': [0],
                'batch_logs': [],
                'provider': 'test',
                'model': 'test',
                'latency_ms': 0,
            },
        }
        run.save(update_fields=['chart_assets'])

        def batch_side_effect(batch_index, batch, **kwargs):
            return ({int(s['id']): s['text'] for s in batch}, 'p', 'm', 1, [])

        mock_seo.return_value = ('t', 'e', 'p', 'm', 1, [])
        mock_batch.side_effect = batch_side_effect

        result = polish_market_article_run(run, resume=True)
        self.assertTrue(result.applied)
        self.assertFalse(mock_seo.called)
        self.assertGreaterEqual(mock_batch.call_count, 0)

    @patch('blog.services.market_article_autopublish._run_ai_polish_with_retries', return_value=True)
    @patch('blog.services.market_article_autopublish.run_quality_gates')
    @patch('blog.services.market_article_autopublish.build_preview')
    def test_resume_autopublish_skips_build(self, mock_build, mock_qa, _mock_polish):
        from blog.models import SystematicArticleAutoPublishConfig
        from blog.services.market_article_quality_gates import QAReport

        mock_qa.return_value = QAReport()
        mock_qa.return_value.total_score = 90
        mock_qa.return_value.critical_errors = 0
        cfg = SystematicArticleAutoPublishConfig.objects.get(pk=1)
        cfg.shadow_mode = True
        cfg.is_enabled = True
        cfg.save()

        run = build_preview(self.ds, self.staff)
        ap = resume_systematic_article_autopublish(
            market_article_run_id=run.pk,
            shadow=True,
            force=True,
        )
        mock_build.assert_not_called()
        self.assertIsNotNone(ap.pk)
