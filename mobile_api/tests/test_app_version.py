from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch


@override_settings(SITE_URL='https://divarfiling.ir')
class AppVersionApiTests(TestCase):
    def test_app_version_public(self):
        with patch('shop.services.app_downloads.android_apk_available', return_value=True), \
             patch('shop.services.app_downloads.android_apk_version_info', return_value=('2.6.2', 42)), \
             patch('shop.services.app_downloads.android_apk_size_bytes', return_value=12_000_000), \
             patch('shop.services.app_downloads.android_apk_sha256', return_value='abc123'):
            response = self.client.get(reverse('mobile_api:app_version'), {'current_build': 30})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['ok'])
        data = body['data']
        self.assertEqual(data['package_id'], 'ir.divarfiling.mobile')
        self.assertEqual(data['version_name'], '2.6.2')
        self.assertEqual(data['version_code'], 42)
        self.assertTrue(data['update_available'])
        self.assertIn('/download/android/', data['apk_url'])
        self.assertEqual(data['apk_sha256'], 'abc123')
        self.assertEqual(response['Cache-Control'], 'no-cache, no-store, must-revalidate')

    def test_app_version_no_update_when_current(self):
        with patch('shop.services.app_downloads.android_apk_available', return_value=True), \
             patch('shop.services.app_downloads.android_apk_version_info', return_value=('2.6.2', 42)), \
             patch('shop.services.app_downloads.android_apk_sha256', return_value=''):
            response = self.client.get(
                reverse('mobile_api:app_version'),
                {'current_build': 42},
            )
        data = response.json()['data']
        self.assertFalse(data['update_available'])

    def test_force_when_below_min_supported(self):
        with patch('shop.services.app_downloads.android_apk_available', return_value=True), \
             patch('shop.services.app_downloads.ANDROID_MIN_SUPPORTED_BUILD', 40), \
             patch('shop.services.app_downloads.ANDROID_APP_BUILD', 45), \
             patch('shop.services.app_downloads.android_apk_sha256', return_value=''):
            response = self.client.get(reverse('mobile_api:app_version'), {'current_build': 20})
        data = response.json()['data']
        self.assertTrue(data['force_update'])
        self.assertTrue(data['update_available'])
