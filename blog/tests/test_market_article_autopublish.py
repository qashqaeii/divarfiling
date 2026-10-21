"""تست انتشار خودکار مقالات سیستماتیک."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from blog.models import (
    MarketArticleLink,
    MarketArticleRun,
    Post,
    SystematicArticleAutoPublishConfig,
    SystematicArticleAutoPublishRun,
)
from blog.services.market_article_autopublish import (
    AutoPublishBlocked,
    publish_market_article_from_run,
    recover_stuck_autopublish_runs,
    run_systematic_article_autopublish,
)
from blog.services.market_article_ai_polish import PolishResult
from blog.services.market_article_autopublish_config import get_autopublish_settings, local_today
from blog.services.market_article_candidate_selection import pick_best_candidate
from blog.services.market_article_pipeline import build_preview, create_draft
from blog.services.market_article_publish_decision import PublishAction, decide_publish_action
from blog.services.market_article_quality_gates import run_quality_gates
from blog.tests.test_market_articles import _seed_dataset

User = get_user_model()


def _configure_autopublish(**kwargs):
    cfg = SystematicArticleAutoPublishConfig.objects.get(pk=1)
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    cfg.save()
    return cfg


def _mock_polish_pass(run):
    return PolishResult(applied=True, provider='test', model='test', latency_ms=1, report={'ok': True})


def _clear_today_autopublish_runs():
    SystematicArticleAutoPublishRun.objects.filter(run_date=local_today()).delete()


@override_settings(MARKET_ARTICLE_SKIP_MAP_TILES=True, MARKET_ARTICLE_SKIP_ACCESS=True)
class MarketArticleAutoPublishTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='owner_auto', password='pass1234', phone='09120003001',
        )
        self.staff = User.objects.create_user(
            username='admin_auto', password='pass1234', phone='09120003002', is_staff=True, is_superuser=True,
        )
        self.ds = _seed_dataset(self.user, n=160, city='کرج', district='مهرشهر')
        _configure_autopublish(
            is_enabled=False,
            shadow_mode=True,
            min_records=150,
            quality_threshold=70,
        )

    def test_no_candidate_when_weak_dataset(self):
        weak = _seed_dataset(self.user, n=120, city='قم', district='بلوار')
        _configure_autopublish(min_records=200)
        candidate = pick_best_candidate(get_autopublish_settings())
        self.assertIsNone(candidate)

    def test_candidate_picks_strong_dataset(self):
        candidate = pick_best_candidate(get_autopublish_settings())
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.dataset_id, str(self.ds.pk))

    def test_duplicate_intent_update_instead_of_create(self):
        run = build_preview(self.ds, self.staff)
        post = create_draft(run, self.staff)
        post.is_published = True
        post.published_at = timezone.now()
        post.save()
        self.ds.mark_updated()

        decision = decide_publish_action(self.ds, pick_best_candidate(get_autopublish_settings()))
        self.assertEqual(decision.action, PublishAction.UPDATE_EXISTING)

    def test_dry_run_never_builds(self):
        with patch('blog.services.market_article_autopublish.build_preview') as mock_build:
            run = run_systematic_article_autopublish(dry_run=True)
            mock_build.assert_not_called()
        self.assertEqual(run.publish_mode, SystematicArticleAutoPublishRun.PublishMode.DRY_RUN)
        self.assertTrue(run.would_publish or run.status == SystematicArticleAutoPublishRun.Status.SKIPPED)

    def test_shadow_mode_never_publishes(self):
        with patch('blog.services.market_article_autopublish.polish_market_article_run', side_effect=_mock_polish_pass):
            run = run_systematic_article_autopublish(shadow=True, force=True)
        self.assertIn(run.status, (
            SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW,
            SystematicArticleAutoPublishRun.Status.QA_FAILED,
            SystematicArticleAutoPublishRun.Status.SKIPPED,
        ))
        if run.post_id:
            self.fail('Shadow mode published a post')
        published = Post.objects.filter(is_published=True).count()
        self.assertEqual(published, 0)

    @patch('blog.services.market_article_autopublish.run_quality_gates')
    def test_successful_live_publish(self, mock_qa):
        from blog.services.market_article_quality_gates import QAReport

        _clear_today_autopublish_runs()
        mock_qa.return_value = QAReport()
        mock_qa.return_value.total_score = 95
        mock_qa.return_value.critical_errors = 0
        _configure_autopublish(is_enabled=True, shadow_mode=False, quality_threshold=60, min_insights=0)
        with patch('blog.services.market_article_autopublish.polish_market_article_run', side_effect=_mock_polish_pass):
            run = run_systematic_article_autopublish(force=True)
        self.assertIn(run.status, (
            SystematicArticleAutoPublishRun.Status.PUBLISHED,
            SystematicArticleAutoPublishRun.Status.UPDATED,
        ))
        self.assertTrue(run.post.is_published)

    @patch('blog.services.market_article_autopublish.run_quality_gates')
    def test_max_one_publish_per_day(self, mock_qa):
        from blog.services.market_article_quality_gates import QAReport

        _clear_today_autopublish_runs()
        mock_qa.return_value = QAReport()
        mock_qa.return_value.total_score = 95
        mock_qa.return_value.critical_errors = 0
        _configure_autopublish(is_enabled=True, shadow_mode=False, quality_threshold=60, min_insights=0)
        with patch('blog.services.market_article_autopublish.polish_market_article_run', side_effect=_mock_polish_pass):
            first = run_systematic_article_autopublish(force=True)
        self.assertIn(
            first.status,
            (SystematicArticleAutoPublishRun.Status.PUBLISHED, SystematicArticleAutoPublishRun.Status.UPDATED),
        )
        with self.assertRaises(AutoPublishBlocked):
            run_systematic_article_autopublish(force=True)

    def test_disabled_blocks_live(self):
        _configure_autopublish(is_enabled=False, shadow_mode=False)
        with self.assertRaises(AutoPublishBlocked):
            run_systematic_article_autopublish()

    def test_update_preserves_slug(self):
        run = build_preview(self.ds, self.staff)
        post = create_draft(run, self.staff)
        old_slug = post.slug
        run2 = build_preview(self.ds, self.staff)
        published = publish_market_article_from_run(run2, user=self.staff, is_update=True)
        self.assertEqual(published.slug, old_slug)

    def test_featured_image_missing_blocks_qa(self):
        run = build_preview(self.ds, self.staff)
        run.featured_image = None
        run.save(update_fields=['featured_image'])
        qa = run_quality_gates(run, get_autopublish_settings())
        self.assertGreater(qa.critical_errors, 0)
        self.assertTrue(any('Featured' in r for r in qa.failure_reasons))

    def test_score_below_threshold_blocks(self):
        run = build_preview(self.ds, self.staff)
        _configure_autopublish(quality_threshold=99, min_insights=99)
        qa = run_quality_gates(run, get_autopublish_settings())
        from blog.services.market_article_quality_gates import qa_passes_for_publish
        self.assertFalse(qa_passes_for_publish(qa, get_autopublish_settings()))

    def test_management_command_dry_run(self):
        out = call_command('run_systematic_article_autopublish', '--dry-run')
        self.assertIsNone(out)

    def test_autopublish_admin_page(self):
        c = Client()
        c.force_login(self.staff)
        resp = c.get(reverse('admin_panel_blog_systematic_autopublish'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'انتشار خودکار')

    def test_privacy_fields_not_in_article(self):
        run = build_preview(self.ds, self.staff)
        blob = str(run.content_html) + str(run.report_json)
        self.assertNotIn('token0', blob.lower())

    def test_no_candidate_skips(self):
        SystematicArticleAutoPublishConfig.objects.filter(pk=1).update(min_records=99999)
        run = run_systematic_article_autopublish(shadow=True, force=True)
        self.assertEqual(run.status, SystematicArticleAutoPublishRun.Status.SKIPPED)

    @patch('blog.services.market_article_autopublish.run_quality_gates')
    def test_concurrent_blocked_after_publish(self, mock_qa):
        from blog.services.market_article_quality_gates import QAReport

        _clear_today_autopublish_runs()
        mock_qa.return_value = QAReport()
        mock_qa.return_value.total_score = 95
        mock_qa.return_value.critical_errors = 0
        _configure_autopublish(is_enabled=True, shadow_mode=False, quality_threshold=60, min_insights=0)
        with patch('blog.services.market_article_autopublish.polish_market_article_run', side_effect=_mock_polish_pass):
            first = run_systematic_article_autopublish(force=True)
        self.assertIn(
            first.status,
            (SystematicArticleAutoPublishRun.Status.PUBLISHED, SystematicArticleAutoPublishRun.Status.UPDATED),
        )
        count = SystematicArticleAutoPublishRun.objects.filter(
            run_date=local_today(),
            status__in=(
                SystematicArticleAutoPublishRun.Status.PUBLISHED,
                SystematicArticleAutoPublishRun.Status.UPDATED,
            ),
        ).count()
        self.assertEqual(count, 1)

    def test_recover_stuck_generating_run(self):
        stuck = SystematicArticleAutoPublishRun.objects.create(
            run_date=local_today(),
            status=SystematicArticleAutoPublishRun.Status.GENERATING,
            action=SystematicArticleAutoPublishRun.Action.CREATE_NEW,
            publish_mode=SystematicArticleAutoPublishRun.PublishMode.SHADOW,
        )
        SystematicArticleAutoPublishRun.objects.filter(pk=stuck.pk).update(
            updated_at=timezone.now() - timedelta(hours=7),
        )
        n = recover_stuck_autopublish_runs(max_age_hours=6)
        self.assertEqual(n, 1)
        stuck.refresh_from_db()
        self.assertEqual(stuck.status, SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW)

    def test_ai_polish_failure_blocks_publish(self):
        from blog.services.market_article_ai_polish import AIPolishRecoverableError

        _configure_autopublish(is_enabled=True, shadow_mode=False, quality_threshold=60, min_insights=0)

        def _fail_polish(_run):
            raise AIPolishRecoverableError('providers down')

        with patch('blog.services.market_article_autopublish.polish_market_article_run', side_effect=_fail_polish):
            run = run_systematic_article_autopublish(force=True)
        self.assertEqual(run.status, SystematicArticleAutoPublishRun.Status.AI_POLISH_FAILED)
        self.assertFalse(Post.objects.filter(is_published=True).exists())

    def test_duplicate_create_blocked_when_link_exists(self):
        run = build_preview(self.ds, self.staff)
        post = create_draft(run, self.staff)
        post.is_published = True
        post.published_at = timezone.now()
        post.save()
        self.ds.mark_updated()

        _configure_autopublish(is_enabled=True, shadow_mode=False, quality_threshold=60, min_insights=0)
        with patch('blog.services.market_article_autopublish.polish_market_article_run', side_effect=_mock_polish_pass):
            ap_run = run_systematic_article_autopublish(force=True)
        if ap_run.status == SystematicArticleAutoPublishRun.Status.PUBLISHED:
            self.fail('Should not create duplicate published post')
        self.assertIn(ap_run.status, (
            SystematicArticleAutoPublishRun.Status.UPDATED,
            SystematicArticleAutoPublishRun.Status.SKIPPED,
            SystematicArticleAutoPublishRun.Status.QA_FAILED,
            SystematicArticleAutoPublishRun.Status.NEEDS_REVIEW,
        ))
