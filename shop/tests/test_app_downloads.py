from unittest.mock import mock_open, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from shop.services.app_downloads import (
    ANDROID_APK_FILENAME,
    android_apk_available,
    build_android_apk_response,
)


class AndroidAppDownloadTests(TestCase):
    def test_download_url_returns_apk_when_file_exists(self):
        if not android_apk_available():
            self.skipTest('APK file not present in django/files/')
        response = self.client.get(reverse('android_app_download'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.android.package-archive',
        )
        self.assertIn(ANDROID_APK_FILENAME, response['Content-Disposition'])

    def test_license_guide_install_link_uses_in_page_fragment(self):
        response = self.client.get(reverse('license_guide'))
        self.assertContains(response, 'href="#mk-dl-android-install"')

    def test_license_guide_shows_download_hub(self):
        response = self.client.get(reverse('license_guide'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="download-apps"')
        self.assertContains(response, 'دانلود APK')
        self.assertContains(response, 'Play Protect')

    def test_dashboard_install_link_points_to_android_tutorial(self):
        user = get_user_model().objects.create_user(
            username='dlguide',
            password='test-pass-123',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, f'href="{reverse("android_tutorial")}"')
        self.assertNotContains(response, 'id="mk-dl-android-install"')
        self.assertNotContains(response, 'Play Protect')

    def test_dashboard_shows_android_link_for_authenticated_user(self):
        if not android_apk_available():
            self.skipTest('APK file not present in django/files/')
        user = get_user_model().objects.create_user(
            username='dltest',
            password='test-pass-123',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('android_app_download'))

    @patch('shop.services.app_downloads.os.path.isfile', return_value=True)
    @patch('shop.services.app_downloads.FileResponse', side_effect=RuntimeError('response failed'))
    def test_closes_file_if_file_response_raises(self, _mock_response, _mock_isfile):
        with patch('builtins.open', mock_open(read_data=b'apk')) as mocked_open:
            with self.assertRaises(RuntimeError):
                build_android_apk_response()
            mocked_open.return_value.close.assert_called_once()
