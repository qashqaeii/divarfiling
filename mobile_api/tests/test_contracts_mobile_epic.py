"""Epic 02 — Contracts Native Core mobile API."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from contracts.constants import CONTRACT_TYPE_SALE
from contracts.services.lifecycle import create_contract
from contracts.tests.helpers import grant_bot_license
from workspace.models import CRMDeal, CRMProperty, Customer

User = get_user_model()


class ContractsMobileEpicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09123334455', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.customer = Customer.objects.create(
            user=self.user,
            name='علی',
            phone='09123334455',
            status='جدید',
        )
        self.property = CRMProperty.objects.create(
            user=self.user,
            title='ویلا',
            city='تهران',
            sale_price=2_000_000_000,
        )
        self.deal = CRMDeal.objects.create(
            user=self.user,
            customer=self.customer,
            property=self.property,
            title='فروش ویلا',
            stage='مذاکره',
            value=2_000_000_000,
        )

    def test_list_license_denied(self):
        resp = self.client.get('/api/mobile/v1/contracts')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['code'], 'CONTRACTS_LICENSE_REQUIRED')

    def test_list_empty_with_license(self):
        grant_bot_license(self.user)
        resp = self.client.get('/api/mobile/v1/contracts')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()['data']
        self.assertEqual(body['stats']['all'], 0)
        self.assertEqual(body['items'], [])

    def test_create_standalone_and_detail(self):
        grant_bot_license(self.user)
        create = self.client.post(
            '/api/mobile/v1/contracts',
            {'contract_type': 'sale'},
            format='json',
        )
        self.assertEqual(create.status_code, 201)
        cid = create.json()['data']['id']
        detail = self.client.get(f'/api/mobile/v1/contracts/{cid}')
        self.assertEqual(detail.status_code, 200)
        self.assertIn('next_action', detail.json()['data'])
        self.assertIsNone(detail.json()['data']['deal_id'])

    def test_deal_linked_contract(self):
        grant_bot_license(self.user)
        contract = create_contract(self.user, CONTRACT_TYPE_SALE, deal_id=self.deal.pk)
        resp = self.client.get('/api/mobile/v1/contracts', {'deal_linked': 'true'})
        self.assertEqual(resp.status_code, 200)
        items = resp.json()['data']['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['deal_id'], self.deal.pk)

    def test_search_by_number(self):
        grant_bot_license(self.user)
        contract = create_contract(self.user, CONTRACT_TYPE_SALE, deal_id=self.deal.pk)
        resp = self.client.get('/api/mobile/v1/contracts', {'q': contract.internal_number[:6]})
        self.assertEqual(len(resp.json()['data']['items']), 1)

    def test_timeline(self):
        grant_bot_license(self.user)
        contract = create_contract(self.user, CONTRACT_TYPE_SALE)
        resp = self.client.get(f'/api/mobile/v1/contracts/{contract.pk}/timeline')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.json()['data']['items']) >= 1)

    def test_pdf_unauthorized_other_user(self):
        other = User.objects.create_user(username='other_contract_user', password='test', phone='09128889900')
        grant_bot_license(self.user)
        grant_bot_license(other)
        contract = create_contract(self.user, CONTRACT_TYPE_SALE)
        other_client = APIClient()
        other_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(other).access_token}',
        )
        resp = other_client.get(f'/api/mobile/v1/contracts/{contract.pk}/pdf')
        self.assertEqual(resp.status_code, 404)

    def test_pdf_with_access(self):
        grant_bot_license(self.user)
        contract = create_contract(self.user, CONTRACT_TYPE_SALE)
        resp = self.client.get(f'/api/mobile/v1/contracts/{contract.pk}/pdf')
        self.assertIn(resp.status_code, (200, 404))

    def test_handover_summary(self):
        grant_bot_license(self.user)
        contract = create_contract(self.user, CONTRACT_TYPE_SALE)
        resp = self.client.get(f'/api/mobile/v1/contracts/{contract.pk}/handover')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['data']['exists'])

    def test_needs_action_filter(self):
        grant_bot_license(self.user)
        draft = create_contract(self.user, CONTRACT_TYPE_SALE)
        sent = create_contract(self.user, CONTRACT_TYPE_SALE, deal_id=self.deal.pk)
        from contracts.models import Contract
        Contract.objects.filter(pk=sent.pk).update(status='sent')
        resp = self.client.get('/api/mobile/v1/contracts', {'needs_action': 'true'})
        self.assertEqual(resp.status_code, 200)
        ids = [i['id'] for i in resp.json()['data']['items']]
        self.assertIn(sent.pk, ids)
        self.assertNotIn(draft.pk, ids)

    def test_filter_type_and_deal_linked(self):
        grant_bot_license(self.user)
        create_contract(self.user, CONTRACT_TYPE_SALE, deal_id=self.deal.pk)
        resp = self.client.get(
            '/api/mobile/v1/contracts',
            {'type': 'sale', 'deal_linked': 'true'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']['items']), 1)

    def test_attachments_list(self):
        grant_bot_license(self.user)
        contract = create_contract(self.user, CONTRACT_TYPE_SALE)
        resp = self.client.get(f'/api/mobile/v1/contracts/{contract.pk}/attachments')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['items'], [])
