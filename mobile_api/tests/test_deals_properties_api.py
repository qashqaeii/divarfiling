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
        self.assertIn('definitions', data)

    def test_deal_stages_get_and_save(self):
        resp = self.client.get('/api/mobile/v1/crm/deals/stages')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('stages', data)
        self.assertIn('definitions', data)
        defs = data['definitions']
        defs[0]['name'] = 'فرصت'
        save_resp = self.client.post(
            '/api/mobile/v1/crm/deals/stages',
            {'definitions': defs},
            format='json',
        )
        self.assertEqual(save_resp.status_code, 200)
        self.assertTrue(save_resp.json()['ok'])
        names = save_resp.json()['data']['stages']
        self.assertEqual(names[0], 'فرصت')

    def test_deal_finance_dashboard_and_update(self):
        create_resp = self.client.post(
            '/api/mobile/v1/crm/deals',
            {
                'customer_id': self.customer.pk,
                'property_id': self.property.pk,
                'title': 'معامله مالی',
                'stage': 'بسته‌شده',
                'amount': 2_000_000_000,
            },
            format='json',
        )
        self.assertEqual(create_resp.status_code, 201)
        deal_id = create_resp.json()['data']['id']
        self.assertIn('advisor_commission', create_resp.json()['data'])

        patch_resp = self.client.patch(
            f'/api/mobile/v1/crm/deals/{deal_id}/finance',
            {
                'buyer_commission_rate': 0.5,
                'seller_commission_rate': 0.5,
                'advisor_share_percent': 80,
                'agency_share_percent': 20,
                'payout_status': 'paid',
            },
            format='json',
        )
        self.assertEqual(patch_resp.status_code, 200)
        data = patch_resp.json()['data']
        self.assertEqual(data['advisor_share_percent'], 80)
        self.assertEqual(data['payout_status'], 'paid')

        dash = self.client.get('/api/mobile/v1/crm/deals/finance', {'period': 'all'})
        self.assertEqual(dash.status_code, 200)
        kpis = dash.json()['data']['kpis']
        self.assertGreaterEqual(kpis['closed_count'], 1)

        settings_resp = self.client.post(
            '/api/mobile/v1/crm/deals/finance/settings',
            {'advisor_share_percent': 75, 'agency_share_percent': 25},
            format='json',
        )
        self.assertEqual(settings_resp.status_code, 200)
        self.assertEqual(settings_resp.json()['data']['defaults']['advisor_share_percent'], 75)
