"""تست صفحه آموزش اپ اندروید."""
from django.test import TestCase
from django.urls import reverse

from shop.android_tutorial_content import android_tutorial_content, android_tutorial_schema_json
from shop.android_tutorial_video import get_android_video_context


class AndroidTutorialPageTests(TestCase):
    def test_page_renders(self):
        response = self.client.get(reverse('android_tutorial'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'آموزش اپ اندروید')
        self.assertContains(response, 'chapter-install')
        self.assertContains(response, 'ANDROID-OVERVIEW.mp4')

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
