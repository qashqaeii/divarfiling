"""تست توقف Autopublish قبل از پولیش به‌خاطر کیفیت داده."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from blog.models import MarketArticleRun, SystematicArticleAutoPublishConfig, SystematicArticleAutoPublishRun
from blog.services.market_article_autopublish import _pipeline_after_market_preview
from blog.services.market_article_autopublish_config import get_autopublish_settings
from blog.services.market_article_publish_decision import PublishAction, decide_publish_action
from blog.services.market_article_quality_gates import critical_pre_polish_data_failures, run_quality_gates
from blog.tests.test_market_articles import _seed_dataset

User = get_user_model()


def _configure_autopublish(**kwargs):
    cfg = SystematicArticleAutoPublishConfig.objects.get(pk=1)
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    cfg.save()
    return cfg


@override_settings(MARKET_ARTICLE_SKIP_MAP_TILES=True, MARKET_ARTICLE_SKIP_ACCESS=True)
class AutopublishDataQualityGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dq_owner', password='pass1234', phone='09120005001',
        )
        self.staff = User.objects.create_user(
            username='dq_admin', password='pass1234', phone='09120005002',
            is_staff=True, is_superuser=True,
        )
        self.ds = _seed_dataset(self.user, n=160, city='تهران', district='پونک')
        _configure_autopublish(
            min_records=150,
            min_valid_ratio=0.80,
            min_insights=0,
            quality_threshold=60,
        )

    def _market_run(self, *, valid: int, raw: int, quality_pct: float) -> MarketArticleRun:
        from blog.tests.test_market_article_autopublish_qa_flow import _minimal_numeric_clean_run

        run = _minimal_numeric_clean_run(self.ds)
        run.valid_count = valid
        run.raw_count = raw
        run.quality_pct = quality_pct
        run.report_json = {
            **(run.report_json or {}),
            'metrics': {'valid_count': valid, 'raw_count': raw, 'quality_pct': quality_pct},
        }
        run.save()
        return run

    def test_quality_57_percent_fails_pre_polish_data_gate(self):
        run = self._market_run(valid=57, raw=100, quality_pct=57.0)
        settings = get_autopublish_settings()
        qa = run_quality_gates(run, settings)
        failures = critical_pre_polish_data_failures(qa)
        self.assertTrue(any('57.0' in f or '57' in f for f in failures))

    def test_quality_82_percent_passes_pre_polish_data_gate(self):
        run = self._market_run(valid=164, raw=200, quality_pct=82.0)
        settings = get_autopublish_settings()
        qa = run_quality_gates(run, settings)
        self.assertEqual(critical_pre_polish_data_failures(qa), [])

    @patch('blog.services.market_article_autopublish.polish_market_article_run')
    def test_pipeline_blocks_polish_on_low_data_quality(self, mock_polish):
        run = self._market_run(valid=57, raw=100, quality_pct=57.0)
        autopublish = SystematicArticleAutoPublishRun.objects.create(
            run_date=run.created_at.date(),
            publish_mode=SystematicArticleAutoPublishRun.PublishMode.SHADOW,
            dataset=self.ds,
            market_article_run=run,
        )
        decision = decide_publish_action(self.ds, None)
        decision.action = PublishAction.CREATE_NEW
        out = _pipeline_after_market_preview(
            autopublish,
            run,
            decision,
            settings=get_autopublish_settings(),
            publish_mode=SystematicArticleAutoPublishRun.PublishMode.SHADOW,
            shadow=True,
            run_date=run.created_at.date(),
            user=self.staff,
        )
        self.assertEqual(out.status, SystematicArticleAutoPublishRun.Status.DATA_QUALITY_FAILED)
        mock_polish.assert_not_called()
        summary = (out.qa_report or {}).get('summary') or {}
        self.assertEqual(summary.get('publish_result'), 'data_quality_failed')
