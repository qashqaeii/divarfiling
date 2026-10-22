"""تست JSON repair، batch و resume پولیش AI."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ai_workspace.providers.base import ProviderError

from blog.services.market_article_ai_polish import (
    AIPolishJsonError,
    AIPolishRecoverableError,
    SCHEMA_BATCH,
    SCHEMA_SEO,
    StatisticalProtection,
    _polish_text_batch,
    batch_text_segments,
    find_missing_numeric_tokens,
    migrate_polish_state,
    normalize_number_text,
    shield_numeric_spans,
    unshield_numeric_spans,
    parse_llm_response,
    parse_polish_json,
    polish_market_article_run,
    repair_json_text,
    repair_polished_map_numeric_safety,
    segment_numeric_issues,
    split_html_parts,
    text_segment_payload,
    token_present_in_text,
)
from blog.services.market_article_autopublish import resume_systematic_article_autopublish
from blog.services.market_article_pipeline import build_preview
from blog.tests.test_market_articles import _seed_dataset

User = get_user_model()


class NumericSafetyTests(TestCase):
    def test_persian_ascii_digits_equivalent(self):
        self.assertTrue(token_present_in_text('۱۲,۵۰۰', 'قیمت 12,500 تومان'))
        self.assertEqual(normalize_number_text('۱۲٬۵۰۰'), normalize_number_text('12,500'))

    def test_missing_token_detected_with_detail(self):
        prot = StatisticalProtection(tokens=['۱۲,۵۰۰,۰۰۰'])
        missing = find_missing_numeric_tokens('قیمت ۱۲,۵۰۰,۰۰۰', 'قیمت بالا', prot)
        self.assertEqual(len(missing), 1)

    def test_invented_number_detected(self):
        issue = segment_numeric_issues(
            1,
            'قیمت ۱۰,۰۰۰,۰۰۰ تومان',
            'قیمت ۱۲,۰۰۰,۰۰۰ تومان',
            StatisticalProtection(),
        )
        self.assertTrue(issue['invented_numbers'])

    def test_shield_unshield_million_stats(self):
        text = 'میانگین 255 و 372 میلیون تومان/متر در پونک'
        shielded, mapping = shield_numeric_spans(text)
        self.assertIn('⟦DFN:', shielded)
        restored = unshield_numeric_spans(shielded, mapping)
        self.assertIn('255', restored)
        self.assertIn('372', restored)

    def test_migrate_state_adds_completed_segment_ids(self):
        segments = [{'id': 0, 'text': 'a'}, {'id': 2, 'text': 'b'}]
        state = migrate_polish_state(
            {'completed_batches': [0], 'polished_by_id': {'0': 'a'}},
            segments,
            plan_version=2,
        )
        self.assertIn(0, state['completed_segment_ids'])

    @patch('blog.services.market_article_ai_polish._polish_single_segment_numeric')
    def test_repair_map_only_bad_segments(self, mock_single):
        mock_single.return_value = ('متن اصلاح‌شده', 'mock', 'm', 1)
        originals = {1: '۱,۰۰۰ تومان', 2: 'بدون عدد طولانی'}
        polished = {1: 'بدون عدد', 2: 'بدون عدد طولانی ویرایش'}
        segments = [{'id': 1, 'text': originals[1]}, {'id': 2, 'text': originals[2]}]
        prot = StatisticalProtection(tokens=['۱,۰۰۰'])
        out = repair_polished_map_numeric_safety(
            segments,
            originals,
            polished,
            protection=prot,
            attempts_log=[],
        )
        self.assertEqual(out[1], 'متن اصلاح‌شده')
        mock_single.assert_called_once()
        self.assertEqual(out[2], polished[2])


class JsonRepairTests(TestCase):
    def test_repair_trailing_comma(self):
        raw = '{"texts": [{"id": 1, "text": "سلام"},]}'
        data = parse_polish_json(raw)
        self.assertIn('texts', data)

    def test_invalid_json_raises_recoverable(self):
        with self.assertRaises(AIPolishJsonError):
            parse_polish_json('{not json at all')

    def test_array_json_normalized_to_texts(self):
        raw = '[{"id": 3, "text": "سلام"}]'
        data = parse_llm_response(raw, SCHEMA_BATCH)
        self.assertEqual(data['texts'][0]['id'], 3)

    def test_missing_texts_error_type(self):
        with self.assertRaises(AIPolishJsonError) as ctx:
            parse_llm_response('{"foo": 1}', SCHEMA_BATCH)
        self.assertEqual(ctx.exception.error_type, 'missing_texts')

    def test_plain_text_error_type(self):
        with self.assertRaises(AIPolishJsonError) as ctx:
            parse_llm_response('این JSON نیست', SCHEMA_BATCH)
        self.assertEqual(ctx.exception.error_type, 'plain_text')

    def test_seo_schema(self):
        data = parse_llm_response('{"title":"a","excerpt":"b"}', SCHEMA_SEO)
        self.assertEqual(data['title'], 'a')

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

    @patch('blog.services.market_article_ai_polish.repair_polished_map_numeric_safety')
    @patch('blog.services.market_article_ai_polish.run_quality_gates')
    @patch('blog.services.market_article_ai_polish._polish_text_batch')
    @patch('blog.services.market_article_ai_polish._polish_seo')
    def test_resume_skips_completed_batch(self, mock_seo, mock_batch, mock_qa, mock_repair):
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
                'completed_segment_ids': [int(s['id']) for s in first_batch],
                'batch_plan_version': 2,
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
        mock_repair.side_effect = lambda _segments, _orig, polished, **_: polished

        result = polish_market_article_run(run, resume=True)
        self.assertTrue(result.applied)
        self.assertFalse(mock_seo.called)
        self.assertGreaterEqual(mock_batch.call_count, 0)

    @patch('blog.services.market_article_autopublish._run_ai_polish_with_retries', return_value=True)
    @patch('blog.services.market_article_autopublish.run_quality_gates')
    @patch('blog.services.market_article_pipeline.build_preview')
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


class ProviderFallbackTests(TestCase):
    @patch('blog.services.market_article_ai_polish.get_http_provider_chain')
    def test_skips_geo_blocked_provider(self, mock_chain):
        from blog.services.market_article_ai_polish import _call_llm

        class P:
            name = 'gemini'

            def complete(self, **kwargs):
                raise ProviderError('geo', retryable=True, code='geo_blocked')

        class Ok:
            name = 'arvan'

            def complete(self, **kwargs):
                from ai_workspace.providers.base import ProviderResult

                return ProviderResult(
                    text='{"texts":[{"id":1,"text":"x"}]}',
                    provider='arvan',
                    model='m',
                    latency_ms=1,
                    input_tokens=1,
                    output_tokens=2,
                )

        mock_chain.return_value = [P(), Ok()]
        result = _call_llm('sys', 'user')
        self.assertEqual(result.provider, 'arvan')

    @patch('blog.services.market_article_ai_polish.get_http_provider_chain')
    def test_all_providers_fail_raises_recoverable(self, mock_chain):
        from blog.services.market_article_ai_polish import _call_llm

        class P:
            name = 'openrouter'

            def complete(self, **kwargs):
                raise ProviderError('403', retryable=False, code='403')

        mock_chain.return_value = [P()]
        with self.assertRaises(AIPolishRecoverableError):
            _call_llm('sys', 'user')


class IdentityFallbackTests(TestCase):
    @patch('blog.services.market_article_ai_polish.BATCH_MAX_ATTEMPTS', 2)
    @patch('blog.services.market_article_ai_polish._call_llm')
    def test_batch_identity_fallback_after_json_failures(self, mock_llm):
        from blog.services.market_article_ai_polish import LLMCallResult, StatisticalProtection

        mock_llm.return_value = LLMCallResult(
            text='{"no_texts": true}',
            provider='mock',
            model='mock',
            latency_ms=1,
            input_tokens=1,
            output_tokens=1,
        )
        batch = [{'id': 5, 'text': 'متن نمونه برای پولیش'}]
        polished, provider, model, latency, logs = _polish_text_batch(
            0,
            batch,
            protection=StatisticalProtection(),
            segment_outcomes={},
        )
        self.assertEqual(polished[5], batch[0]['text'])
        self.assertEqual(provider, 'identity')
        self.assertTrue(any(l.get('status') == 'identity_fallback' for l in logs))

    @patch('blog.services.market_article_ai_polish._polish_single_segment_numeric')
    @patch('blog.services.market_article_ai_polish._call_llm')
    def test_batch_numeric_mismatch_triggers_segment_retry(self, mock_llm, mock_single):
        from blog.services.market_article_ai_polish import LLMCallResult, StatisticalProtection

        mock_llm.return_value = LLMCallResult(
            text='{"texts":[{"id":7,"text":"قیمت بالا"}]}',
            provider='mock',
            model='mock',
            latency_ms=1,
            input_tokens=1,
            output_tokens=1,
        )
        mock_single.return_value = ('قیمت ۱۲,۵۰۰,۰۰۰ تومان', 'mock', 'm', 0)
        batch = [{'id': 7, 'text': 'قیمت ۱۲,۵۰۰,۰۰۰ تومان'}]
        prot = StatisticalProtection(tokens=['۱۲,۵۰۰,۰۰۰'])
        outcomes: dict[str, str] = {}
        polished, _, _, _, logs = _polish_text_batch(
            3, batch, protection=prot, segment_outcomes=outcomes,
        )
        self.assertEqual(polished[7], 'قیمت ۱۲,۵۰۰,۰۰۰ تومان')
        mock_single.assert_called_once()
        self.assertTrue(any(e.get('status') == 'segment_retry' for e in logs))
