"""تست صفحه آموزش اپ اندروید."""
from pathlib import Path
from django.test import TestCase, override_settings
from django.urls import reverse

from shop.android_tutorial_content import android_tutorial_content, android_tutorial_schema_json
from shop.android_tutorial_video import get_android_video_context, get_android_video_url


class AndroidTutorialPageTests(TestCase):
    def test_page_renders(self):
        response = self.client.get(reverse('android_tutorial'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'آموزش اپ اندروید')
        self.assertContains(response, 'chapter-install')
        self.assertNotContains(response, 'media/Video/android/')

    def test_schema_json_valid(self):
        import json
        raw = android_tutorial_schema_json()
        data = json.loads(raw)
        self.assertIn('@graph', data)
        types = {node['@type'] for node in data['@graph']}
        self.assertIn('FAQPage', types)
        self.assertIn('HowTo', types)
        self.assertIn('SoftwareApplication', types)

    def test_content_structure(self):
        content = android_tutorial_content()
        self.assertEqual(len(content['modules']), 6)
        self.assertGreater(len(content['faq']), 5)
        self.assertEqual(len(content['videos']), 7)

    def test_video_context_when_missing(self):
        ctx = get_android_video_context('overview')
        self.assertFalse(ctx['available'])
        self.assertEqual(ctx['filename'], 'ANDROID-OVERVIEW.mp4')

    @override_settings(MEDIA_ROOT='/tmp/test-media')
    def test_video_resolves_from_video_root_fallback(self):
        media_root = Path('/tmp/test-media')
        install_file = media_root / 'Video' / 'ANDROID-INSTALL.mp4'
        install_file.parent.mkdir(parents=True, exist_ok=True)
        install_file.write_bytes(b'fake-mp4')
        try:
            url = get_android_video_url('install')
            self.assertTrue(url.endswith('/media/Video/ANDROID-INSTALL.mp4'))
            ctx = get_android_video_context('install')
            self.assertTrue(ctx['available'])
            self.assertEqual(ctx['mode'], 'file')
        finally:
            if install_file.is_file():
                install_file.unlink()

    @override_settings(MEDIA_ROOT='/tmp/test-media')
    def test_video_prefers_android_subdir_when_both_exist(self):
        media_root = Path('/tmp/test-media')
        subdir_file = media_root / 'Video' / 'android' / 'ANDROID-INSTALL.mp4'
        root_file = media_root / 'Video' / 'ANDROID-INSTALL.mp4'
        subdir_file.parent.mkdir(parents=True, exist_ok=True)
        subdir_file.write_bytes(b'sub')
        root_file.write_bytes(b'root')
        try:
            url = get_android_video_url('install')
            self.assertIn('/Video/android/ANDROID-INSTALL.mp4', url)
        finally:
            subdir_file.unlink(missing_ok=True)
            root_file.unlink(missing_ok=True)

    @override_settings(MEDIA_ROOT='/tmp/test-media')
    def test_poster_state_when_video_missing(self):
        from django.conf import settings
        poster_rel = 'images/android/posters/android-video-install.jpg'
        poster_path = Path(settings.BASE_DIR) / 'static' / poster_rel
        poster_path.parent.mkdir(parents=True, exist_ok=True)
        poster_path.write_bytes(b'\xff\xd8\xff\xd9')
        try:
            ctx = get_android_video_context('install')
            self.assertFalse(ctx['available'])
            self.assertTrue(ctx['poster_available'])
            self.assertEqual(ctx['state'], 'poster')
            self.assertEqual(ctx['mode'], 'poster')
            response = self.client.get(reverse('android_tutorial'))
            self.assertContains(response, 'پیش‌نمایش')
            self.assertContains(response, 'ویدیو به‌زودی')
        finally:
            poster_path.unlink(missing_ok=True)

