from unittest.mock import mock_open, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from shop.services.app_downloads import (
    ANDROID_APK_FILENAME,
    android_apk_available,
    android_apk_version_info,
    build_android_apk_response,
    parse_apk_version_from_filename,
)


class AndroidAppDownloadTests(TestCase):
    def test_parse_apk_version_from_filename(self):
        self.assertEqual(
            parse_apk_version_from_filename('divar-filing-v2.6.2-42-direct-release.apk'),
            ('2.6.2', 42),
        )
        self.assertEqual(
            parse_apk_version_from_filename('divar-filing-v2.6.0-40-release.apk'),
            ('2.6.0', 40),
        )
        self.assertIsNone(parse_apk_version_from_filename('random.apk'))

    def test_android_apk_version_info_from_resolved_filename(self):
        with patch('shop.services.app_downloads.android_apk_filename_resolved') as mock_name:
            mock_name.return_value = 'divar-filing-v2.6.2-42-direct-release.apk'
            version, build = android_apk_version_info()
        self.assertEqual(version, '2.6.2')
        self.assertEqual(build, 42)

    def test_download_url_returns_apk_when_file_exists(self):
        if not android_apk_available():
            self.skipTest('APK file not present in django/files/')
        response = self.client.get(reverse('android_app_download'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.android.package-archive',
        )
        self.assertIn('.apk', response['Content-Disposition'].lower())

    def test_license_guide_install_link_uses_in_page_fragment(self):
        response = self.client.get(reverse('license_guide'))
        self.assertContains(response, 'href="#mk-dl-android-notes"')

    def test_license_guide_shows_download_hub(self):
        response = self.client.get(reverse('license_guide'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="download-apps"')
        self.assertContains(response, 'دانلود APK')
        self.assertContains(response, 'Play Protect')

    def test_dashboard_downloads_in_separate_tab(self):
        user = get_user_model().objects.create_user(
            username='dlguide',
            password='test-pass-123',
        )
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'data-tab="downloads"')
        self.assertContains(response, 'id="tab-downloads"')
        self.assertContains(response, 'id="download-apps"')
        self.assertContains(response, "tabName = 'downloads'")
        if android_apk_available():
            self.assertContains(response, 'id="mk-dl-android-notes"')
            self.assertContains(response, 'Play Protect')
            self.assertContains(response, 'href="#mk-dl-android-notes"')
        self.assertContains(response, 'id="mk-dl-windows-notes"')
        self.assertContains(response, 'output')
        self.assertContains(response, 'توصیه‌شده')
        self.assertContains(response, 'استخراج گروهی')

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

    def test_build_app_download_context_without_user_attribute(self):
        from types import SimpleNamespace

        from shop.services.app_downloads import build_app_download_context

        request = SimpleNamespace()
        context = build_app_download_context(request)
        self.assertIsNone(context['windows_download'])

    @patch('shop.services.app_downloads.os.path.isfile', return_value=True)
    @patch('shop.services.app_downloads.FileResponse', side_effect=RuntimeError('response failed'))
    def test_closes_file_if_file_response_raises(self, _mock_response, _mock_isfile):
        with patch('builtins.open', mock_open(read_data=b'apk')) as mocked_open:
            with self.assertRaises(RuntimeError):
                build_android_apk_response()
            mocked_open.return_value.close.assert_called_once()
