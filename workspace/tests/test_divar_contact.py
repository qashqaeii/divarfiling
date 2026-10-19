"""تست‌های Feature Flag و مجوز API دریافت شماره از دیوار."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse

from workspace.divar_session_models import DivarContactFeatureConfig
from workspace.models import Dataset, Listing
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


class DivarConnectModalMarkupTests(TestCase):
    """پنجره اتصال دیوار باید با سیستم WSModal (کلاس is-open) سازگار باشد."""

    def setUp(self):
        self.superuser = User.objects.create_user(
            username='09121110099',
            phone='09121110099',
            password='x',
            is_superuser=True,
            is_staff=True,
        )
        self.dataset = Dataset.objects.create(
            user=self.superuser,
            name='تست دیوار',
            original_filename='test.xlsx',
            file_format='xlsx',
            transaction_type='فروش',
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='divar-modal-test',
            title='ملک تست مودال',
            price=1_000_000_000,
            area=100,
        )
        self.client = Client()
        self.client.force_login(self.superuser)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_listing_detail_divar_modal_uses_ws_modal_markup(self, _license):
        url = reverse(
            'workspace:listing_detail',
            kwargs={'dataset_id': self.dataset.pk, 'listing_id': self.listing.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('id="divar-connect-modal"', html)
        self.assertIn('data-divar-contact-box', html)
        self.assertIn('ws-modal-overlay', html)
        self.assertIn('ws-modal-panel', html)
        self.assertIn('divar_contact.js', html)
        self.assertIn('divar_contact.js?v=4', html)
        self.assertIn('data-divar-default-phone="09121110099"', html)
        self.assertIn('value="09121110099"', html)
        self.assertNotIn('ws-modal__backdrop', html)
        self.assertNotIn('ws-modal__panel', html)
        self.assertIn('mk-owner-divar-fetch', html)
        self.assertIn('data-divar-action-label', html)
        self.assertIn('mk-owner-divar-status', html)
        self.assertNotIn('mk-owner-box__divar-row', html)

    def test_divar_contact_js_opens_via_ws_modal(self):
        js_path = (
            Path(settings.BASE_DIR)
            / 'static'
            / 'workspace'
            / 'js'
            / 'divar_contact.js'
        )
        source = js_path.read_text(encoding='utf-8')
        self.assertIn('WSModal.open', source)
        self.assertIn('WSModal.close', source)
        self.assertNotIn('modal.hidden = false', source)
