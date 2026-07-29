"""Tests for filing tutorial video helper."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from workspace.services.filing_video import (
    FILING_VIDEO_MEDIA,
    get_filing_video_context,
    get_filing_video_url,
)

User = get_user_model()


@override_settings(MEDIA_ROOT='/tmp/test-media', MEDIA_URL='/media/')
class FilingVideoHelperTests(SimpleTestCase):
    def test_missing_file_returns_unavailable(self):
        with patch('workspace.services.filing_video.filing_video_exists', return_value=False):
            ctx = get_filing_video_context()
        self.assertFalse(ctx['available'])
        self.assertEqual(ctx['mode'], 'none')
        self.assertIn('title', ctx)

    def test_existing_file_returns_media_url(self):
        with patch('workspace.services.filing_video.filing_video_exists', return_value=True):
            url = get_filing_video_url()
            ctx = get_filing_video_context()
        self.assertEqual(url, f'/media/{FILING_VIDEO_MEDIA}')
        self.assertTrue(ctx['available'])
        self.assertEqual(ctx['src'], url)
        self.assertEqual(ctx['mode'], 'file')


class DatasetListFilingVideoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='viduser', password='pass1234', phone='09128888888',
        )
        self.product = Product.objects.create(
            title='ربات', slug='bot-vid-test', description='t', is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product, name='ماهانه', plan_type='monthly',
            price=100000, duration_days=30, is_active=True,
        )
        order = Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=100000, status='paid',
        )
        License.objects.create(
            order=order, plan=self.plan, license_key='VID-1234-5678-9ABC',
            status='active', max_activations=1,
        )

    def test_dataset_list_hides_video_band(self):
        self.client.login(username='viduser', password='pass1234')
        with patch('workspace.services.filing_video.filing_video_exists', return_value=True):
            resp = self.client.get(reverse('workspace:dataset_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'mk-filing-video-band')
        self.assertNotContains(resp, 'id="filing-video"')
