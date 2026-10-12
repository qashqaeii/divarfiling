"""Mobile API — Contract lifecycle actions (prepare_send, cancel, copy)."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from contracts.constants import CONTRACT_STATUS_DRAFT, CONTRACT_STATUS_READY, CONTRACT_TYPE_LEASE
from contracts.services.lifecycle import create_contract, save_wizard_step
from contracts.tests.helpers import grant_bot_license
from contracts.tests.test_phase2 import _lease_wizard_data

User = get_user_model()


class ContractActionsMobileApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09124445566', phone='09124445566', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        grant_bot_license(self.user)

    def _url(self, contract_id: int) -> str:
        return f'/api/mobile/v1/contracts/{contract_id}/actions'

    def _fill_lease_wizard(self, contract):
        wd = _lease_wizard_data()
        for step in ('parties', 'property', 'financial', 'witnesses'):
            save_wizard_step(contract, step, wd[step], user=self.user)
        save_wizard_step(contract, 'clauses', wd['selected_clauses'], user=self.user)

    def test_invalid_action(self):
        contract = create_contract(self.user, CONTRACT_TYPE_LEASE)
        resp = self.client.post(self._url(contract.pk), {'action': 'nope'}, format='json')
        self.assertEqual(resp.status_code, 400)

    @patch('contracts.services.invitations.send_simple_sms')
    def test_prepare_send_success(self, mock_sms):
        mock_sms.return_value = None
        contract = create_contract(self.user, CONTRACT_TYPE_LEASE)
        self._fill_lease_wizard(contract)
        resp = self.client.post(self._url(contract.pk), {'action': 'prepare_send'}, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn(data['status'], (CONTRACT_STATUS_READY, 'sent'))
        contract.refresh_from_db()
        self.assertEqual(contract.status, data['status'])
        self.assertTrue(contract.current_version.is_locked)

    def test_prepare_send_incomplete_draft(self):
        contract = create_contract(self.user, CONTRACT_TYPE_LEASE)
        resp = self.client.post(self._url(contract.pk), {'action': 'prepare_send'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_copy_creates_new_draft(self):
        contract = create_contract(self.user, CONTRACT_TYPE_LEASE)
        self._fill_lease_wizard(contract)
        resp = self.client.post(self._url(contract.pk), {'action': 'copy'}, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertNotEqual(data['contract_id'], contract.pk)
        self.assertEqual(data['status'], CONTRACT_STATUS_DRAFT)

    @patch('contracts.services.invitations.send_simple_sms')
    def test_resend_invitation(self, mock_sms):
        mock_sms.return_value = None
        contract = create_contract(self.user, CONTRACT_TYPE_LEASE)
        self._fill_lease_wizard(contract)
        prep = self.client.post(self._url(contract.pk), {'action': 'prepare_send'}, format='json')
        self.assertEqual(prep.status_code, 200)
        contract.refresh_from_db()
        inv = contract.invitations.filter(is_revoked=False).first()
        self.assertIsNotNone(inv)
        resp = self.client.post(
            self._url(contract.pk),
            {'action': 'resend_invitation', 'invitation_id': inv.pk},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

    def test_cancel_draft(self):
        contract = create_contract(self.user, CONTRACT_TYPE_LEASE)
        resp = self.client.post(
            self._url(contract.pk),
            {'action': 'cancel', 'reason': 'انصراف تست'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        contract.refresh_from_db()
        self.assertEqual(contract.status, 'cancelled')
