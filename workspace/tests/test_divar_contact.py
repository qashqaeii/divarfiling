"""تست‌های Feature Flag و مجوز API دریافت شماره از دیوار."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.divar_session_models import DivarContactFeatureConfig
from workspace.services.divar_session.feature import update_rollout_mode, user_can_use_divar_contact

User = get_user_model()


class DivarContactFeatureFlagTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='09121110001',
            phone='09121110001',
            password='x',
            is_superuser=True,
            is_staff=True,
        )
        self.staff = User.objects.create_user(
            username='09121110002',
            phone='09121110002',
            password='x',
            is_staff=True,
            is_superuser=False,
        )
        self.user = User.objects.create_user(
            username='09121110003',
            phone='09121110003',
            password='x',
        )
        self.client = Client()

    def test_default_admin_only_superuser_only(self):
        cfg = DivarContactFeatureConfig.objects.get(singleton_key='default')
        self.assertEqual(cfg.rollout_mode, DivarContactFeatureConfig.RolloutMode.ADMIN_ONLY)
        self.assertTrue(user_can_use_divar_contact(self.superuser))
        self.assertFalse(user_can_use_divar_contact(self.staff))
        self.assertFalse(user_can_use_divar_contact(self.user))

    def test_api_forbidden_for_regular_user(self):
        self.client.force_login(self.user)
        url = reverse('workspace:divar_contact_status')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_api_ok_for_superuser(self):
        self.client.force_login(self.superuser)
        url = reverse('workspace:divar_contact_status')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])

    def test_enabled_for_all_allows_regular_user(self):
        update_rollout_mode(
            rollout_mode=DivarContactFeatureConfig.RolloutMode.ENABLED_FOR_ALL,
            changed_by=self.superuser,
        )
        self.assertTrue(user_can_use_divar_contact(self.user))
        self.client.force_login(self.user)
        resp = self.client.get(reverse('workspace:divar_contact_status'))
        self.assertEqual(resp.status_code, 200)

    def test_disabled_blocks_superuser(self):
        update_rollout_mode(
            rollout_mode=DivarContactFeatureConfig.RolloutMode.DISABLED,
            changed_by=self.superuser,
        )
        self.assertFalse(user_can_use_divar_contact(self.superuser))
        self.client.force_login(self.superuser)
        resp = self.client.get(reverse('workspace:divar_contact_status'))
        self.assertEqual(resp.status_code, 403)

    def test_audit_log_on_rollout_change(self):
        from workspace.divar_session_models import DivarContactFeatureAuditLog

        update_rollout_mode(
            rollout_mode=DivarContactFeatureConfig.RolloutMode.ENABLED_FOR_ALL,
            changed_by=self.superuser,
        )
        self.assertTrue(
            DivarContactFeatureAuditLog.objects.filter(
                field_name='rollout_mode',
                new_value='enabled_for_all',
            ).exists(),
        )
