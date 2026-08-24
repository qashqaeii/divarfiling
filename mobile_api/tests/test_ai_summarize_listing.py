"""Regression tests for AI summarize-listing."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from licenses.models import License, LicenseActivation
from shop.models import LicensePlan, Order, Product
from workspace.models import Dataset, Listing

User = get_user_model()


class AISummarizeListingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09121112233',
            phone='09121112233',
            password='testpass123',
        )
        product = Product.objects.create(
            title='ربات',
            slug='bot-ai-test',
            description='test',
            is_active=True,
        )
        plan = LicensePlan.objects.create(
            product=product,
            name='Pro',
            plan_type='yearly',
            price=1000000,
            duration_days=365,
            max_activations=1,
        )
        order = Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=1000000,
            status='paid',
        )
        self.license = License.objects.create(
            order=order,
            license_key='AI-TEST-KEY1',
            plan=plan,
            status='active',
            max_activations=1,
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        LicenseActivation.objects.create(
            license=self.license,
            hardware_fingerprint='a' * 64,
            is_active=True,
        )
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='تست',
            original_filename='test.json',
            file_format='json',
            row_count=1,
            column_count=1,
            columns=['token'],
            is_active=True,
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='tok-ai-1',
            title='آپارتمان تست',
            price=5_000_000_000,
            area=100,
        )
        self.client = APIClient()
        login = self.client.post('/api/mobile/v1/auth/login', {
            'username': '09121112233',
            'password': 'testpass123',
        }, format='json')
        token = login.data['data']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    @patch('ai_workspace.constants.is_ai_enabled', return_value=False)
    def test_summarize_listing_does_not_use_updated_at(self, _mock_ai):
        """Listing has no updated_at — endpoint must not 500."""
        resp = self.client.post(
            '/api/mobile/v1/ai/summarize-listing',
            {'listing_token': 'tok-ai-1'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data.get('ok'))
        self.assertIn('text', resp.data.get('data') or {})

    @patch('ai_workspace.constants.is_ai_enabled', return_value=False)
    def test_summarize_listing_picks_latest_created(self, _mock_ai):
        Listing.objects.filter(pk=self.listing.pk).update(
            created_at=timezone.now() - timezone.timedelta(days=2),
        )
        dataset2 = Dataset.objects.create(
            user=self.user,
            name='تست ۲',
            original_filename='test2.json',
            file_format='json',
            row_count=1,
            column_count=1,
            columns=['token'],
            is_active=True,
        )
        newer = Listing.objects.create(
            dataset=dataset2,
            token='tok-ai-1',
            title='جدید',
            price=2,
            area=60,
        )
        resp = self.client.post(
            '/api/mobile/v1/ai/summarize-listing',
            {'listing_token': 'tok-ai-1'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        latest = Listing.objects.filter(token='tok-ai-1', dataset__user=self.user).order_by('-created_at', '-id').first()
        self.assertEqual(latest.pk, newer.pk)
