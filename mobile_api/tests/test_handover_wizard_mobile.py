"""Mobile API — Handover wizard."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from contracts.constants import CONTRACT_TYPE_LEASE
from contracts.services.handover import create_handover, save_handover_step
from contracts.services.lifecycle import create_contract, save_wizard_step
from contracts.tests.helpers import grant_bot_license

User = get_user_model()


class HandoverWizardMobileApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09124445566', phone='09124445566', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        grant_bot_license(self.user)

    def _finalized_lease(self):
        contract = create_contract(self.user, CONTRACT_TYPE_LEASE)
        save_wizard_step(
            contract,
            'parties',
            [
                {'role': 'landlord', 'first_name': 'م', 'last_name': 'الک', 'mobile': '09121111111'},
                {'role': 'tenant', 'first_name': 'م', 'last_name': 'ستاجر', 'mobile': '09122222222'},
            ],
            user=self.user,
        )
        contract.status = 'finalized'
        contract.save(update_fields=['status'])
        return contract

    def test_create_handover_and_get_wizard(self):
        contract = self._finalized_lease()
        resp = self.client.post(f'/api/mobile/v1/contracts/{contract.pk}/handover')
        self.assertEqual(resp.status_code, 201)
        handover_id = resp.json()['data']['handover_id']
        get_resp = self.client.get(
            f'/api/mobile/v1/contracts/{contract.pk}/handover/{handover_id}/wizard?step=keys',
        )
        self.assertEqual(get_resp.status_code, 200)
        data = get_resp.json()['data']
        wizard = data['wizard']
        self.assertEqual(wizard['handover_step'], 'keys')
        self.assertTrue(data['can_edit'])
        self.assertIn('key_rows', wizard)
        review = wizard.get('review')
        self.assertIsInstance(review, dict)
        self.assertIn('issues', review)

    def test_duplicate_active_handover_rejected(self):
        contract = self._finalized_lease()
        self.client.post(f'/api/mobile/v1/contracts/{contract.pk}/handover')
        resp = self.client.post(f'/api/mobile/v1/contracts/{contract.pk}/handover')
        self.assertEqual(resp.status_code, 400)

    def test_patch_keys_meters_conditions_equipment(self):
        contract = self._finalized_lease()
        handover = create_handover(self.user, contract.pk)
        base = f'/api/mobile/v1/contracts/{contract.pk}/handover/{handover.pk}/wizard'
        keys_resp = self.client.patch(
            base,
            {'step': 'keys', 'data': {'keys': [{'type': 'کلید واحد', 'count': 2, 'notes': ''}]}},
            format='json',
        )
        self.assertEqual(keys_resp.status_code, 200)
        handover.refresh_from_db()
        self.assertEqual(handover.snapshot_json['keys'][0]['count'], 2)

        meters_resp = self.client.patch(
            base,
            {
                'step': 'meters',
                'data': {
                    'meters': [{
                        'utility': 'electricity',
                        'meter_number': '123',
                        'reading': '456',
                        'notes': '',
                    }],
                },
            },
            format='json',
        )
        self.assertEqual(meters_resp.status_code, 200)

        cond_resp = self.client.patch(
            base,
            {
                'step': 'conditions',
                'data': {'conditions': [{'item': 'دیوارها', 'status': 'ok', 'note': 'سالم'}]},
            },
            format='json',
        )
        self.assertEqual(cond_resp.status_code, 200)

        eq_resp = self.client.patch(
            base,
            {'step': 'equipment', 'data': {'equipment': [{'name': 'پکیج', 'count': '1', 'status': 'ok'}]}},
            format='json',
        )
        self.assertEqual(eq_resp.status_code, 200)
        handover.refresh_from_db()
        self.assertEqual(handover.snapshot_json['equipment'][0]['name'], 'پکیج')

    def test_patch_locked_handover_rejected(self):
        contract = self._finalized_lease()
        handover = create_handover(self.user, contract.pk)
        handover.status = 'finalized'
        handover.is_locked = True
        handover.save(update_fields=['status', 'is_locked'])
        resp = self.client.patch(
            f'/api/mobile/v1/contracts/{contract.pk}/handover/{handover.pk}/wizard',
            {'step': 'basic', 'data': {'notes': 'x'}},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_handover_pdf_endpoint(self):
        contract = self._finalized_lease()
        handover = create_handover(self.user, contract.pk)
        handover.refresh_from_db()
        parties = list(handover.snapshot_json.get('parties') or [])
        if len(parties) < 2:
            contract.refresh_from_db()
            parties = list((contract.wizard_data or {}).get('parties') or [])
        save_handover_step(
            handover,
            'basic',
            {
                'handover_date': '1403/06/01',
                'handover_time': '10:00',
                'delivered_by': parties[0],
                'received_by': parties[1],
                'notes': '',
            },
            user=self.user,
        )
        resp = self.client.get(
            f'/api/mobile/v1/contracts/{contract.pk}/handover/{handover.pk}/pdf?inline=1',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
