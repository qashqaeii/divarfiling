"""تست سهمیه AI."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ai_workspace.constants import FEATURE_LISTING_SUMMARY
from ai_workspace.services.quota import (
    QuotaExceededError,
    check_quota,
    consume_quota,
    feature_quota_dict,
    get_or_create_quota,
)

User = get_user_model()


@override_settings(AI_ENABLED=True, AI_QUOTA_UNLIMITED_FOR_ALL=False)
class QuotaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='quota_user', password='x', phone='09120000002',
        )

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    def test_no_license_raises(self, _mock):
        with self.assertRaises(QuotaExceededError) as ctx:
            check_quota(self.user, FEATURE_LISTING_SUMMARY)
        self.assertEqual(ctx.exception.code, 'no_license')

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=True)
    def test_feature_cap(self, _mock):
        quota = get_or_create_quota(self.user)
        quota.listing_summary_used = 30
        quota.save()
        with self.assertRaises(QuotaExceededError) as ctx:
            check_quota(self.user, FEATURE_LISTING_SUMMARY)
        self.assertEqual(ctx.exception.code, 'feature_limit')

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=True)
    def test_staff_unlimited(self, _mock):
        staff = User.objects.create_user(
            username='staff_quota_test',
            password='x',
            is_staff=True,
            phone='09120000001',
        )
        for _ in range(25):
            check_quota(staff, FEATURE_LISTING_SUMMARY)
            consume_quota(staff, FEATURE_LISTING_SUMMARY)

    @override_settings(AI_QUOTA_UNLIMITED_FOR_ALL=True)
    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=True)
    def test_global_unlimited_ignores_quotas(self, _mock):
        quota = get_or_create_quota(self.user)
        quota.daily_limit = 1
        quota.used_today = 100
        quota.listing_summary_used = 100
        quota.tokens_used_today = 1000000
        quota.save()
        check_quota(self.user, FEATURE_LISTING_SUMMARY)
        consume_quota(self.user, FEATURE_LISTING_SUMMARY)

    @override_settings(AI_QUOTA_UNLIMITED_FOR_ALL=True)
    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    def test_unlimited_still_requires_license(self, _mock):
        with self.assertRaises(QuotaExceededError) as ctx:
            check_quota(self.user, FEATURE_LISTING_SUMMARY)
        self.assertEqual(ctx.exception.code, 'no_license')

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=True)
    def test_daily_limit(self, _mock):
        quota = get_or_create_quota(self.user)
        quota.used_today = 30
        quota.save()
        with self.assertRaises(QuotaExceededError) as ctx:
            check_quota(self.user, FEATURE_LISTING_SUMMARY)
        self.assertEqual(ctx.exception.code, 'daily_limit')

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=True)
    def test_feature_quota_dict(self, _mock):
        quota = get_or_create_quota(self.user)
        quota.listing_summary_used = 3
        quota.save()
        payload = feature_quota_dict(self.user, FEATURE_LISTING_SUMMARY)
        self.assertEqual(payload['feature_used'], 3)
        self.assertEqual(payload['feature_limit'], 30)
        self.assertEqual(payload['feature_remaining'], 27)
        self.assertEqual(payload['feature_percent_used'], 10)
