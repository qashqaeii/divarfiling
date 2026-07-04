"""تست سهمیه AI."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ai_workspace.constants import FEATURE_LISTING_SUMMARY
from ai_workspace.services.quota import QuotaExceededError, check_quota, consume_quota, get_or_create_quota

User = get_user_model()


@override_settings(AI_ENABLED=True)
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
        quota.listing_summary_used = 10
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

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=True)
    def test_daily_limit(self, _mock):
        quota = get_or_create_quota(self.user)
        quota.used_today = 10
        quota.save()
        with self.assertRaises(QuotaExceededError) as ctx:
            check_quota(self.user, FEATURE_LISTING_SUMMARY)
        self.assertEqual(ctx.exception.code, 'daily_limit')
