"""Epic 01 — Deal Journey, contracts bridge, duplicate, commission."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from contracts.tests.helpers import grant_bot_license
from contracts.services.lifecycle import create_contract
from contracts.constants import CONTRACT_TYPE_SALE
from workspace.models import CRMDeal, CRMProperty, Customer

User = get_user_model()


class DealJourneyEpicApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09121112233', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.customer = Customer.objects.create(
            user=self.user,
            name='رضا محمدی',
            phone='09121112233',
            status='جدید',
        )
        self.property = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان سعادت‌آباد',
            city='تهران',
            sale_price=4_800_000_000,
        )
        self.deal = CRMDeal.objects.create(
            user=self.user,
            customer=self.customer,
            property=self.property,
            title='فروش آپارتمان',
            stage='مذاکره',
            value=4_800_000_000,
            commission_amount=48_000_000,
        )

    def test_journey_without_contract(self):
        resp = self.client.get(f'/api/mobile/v1/crm/deals/{self.deal.pk}/journey')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('primary', data)
        self.assertIn('headline', data)

    def test_contracts_empty(self):
        resp = self.client.get(f'/api/mobile/v1/crm/deals/{self.deal.pk}/contracts')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()['data']
        self.assertEqual(body['count'], 0)
        self.assertTrue(body['locked'])  # بدون لایسنس

    def test_create_contract_and_list(self):
        grant_bot_license(self.user)
        create = self.client.post(
            f'/api/mobile/v1/crm/deals/{self.deal.pk}/contracts',
            {'contract_type': 'sale'},
            format='json',
        )
        self.assertEqual(create.status_code, 201)
        listed = self.client.get(f'/api/mobile/v1/crm/deals/{self.deal.pk}/contracts')
        self.assertEqual(listed.json()['data']['count'], 1)

    def test_duplicate_deal_check(self):
        resp = self.client.get(
            '/api/mobile/v1/crm/deals/duplicate-check',
            {'property_id': self.property.pk, 'customer_id': self.customer.pk},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['data']['duplicate'])

    def test_duplicate_deal_none(self):
        other = Customer.objects.create(
            user=self.user,
            name='دیگری',
            phone='09129998877',
            status='جدید',
        )
        resp = self.client.get(
            '/api/mobile/v1/crm/deals/duplicate-check',
            {'property_id': self.property.pk, 'customer_id': other.pk},
        )
        self.assertFalse(resp.json()['data']['duplicate'])

    def test_force_create_allowed(self):
        resp = self.client.post(
            '/api/mobile/v1/crm/deals',
            {
                'customer_id': self.customer.pk,
                'property_id': self.property.pk,
                'title': 'معامله دوم',
                'stage': 'سرنخ',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)

    def test_commission_split_invalid(self):
        resp = self.client.post(
            f'/api/mobile/v1/crm/deals/{self.deal.pk}/commission-splits',
            {'splits': [{'member_id': 1, 'percent': 50}]},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_workspace_bridge_path_validation(self):
        bad = self.client.post(
            '/api/mobile/v1/workspace/bridge',
            {'path': 'https://evil.com/phish'},
            format='json',
        )
        self.assertEqual(bad.status_code, 400)
        ok = self.client.post(
            '/api/mobile/v1/workspace/bridge',
            {'path': f'/workspace/crm/deals/{self.deal.pk}/'},
            format='json',
        )
        self.assertEqual(ok.status_code, 200)
        self.assertIn('bridge_url', ok.json()['data'])

    def test_workspace_bridge_contact_import_paths(self):
        for path in (
            '/workspace/crm/contacts/import/',
            '/workspace/crm/contacts/import/template/',
            '/workspace/crm/team/',
        ):
            with self.subTest(path=path):
                resp = self.client.post(
                    '/api/mobile/v1/workspace/bridge',
                    {'path': path},
                    format='json',
                )
                self.assertEqual(resp.status_code, 200, resp.content)
                self.assertIn('bridge_url', resp.json()['data'])

    def test_contract_metadata_patch(self):
        resp = self.client.patch(
            f'/api/mobile/v1/crm/deals/{self.deal.pk}',
            {
                'contract_number': 'C-100',
                'contract_amount': 50_000_000,
                'contract_date': '1404-01-01',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.contract_number, 'C-100')
