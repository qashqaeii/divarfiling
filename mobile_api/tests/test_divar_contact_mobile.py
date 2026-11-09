"""تست‌های API موبایل دریافت شماره از دیوار."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from workspace.divar_session_models import DivarContactFeatureConfig
from workspace.models import Dataset, Listing
from workspace.services.divar_session.feature import update_rollout_mode

User = get_user_model()


class DivarContactMobileApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09123330001',
            phone='09123330001',
            password='x',
        )
        self.superuser = User.objects.create_user(
            username='09123330002',
            phone='09123330002',
            password='x',
            is_superuser=True,
            is_staff=True,
        )
        self.dataset = Dataset.objects.create(
            user=self.superuser,
            name='d1',
            original_filename='d1.json',
            file_format='json',
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='tok-divar-mobile-1',
            title='آگهی تست',
            link='https://divar.ir/v/tok-divar-mobile-1',
        )
        self.client = APIClient()

    def test_status_disabled_for_regular_user_by_default(self):
        DivarContactFeatureConfig.objects.get_or_create(singleton_key='default')
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/mobile/v1/filing/divar-contact/status')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['ok'])
        self.assertFalse(body['data']['enabled'])

    def test_status_enabled_for_superuser(self):
        self.client.force_authenticate(user=self.superuser)
        resp = self.client.get(
            f'/api/mobile/v1/filing/listings/{self.listing.token}/divar-contact/status',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['ok'])
        self.assertTrue(body['data']['enabled'])
        self.assertEqual(body['data']['status']['button_state'], 'connect')
        self.assertIn('divar.ir', body['data']['captcha_fallback_url'])

    def test_otp_send_forbidden_for_regular_user(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            '/api/mobile/v1/filing/divar-contact/otp/send',
            {'phone': '09121234567'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(resp.json()['ok'])

    def test_fetch_not_found_listing(self):
        update_rollout_mode(
            rollout_mode=DivarContactFeatureConfig.RolloutMode.ENABLED_FOR_ALL,
            changed_by=self.superuser,
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            '/api/mobile/v1/filing/listings/missing-token/divar-contact/fetch',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)
