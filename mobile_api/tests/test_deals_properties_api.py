"""تست API معاملات و املاک موبایل."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import CRMDeal, CRMProperty, Customer

User = get_user_model()


class DealsPropertiesApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09123334444', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.customer = Customer.objects.create(
            user=self.user,
            name='مشتری تست',
            phone='09123334444',
            status='جدید',
        )
        self.property = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان ونک',
            city='تهران',
            district='ونک',
            sale_price=5_000_000_000,
        )

    def test_create_and_list_deal(self):
        resp = self.client.post(
            '/api/mobile/v1/crm/deals',
            {
                'customer_id': self.customer.pk,
                'property_id': self.property.pk,
                'title': 'معامله تست',
                'stage': 'سرنخ',
                'amount': 5_000_000_000,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json()['ok'])
        self.assertEqual(CRMDeal.objects.filter(user=self.user).count(), 1)

        list_resp = self.client.get('/api/mobile/v1/crm/deals')
        self.assertEqual(list_resp.status_code, 200)
        self.assertGreaterEqual(len(list_resp.json()['data']), 1)

    def test_deal_stage_update(self):
        deal = CRMDeal.objects.create(
            user=self.user,
            customer=self.customer,
            title='معامله',
            stage='سرنخ',
        )
        resp = self.client.post(
            f'/api/mobile/v1/crm/deals/{deal.pk}/stage',
            {'stage': 'مذاکره'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        deal.refresh_from_db()
        self.assertEqual(deal.stage, 'مذاکره')

    def test_create_and_list_property(self):
        resp = self.client.post(
            '/api/mobile/v1/crm/properties',
            {
                'title': 'ملک جدید',
                'city': 'تهران',
                'deal_mode': 'فروش',
                'sale_price': 3_000_000_000,
                'contact_id': self.customer.pk,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(CRMProperty.objects.filter(user=self.user).count(), 2)

        list_resp = self.client.get('/api/mobile/v1/crm/properties?q=ملک')
        self.assertEqual(list_resp.status_code, 200)

    def test_property_status_update(self):
        resp = self.client.post(
            f'/api/mobile/v1/crm/properties/{self.property.pk}/status',
            {'transaction_status': 'در مذاکره'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.property.refresh_from_db()
        self.assertEqual(self.property.transaction_status, 'در مذاکره')

    def test_deals_pipeline(self):
        CRMDeal.objects.create(user=self.user, customer=self.customer, title='د', stage='سرنخ')
        resp = self.client.get('/api/mobile/v1/crm/deals/pipeline')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('columns', data)
        self.assertIn('stages', data)
