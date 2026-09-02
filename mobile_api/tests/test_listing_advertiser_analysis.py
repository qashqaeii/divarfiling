"""تست API موبایل — تحلیل هوشمند آگهی‌دهنده."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from workspace.models import AdvertiserSignalFeedback, Dataset, Listing

User = get_user_model()


class MobileListingAdvertiserAnalysisTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09124445566',
            phone='09124445566',
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
            token='mobadv1',
            title='آپارتمان تست',
            description='همکاران عزیز لطفاً تماس نگیرید',
            business_type='personal',
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True)
    def test_listing_detail_includes_advertiser_analysis(self, _mock):
        resp = self.client.get(f'/api/mobile/v1/filing/listings/{self.listing.token}')
        self.assertEqual(resp.status_code, 200)
        analysis = resp.json()['data']['advertiser_analysis']
        self.assertEqual(analysis['classification'], 'disguised_consultant')
        self.assertIn('badge_label', analysis)
        self.assertIn('summary', analysis)
        self.assertNotIn('score', analysis)
        self.assertNotIn('primary_reason', analysis)
        self.assertEqual(analysis['feedback']['submitted'], None)

    @patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True)
    def test_advertiser_feedback_correct(self, _mock):
        url = f'/api/mobile/v1/filing/listings/{self.listing.token}/advertiser-feedback'
        resp = self.client.post(url, {'feedback': 'correct'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['feedback'], 'correct')
        self.assertEqual(
            AdvertiserSignalFeedback.objects.filter(user=self.user, listing=self.listing).count(),
            1,
        )

    @patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True)
    def test_advertiser_feedback_incorrect_requires_correction(self, _mock):
        url = f'/api/mobile/v1/filing/listings/{self.listing.token}/advertiser-feedback'
        resp = self.client.post(url, {'feedback': 'incorrect'}, format='json')
        self.assertEqual(resp.status_code, 400)

    @patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True)
    def test_advertiser_feedback_incorrect_with_correction(self, _mock):
        url = f'/api/mobile/v1/filing/listings/{self.listing.token}/advertiser-feedback'
        resp = self.client.post(
            url,
            {'feedback': 'incorrect', 'user_correction': 'genuine_personal'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        obj = AdvertiserSignalFeedback.objects.get(user=self.user, listing=self.listing)
        self.assertEqual(obj.feedback, 'incorrect')
        self.assertEqual(obj.user_correction, 'genuine_personal')
