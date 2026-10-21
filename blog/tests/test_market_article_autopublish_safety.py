"""تست‌های مستقل: قفل هم‌زمان، duplicate، بازیابی stuck."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from blog.models import Post, SystematicArticleAutoPublishConfig, SystematicArticleAutoPublishRun
from blog.services.market_article_ai_polish import PolishResult
from blog.services.market_article_autopublish import (
    AutoPublishBlocked,
    _acquire_run_lock,
    _duplicate_publish_blocked,
    _has_active_run,
    recover_stuck_autopublish_runs,
    run_systematic_article_autopublish,
)
from blog.services.market_article_autopublish_config import local_today
from blog.tests.test_market_article_autopublish import _clear_today_autopublish_runs
from blog.services.market_article_pipeline import build_preview, create_draft
from blog.tests.test_market_articles import _seed_dataset

User = get_user_model()


def _mock_polish(run, **kwargs):
    return PolishResult(applied=True, provider='t', model='t', latency_ms=1, report={'ok': True})


@override_settings(MARKET_ARTICLE_SKIP_MAP_TILES=True, MARKET_ARTICLE_SKIP_ACCESS=True)
class AutoPublishSafetyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='safety_u', password='x', phone='09120005001')
        self.staff = User.objects.create_user(
            username='safety_admin', password='x', phone='09120005002', is_staff=True, is_superuser=True,
        )
        self.ds = _seed_dataset(self.user, n=160, city='شیراز', district='معالی‌آباد')
        cfg = SystematicArticleAutoPublishConfig.objects.get(pk=1)
        cfg.is_enabled = True
        cfg.shadow_mode = False
        cfg.quality_threshold = 60
        cfg.min_insights = 0
        cfg.save()

    def test_has_active_run_blocks_lock(self):
        SystematicArticleAutoPublishRun.objects.create(
            run_date=local_today(),
            status=SystematicArticleAutoPublishRun.Status.GENERATING,
            action=SystematicArticleAutoPublishRun.Action.CREATE_NEW,
            publish_mode=SystematicArticleAutoPublishRun.PublishMode.LIVE,
        )
        self.assertTrue(_has_active_run(local_today()))
        with self.assertRaises(AutoPublishBlocked):
            _acquire_run_lock(local_today())

    def test_recover_stuck_clears_active_lock(self):
        stuck = SystematicArticleAutoPublishRun.objects.create(
            run_date=local_today(),
            status=SystematicArticleAutoPublishRun.Status.AI_POLISHING,
            action=SystematicArticleAutoPublishRun.Action.CREATE_NEW,
            publish_mode=SystematicArticleAutoPublishRun.PublishMode.LIVE,
        )
        SystematicArticleAutoPublishRun.objects.filter(pk=stuck.pk).update(
            updated_at=timezone.now() - timedelta(hours=8),
        )
        self.assertTrue(_has_active_run(local_today()))
        recover_stuck_autopublish_runs(max_age_hours=6)
        self.assertFalse(_has_active_run(local_today()))

    def test_duplicate_publish_blocked_helper(self):
        run = build_preview(self.ds, self.staff)
        post = create_draft(run, self.staff)
        post.is_published = True
        post.save()
        reason = _duplicate_publish_blocked(
            run,
            'create_new',
            local_today(),
            exclude_run_id=None,
        )
        self.assertIsNotNone(reason)
        self.assertIn('وجود دارد', reason)

    @patch('blog.services.market_article_autopublish.run_quality_gates')
    @patch('blog.services.market_article_autopublish.polish_market_article_run', side_effect=_mock_polish)
    def test_second_run_same_day_blocked_after_publish(self, _polish, mock_qa):
        from blog.services.market_article_quality_gates import QAReport

        _clear_today_autopublish_runs()
        mock_qa.return_value = QAReport()
        mock_qa.return_value.total_score = 95
        mock_qa.return_value.critical_errors = 0

        first = run_systematic_article_autopublish(force=True)
        self.assertIn(
            first.status,
            (
                SystematicArticleAutoPublishRun.Status.PUBLISHED,
                SystematicArticleAutoPublishRun.Status.UPDATED,
            ),
        )
        with self.assertRaises(AutoPublishBlocked):
            run_systematic_article_autopublish(force=True)
        self.assertEqual(Post.objects.filter(is_published=True).count(), 1)
