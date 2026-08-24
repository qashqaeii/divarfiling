"""تست API موبایل — اشتراک عمومی آگهی."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from workspace.models import Dataset, Listing

User = get_user_model()


class MobileListingPublicShareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09123334455',
            phone='09123334455',
            password='testpass123',
        )
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='تست',
            original_filename='test.xlsx',
            file_format='xlsx',
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='mobshare1',
            title='آپارتمان تست',
            price=3_000_000_000,
            area=80,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True)
    def test_listing_detail_does_not_auto_create_public_share(self, _mock):
        resp = self.client.get(f'/api/mobile/v1/filing/listings/{self.listing.token}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('public_share', data)
        self.assertIsNone(data['public_share'])

    @patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True)
    def test_public_share_patch(self, _mock):
        url = f'/api/mobile/v1/filing/listings/{self.listing.token}/public-share'
        resp = self.client.patch(url, {
            'welcome_message': 'سلام، برای بازدید تماس بگیرید',
            'show_divar_link': True,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        share = resp.json()['data']
        self.assertEqual(share['welcome_message'], 'سلام، برای بازدید تماس بگیرید')
        self.assertTrue(share['show_divar_link'])

    @patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True)
    def test_listing_patch_includes_public_share_after_create(self, _mock):
        create = self.client.patch(
            f'/api/mobile/v1/filing/listings/{self.listing.token}/public-share',
            {'welcome_message': 'سلام'},
            format='json',
            HTTP_HOST='testserver',
        )
        self.assertEqual(create.status_code, 200)

        resp = self.client.patch(
            f'/api/mobile/v1/filing/listings/{self.listing.token}',
            {'title': 'آپارتمان به‌روز'},
            format='json',
            HTTP_HOST='testserver',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('public_share', data)
        self.assertIsNotNone(data['public_share'])
        self.assertTrue(data['public_share']['share_url'])
        self.assertIn('/p/', data['public_share']['share_url'])
