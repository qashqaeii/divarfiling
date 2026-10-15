"""تست سهمیه AI — سطح رایگان / لایسنس نامحدود."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ai_workspace.constants import FEATURE_CRM_MESSAGE, FEATURE_LISTING_SUMMARY
from ai_workspace.services.quota import (
    QuotaExceededError,
    check_quota,
    consume_quota,
    feature_quota_dict,
    get_or_create_quota,
    get_status,
    is_ai_unlimited_user,
)

User = get_user_model()


@override_settings(AI_ENABLED=True, AI_LICENSED_UNLIMITED=True)
class QuotaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='quota_user', password='x', phone='09120000002',
        )

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    def test_free_user_can_consume_within_quota(self, _mock):
        for _ in range(3):
            check_quota(self.user, FEATURE_LISTING_SUMMARY)
            consume_quota(self.user, FEATURE_LISTING_SUMMARY)
        payload = feature_quota_dict(self.user, FEATURE_LISTING_SUMMARY)
        self.assertEqual(payload['feature_used'], 3)
        self.assertFalse(payload['is_unlimited'])

    @override_settings(AI_LICENSED_UNLIMITED=False)
    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    def test_legacy_no_license_raises(self, _mock):
        with self.assertRaises(QuotaExceededError) as ctx:
            check_quota(self.user, FEATURE_LISTING_SUMMARY)
        self.assertEqual(ctx.exception.code, 'no_license')

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    def test_feature_cap(self, _mock):
        quota = get_or_create_quota(self.user)
        quota.listing_summary_used = 30
        quota.save()
        with self.assertRaises(QuotaExceededError) as ctx:
            check_quota(self.user, FEATURE_LISTING_SUMMARY)
        self.assertEqual(ctx.exception.code, 'feature_limit')

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=True)
    def test_licensed_unlimited_skips_caps(self, _mock):
        quota = get_or_create_quota(self.user)
        quota.used_today = 100
        quota.tokens_used_today = 200_000
        quota.listing_summary_used = 50
        quota.save()
        self.assertTrue(is_ai_unlimited_user(self.user))
        check_quota(self.user, FEATURE_LISTING_SUMMARY)
        consume_quota(self.user, FEATURE_LISTING_SUMMARY)
        status = get_status(self.user)
        self.assertTrue(status.is_unlimited)
        self.assertTrue(status.has_license)
        self.assertEqual(status.remaining, 9999)

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    def test_staff_unlimited_without_license_flag(self, _mock):
        staff = User.objects.create_user(
            username='staff_quota_test',
            password='x',
            is_staff=True,
            phone='09120000001',
        )
        for _ in range(25):
            check_quota(staff, FEATURE_LISTING_SUMMARY)
            consume_quota(staff, FEATURE_LISTING_SUMMARY)
        status = get_status(staff)
        self.assertTrue(status.is_unlimited)
        self.assertFalse(status.has_license)

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    def test_daily_limit(self, _mock):
        quota = get_or_create_quota(self.user)
        quota.used_today = 30
        quota.save()
        with self.assertRaises(QuotaExceededError) as ctx:
            check_quota(self.user, FEATURE_LISTING_SUMMARY)
        self.assertEqual(ctx.exception.code, 'daily_limit')
        self.assertIn('لایسنس', str(ctx.exception))

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    def test_token_limit(self, _mock):
        quota = get_or_create_quota(self.user)
        quota.tokens_used_today = 90_000
        quota.save()
        with self.assertRaises(QuotaExceededError) as ctx:
            check_quota(self.user, FEATURE_LISTING_SUMMARY)
        self.assertEqual(ctx.exception.code, 'token_limit')

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    def test_feature_quota_dict(self, _mock):
        quota = get_or_create_quota(self.user)
        quota.listing_summary_used = 3
        quota.save()
        payload = feature_quota_dict(self.user, FEATURE_LISTING_SUMMARY)
        self.assertEqual(payload['feature_used'], 3)
        self.assertEqual(payload['feature_limit'], 30)
        self.assertEqual(payload['feature_remaining'], 27)
        self.assertEqual(payload['feature_percent_used'], 10)

    def test_license_expiry_returns_to_free_tier(self):
        with patch('ai_workspace.services.quota.has_active_bot_license', return_value=True):
            self.assertTrue(is_ai_unlimited_user(self.user))
        with patch('ai_workspace.services.quota.has_active_bot_license', return_value=False):
            self.assertFalse(is_ai_unlimited_user(self.user))
            quota = get_or_create_quota(self.user)
            quota.used_today = 29
            quota.save()
            check_quota(self.user, FEATURE_LISTING_SUMMARY)

    @patch('ai_workspace.services.quota.has_active_bot_license', return_value=False)
    def test_crm_message_free_limit(self, _mock):
        quota = get_or_create_quota(self.user)
        quota.crm_message_used = 24
        quota.save()
        with self.assertRaises(QuotaExceededError) as ctx:
            check_quota(self.user, FEATURE_CRM_MESSAGE)
        self.assertEqual(ctx.exception.code, 'feature_limit')
