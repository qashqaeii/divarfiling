"""تست API اشتراک عمومی فایل شخصی."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from workspace.models import CRMProperty

User = get_user_model()


class PropertyPublicShareApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09121112233',
            phone='09121112233',
            password='testpass123',
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان تست',
            deal_mode='فروش',
            property_type='آپارتمان',
            city='تهران',
            sale_price=3_000_000_000,
            area=80,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @patch('workspace.services.access.has_active_bot_license', return_value=True)
    def test_property_detail_includes_public_share(self, _mock):
        url = f'/api/mobile/v1/crm/properties/{self.prop.pk}'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('public_share', data)
        self.assertTrue(data['public_share']['share_url'])
        self.assertIn('/p/f/', data['public_share']['share_url'])

    @patch('workspace.services.access.has_active_bot_license', return_value=True)
    def test_public_share_patch(self, _mock):
        url = f'/api/mobile/v1/crm/properties/{self.prop.pk}/public-share'
        resp = self.client.patch(url, {
            'welcome_message': 'سلام',
            'show_full_address': True,
            'is_active': True,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['welcome_message'], 'سلام')
        self.assertTrue(data['show_full_address'])
