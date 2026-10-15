"""صفحه ارتقا — بلوک ویدیوی دمو استخراج."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from workspace.services.upgrade_extraction_video import (
    EXTRACTION_DEMO_VIDEO_SLUG,
    get_upgrade_extraction_demo,
    should_show_extraction_demo,
)

User = get_user_model()


class UpgradeExtractionDemoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='upg_demo_user', password='x', phone='09121112233',
        )

    def test_should_show_for_datasets(self):
        self.assertTrue(should_show_extraction_demo('datasets'))
        self.assertFalse(should_show_extraction_demo('contracts'))

    def test_upgrade_page_shows_demo_block_when_video_exists(self):
        from workspace.academy.models import AcademyVideo

        if not AcademyVideo.objects.filter(slug=EXTRACTION_DEMO_VIDEO_SLUG).exists():
            self.skipTest('academy extraction video not seeded in test DB')

        self.client.login(username='upg_demo_user', password='x')
        resp = self.client.get(reverse('workspace:upgrade'), {'feature': 'datasets'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'upg-demo')
        self.assertContains(resp, 'قبل از خرید')

    def test_get_upgrade_extraction_demo_none_for_contracts(self):
        demo = get_upgrade_extraction_demo(self.user, 'contracts')
        self.assertIsNone(demo)
