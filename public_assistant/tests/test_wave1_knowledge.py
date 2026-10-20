"""ارزیابی بازیابی موج ۱ فاز ۲ — offline، بدون DB."""
from __future__ import annotations

import json
from pathlib import Path

from django.test import SimpleTestCase

from public_assistant.audit.paths import audit_output_dir
from public_assistant.audit.retrieval_baseline import evaluate_retrieval
from public_assistant.audit.retrieval_offline import (
    _load_offline_chunks,
    make_offline_retrieve_fn,
    offline_retrieve,
)
from public_assistant.tests.eval_dataset import EVAL_QUESTIONS
from public_assistant.tests.eval_wave1_dataset import WAVE1_EVAL_QUESTIONS


class Wave1RetrievalTest(SimpleTestCase):
    def setUp(self):
        _load_offline_chunks.cache_clear()

    def test_wave1_hit_rate(self):
        report = evaluate_retrieval(make_offline_retrieve_fn(), WAVE1_EVAL_QUESTIONS)
        self.assertGreaterEqual(report['article_hit_at_5'], 0.70, msg=report.get('misses'))

    def test_offline_ranking_reaches_share_article(self):
        """کاندیدهای دیررس (ترتیب الفبایی فایل) نباید قبل از امتیازدهی حذف شوند."""
        chunks = offline_retrieve('چطوری لینک برای مشتری بفرستم', limit=5)
        article_ids = {c.article_id for c in chunks}
        self.assertIn('share-public-file', article_ids)

    def test_full_eval_not_regressed_badly(self):
        report = evaluate_retrieval(make_offline_retrieve_fn(), EVAL_QUESTIONS)
        self.assertGreaterEqual(report['article_hit_at_5'], 0.78)

    def test_compare_to_pre_phase2_baseline_if_present(self):
        pre_path = audit_output_dir() / 'retrieval_baseline_pre_phase2_wave1.json'
        if not pre_path.is_file():
            return
        pre = json.loads(pre_path.read_text(encoding='utf-8'))
        pre_rate = pre.get('eval_dataset', {}).get('article_hit_at_5', 0)
        post = evaluate_retrieval(make_offline_retrieve_fn(), EVAL_QUESTIONS)
        post_rate = post['article_hit_at_5']
        self.assertGreaterEqual(post_rate, pre_rate - 0.08)
