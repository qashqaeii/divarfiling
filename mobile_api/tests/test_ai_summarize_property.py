"""Regression tests for AI summarize-property."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from licenses.models import License, LicenseActivation
from shop.models import LicensePlan, Order, Product
from workspace.models import CRMProperty

User = get_user_model()


class AISummarizePropertyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09123334455',
            phone='09123334455',
            password='testpass123',
        )
        product = Product.objects.create(
            title='ربات',
            slug='bot-ai-prop-test',
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
            license_key='AI-PROP-KEY1',
            plan=plan,
            status='active',
            max_activations=1,
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        LicenseActivation.objects.create(
            license=self.license,
            hardware_fingerprint='b' * 64,
            is_active=True,
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان تست',
            deal_mode='فروش',
            city='تهران',
            area=100,
            sale_price=5_000_000_000,
        )
        self.client = APIClient()
        login = self.client.post('/api/mobile/v1/auth/login', {
            'username': '09123334455',
            'password': 'testpass123',
        }, format='json')
        token = login.data['data']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    @patch('ai_workspace.constants.is_ai_enabled', return_value=False)
    def test_summarize_property_fallback_includes_model_label(self, _mock_ai):
        resp = self.client.post(
            '/api/mobile/v1/ai/summarize-property',
            {'property_id': self.prop.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data.get('ok'))
        data = resp.data.get('data') or {}
        self.assertIn('text', data)
        self.assertTrue(data.get('is_fallback'))
        self.assertEqual(data.get('model_label'), 'مدل داخلی سیستم')

    @patch('ai_workspace.constants.is_ai_enabled', return_value=False)
    def test_summarize_property_not_found(self, _mock_ai):
        resp = self.client.post(
            '/api/mobile/v1/ai/summarize-property',
            {'property_id': 999999},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    @patch('ai_workspace.constants.is_ai_enabled', return_value=True)
    @patch('ai_workspace.services.property_summary.generate_summary_for_user')
    def test_summarize_property_ai_returns_model_label(self, mocked, _mock_ai):
        from ai_workspace.services.gateway import GatewayResult

        mocked.return_value = GatewayResult(
            feature='listing_summary',
            provider='gemini',
            model='gemini-2.0-flash',
            text='{}',
            data={'summary': 'خلاصه تست', 'highlights': [], 'negotiation_tip': ''},
            is_fallback=False,
            from_cache=False,
            latency_ms=1,
            input_tokens=0,
            output_tokens=0,
            status='ok',
        )
        resp = self.client.post(
            '/api/mobile/v1/ai/summarize-property',
            {'property_id': self.prop.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.data.get('data') or {}
        self.assertEqual(data.get('text'), 'خلاصه تست')
        self.assertEqual(data.get('model'), 'gemini-2.0-flash')
        self.assertEqual(data.get('model_label'), 'gemini-2.0-flash')

    @patch('ai_workspace.constants.is_ai_enabled', return_value=True)
    def test_summarize_property_insufficient_context_skipped(self, _mock_ai):
        sparse = CRMProperty.objects.create(
            user=self.user,
            title='فقط عنوان',
            deal_mode='فروش',
        )
        resp = self.client.post(
            '/api/mobile/v1/ai/summarize-property',
            {'property_id': sparse.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.data.get('data') or {}
        self.assertTrue(data.get('skipped'))
        self.assertEqual(data.get('skip_reason'), 'insufficient_context')
        self.assertIn('اطلاعات بیشتری', data.get('message', ''))
        self.assertEqual(data.get('text'), '')
