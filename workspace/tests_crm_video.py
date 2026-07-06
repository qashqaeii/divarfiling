"""Tests for CRM tutorial video helper."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from workspace.services.crm_video import (
    CRM_VIDEO_MEDIA,
    get_crm_video_context,
    get_crm_video_url,
)

User = get_user_model()


@override_settings(MEDIA_ROOT='/tmp/test-media', MEDIA_URL='/media/')
class CRMVideoHelperTests(SimpleTestCase):
    def test_missing_file_returns_unavailable(self):
        with patch('workspace.services.crm_video.crm_video_exists', return_value=False):
            ctx = get_crm_video_context()
        self.assertFalse(ctx['available'])
        self.assertEqual(ctx['mode'], 'none')
        self.assertIn('title', ctx)

    def test_existing_file_returns_media_url(self):
        with patch('workspace.services.crm_video.crm_video_exists', return_value=True):
            url = get_crm_video_url()
            ctx = get_crm_video_context()
        self.assertEqual(url, f'/media/{CRM_VIDEO_MEDIA}')
        self.assertTrue(ctx['available'])
        self.assertEqual(ctx['src'], url)
        self.assertEqual(ctx['mode'], 'file')


class CRMDashboardVideoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='crmvid', password='pass1234', phone='09129999999',
        )

    def test_dashboard_shows_video_band_when_available(self):
        self.client.login(username='crmvid', password='pass1234')
        with patch('workspace.services.crm_video.crm_video_exists', return_value=True):
            resp = self.client.get(reverse('workspace:crm_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="crm-video"')
        self.assertContains(resp, 'CRM.mp4')
