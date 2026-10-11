"""Mobile API — Contract wizard GET/PATCH."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from contracts.constants import CONTRACT_TYPE_JV, CONTRACT_TYPE_LEASE, CONTRACT_TYPE_SALE
from contracts.services.lifecycle import create_contract, save_wizard_step
from contracts.tests.helpers import grant_bot_license

User = get_user_model()


class ContractWizardMobileApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09124445566', phone='09124445566', password='test')
        self.other = User.objects.create_user(username='09127778899', phone='09127778899', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        grant_bot_license(self.user)

    def _create(self, ctype: str):
        return create_contract(self.user, ctype)

    def test_get_wizard_requires_license(self):
        unlicensed = User.objects.create_user(username='09125556677', phone='09125556677', password='test')
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(unlicensed).access_token}')
        contract = self._create(CONTRACT_TYPE_SALE)
        resp = client.get(f'/api/mobile/v1/contracts/{contract.pk}/wizard')
        self.assertEqual(resp.status_code, 403)

    def test_get_wizard_sale_steps(self):
        contract = self._create(CONTRACT_TYPE_SALE)
        resp = self.client.get(f'/api/mobile/v1/contracts/{contract.pk}/wizard')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        keys = [s['key'] for s in data['display_steps']]
        self.assertEqual(keys, ['parties', 'property', 'financial', 'clauses', 'review'])
        self.assertTrue(data['can_edit'])

    def test_patch_parties_persists(self):
        contract = self._create(CONTRACT_TYPE_SALE)
        parties = [{
            'role': 'seller',
            'person_type': 'natural',
            'first_name': 'علی',
            'last_name': 'رضایی',
            'mobile': '09121111111',
        }, {
            'role': 'buyer',
            'person_type': 'natural',
            'first_name': ' Sara ',
            'last_name': 'Test',
            'mobile': '09122222222',
        }]
        resp = self.client.patch(
            f'/api/mobile/v1/contracts/{contract.pk}/wizard',
            {'step': 'parties', 'data': parties},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        contract.refresh_from_db()
        self.assertEqual(len(contract.wizard_data.get('parties') or []), 2)
        self.assertEqual(contract.wizard_data['parties'][0]['first_name'], 'علی')

    def test_patch_invalid_step_for_jv(self):
        contract = self._create(CONTRACT_TYPE_JV)
        resp = self.client.patch(
            f'/api/mobile/v1/contracts/{contract.pk}/wizard',
            {'step': 'witnesses', 'data': []},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_patch_lease_financial(self):
        contract = self._create(CONTRACT_TYPE_LEASE)
        fin = {
            'lease_start': '1403/01/01',
            'lease_end': '1404/01/01',
            'deposit': '500000000',
            'monthly_rent': '25000000',
        }
        resp = self.client.patch(
            f'/api/mobile/v1/contracts/{contract.pk}/wizard',
            {'step': 'financial', 'data': fin},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        contract.refresh_from_db()
        saved = contract.wizard_data.get('financial') or {}
        self.assertEqual(saved.get('monthly_rent'), 25000000)

    def test_patch_preserves_other_steps(self):
        contract = self._create(CONTRACT_TYPE_SALE)
        save_wizard_step(contract, 'property', {'city': 'تهران', 'address': 'خیابان اول'}, user=self.user)
        contract.refresh_from_db()
        updated_at = contract.updated_at.isoformat()
        resp = self.client.patch(
            f'/api/mobile/v1/contracts/{contract.pk}/wizard',
            {
                'step': 'parties',
                'data': [
                    {'role': 'seller', 'first_name': 'a', 'last_name': 'b', 'mobile': '09120000000'},
                    {'role': 'buyer', 'first_name': 'c', 'last_name': 'd', 'mobile': '09120000001'},
                ],
                'if_match_updated_at': updated_at,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        contract.refresh_from_db()
        self.assertEqual((contract.wizard_data.get('property') or {}).get('city'), 'تهران')

    def test_patch_forbidden_without_access(self):
        contract = self._create(CONTRACT_TYPE_SALE)
        other_client = APIClient()
        grant_bot_license(self.other)
        other_client = APIClient()
        other_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.other).access_token}',
        )
        resp = other_client.patch(
            f'/api/mobile/v1/contracts/{contract.pk}/wizard',
            {'step': 'parties', 'data': []},
            format='json',
        )
        self.assertIn(resp.status_code, (403, 404, 400))

    def test_patch_locked_finalized_contract(self):
        contract = self._create(CONTRACT_TYPE_SALE)
        contract.status = 'finalized'
        contract.save(update_fields=['status'])
        resp = self.client.patch(
            f'/api/mobile/v1/contracts/{contract.pk}/wizard',
            {
                'step': 'parties',
                'data': [
                    {'role': 'seller', 'first_name': 'a', 'last_name': 'b', 'mobile': '09120000000'},
                    {'role': 'buyer', 'first_name': 'c', 'last_name': 'd', 'mobile': '09120000001'},
                ],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('قابل ویرایش', resp.json()['error'])

    def test_patch_invalid_parties_payload(self):
        contract = self._create(CONTRACT_TYPE_SALE)
        resp = self.client.patch(
            f'/api/mobile/v1/contracts/{contract.pk}/wizard',
            {'step': 'parties', 'data': {'not': 'a list'}},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
