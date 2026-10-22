"""تست command resume_failed_market_article_polish."""
from __future__ import annotations

from unittest.mock import patch

from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from blog.models import SystematicArticleAutoPublishRun
from blog.services.market_article_pipeline import build_preview
from blog.tests.test_market_articles import _seed_dataset

User = get_user_model()


@override_settings(MARKET_ARTICLE_SKIP_MAP_TILES=True, MARKET_ARTICLE_SKIP_ACCESS=True)
class ResumeFailedPolishCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cmd_u', password='x', phone='09120008001')
        self.staff = User.objects.create_user(
            username='cmd_admin', password='x', phone='09120008002', is_staff=True,
        )
        self.ds = _seed_dataset(self.user, n=120, city='تهران', district='گلستان')
        self.market_run = build_preview(self.ds, self.staff)
        self.ap = SystematicArticleAutoPublishRun.objects.create(
            run_date=date(2026, 10, 22),
            status=SystematicArticleAutoPublishRun.Status.AI_POLISH_FAILED,
            publish_mode=SystematicArticleAutoPublishRun.PublishMode.SHADOW,
            dataset=self.ds,
            market_article_run=self.market_run,
            failure_reasons=['پولیش AI ناموفق: تست'],
        )

    @patch('blog.management.commands.resume_failed_market_article_polish.resume_systematic_article_autopublish')
    @patch('blog.management.commands.resume_failed_market_article_polish.polish_market_article_run')
    def test_autopublish_path_does_not_call_polish_directly(self, mock_polish, mock_resume):
        call_command(
            'resume_failed_market_article_polish',
            market_run=str(self.market_run.pk),
            autopublish_run=str(self.ap.pk),
            force=True,
            stdout=StringIO(),
        )
        mock_polish.assert_not_called()
        mock_resume.assert_called_once()

    @patch('blog.management.commands.resume_failed_market_article_polish.resume_systematic_article_autopublish')
    @patch('blog.management.commands.resume_failed_market_article_polish.polish_market_article_run')
    def test_polish_only_calls_polish_once(self, mock_polish, mock_resume):
        from blog.services.market_article_ai_polish import PolishResult

        mock_polish.return_value = PolishResult(
            applied=True,
            provider='mock',
            model='m',
            latency_ms=1,
            report={'fallback_ratio': 0.0, 'editorial_quality': {'total_recorded_tokens': 10}},
        )
        call_command(
            'resume_failed_market_article_polish',
            market_run=str(self.market_run.pk),
            polish_only=True,
            stdout=StringIO(),
        )
        mock_polish.assert_called_once()
        mock_resume.assert_not_called()

    def test_rejects_mismatched_autopublish_market_run(self):
        other = build_preview(self.ds, self.staff)
        self.ap.market_article_run = other
        self.ap.save(update_fields=['market_article_run'])
        with self.assertRaises(CommandError):
            call_command(
                'resume_failed_market_article_polish',
                market_run=str(self.market_run.pk),
                autopublish_run=str(self.ap.pk),
                force=True,
                stdout=StringIO(),
            )

    def test_rejects_wrong_autopublish_status(self):
        self.ap.status = SystematicArticleAutoPublishRun.Status.PUBLISHED
        self.ap.save(update_fields=['status'])
        with self.assertRaises(CommandError):
            call_command(
                'resume_failed_market_article_polish',
                market_run=str(self.market_run.pk),
                autopublish_run=str(self.ap.pk),
                force=True,
                stdout=StringIO(),
            )
