"""Agency closure — invite, settings, bulk moderation, activity filters."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from contracts.services.tokens import generate_bearer_token
from workspace.models import AgencyInvitation, AgencySpaceItem
from workspace.services.agency_invitations import accept_agency_invitation
from workspace.services.agency_space_moderation import hide_space_item_public
from workspace.services.agency_space_publish import publish_property
from workspace.services.crm_agency import create_agency
from workspace.tests.agency_test_utils import ensure_agency_subscription
from workspace.models import CRMProperty

User = get_user_model()


class AgencyClosureMobileTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='09124001101', password='x')
        self.owner.phone = '09124001101'
        self.owner.save(update_fields=['phone'])
        self.advisor = User.objects.create_user(username='09124001102', password='x')
        self.advisor.phone = '09124001102'
        self.advisor.save(update_fields=['phone'])
        self.agency = create_agency(self.owner, 'Closure Agency')
        ensure_agency_subscription(self.owner, self.agency)
        from workspace.models import CRMAgencyMember

        self.member = CRMAgencyMember.objects.create(
            agency=self.agency,
            user=self.advisor,
            role='advisor',
            is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        self.owner_client = APIClient()
        self.owner_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.owner).access_token}',
        )
        self.advisor_client = APIClient()
        self.advisor_client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(self.advisor).access_token}',
        )

    def _invite_with_token(self, phone: str) -> tuple[str, AgencyInvitation]:
        raw, th = generate_bearer_token()
        inv = AgencyInvitation.objects.create(
            agency=self.agency,
            inviter=self.owner,
            phone=phone,
            role='advisor',
            token_hash=th,
            expires_at=timezone.now() + timedelta(days=7),
        )
        return raw, inv

    def test_invite_preview_and_accept(self):
        raw, _inv = self._invite_with_token('09124001102')
        preview = self.advisor_client.get(
            '/api/mobile/v1/agency/invite/preview',
            {'token': raw},
        )
        self.assertEqual(preview.status_code, 200)
        body = preview.json()['data']
        self.assertTrue(body['can_accept'])
        self.assertEqual(body['agency']['name'], self.agency.name)
        self.assertNotIn('09124001102', str(body))

        resp = self.advisor_client.post(
            '/api/mobile/v1/agency/invite/respond',
            {'token': raw, 'action': 'accept', 'consent_acknowledged': True},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['action'], 'accepted')

    def test_agency_settings_patch(self):
        resp = self.owner_client.patch(
            '/api/mobile/v1/agency/settings',
            {'name': 'آژانس به‌روز', 'lead_routing_policy': 'inbox'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.agency.refresh_from_db()
        self.assertEqual(self.agency.name, 'آژانس به‌روز')
        self.assertEqual(self.agency.lead_routing_policy, 'inbox')

    def test_advisor_cannot_patch_settings(self):
        resp = self.advisor_client.patch(
            '/api/mobile/v1/agency/settings',
            {'name': 'Hack'},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_activity_event_types(self):
        resp = self.owner_client.get('/api/mobile/v1/agency/activity')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('event_types', resp.json()['data'])

    def test_bulk_moderation_permissions(self):
        from unittest.mock import patch

        prop = CRMProperty.objects.create(
            user=self.owner,
            agency=self.agency,
            title='Bulk mod',
            city='تهران',
        )
        with patch.dict(
            'workspace.constants.AGENCY_COMMAND_CENTER_FEATURES',
            {'agency_space': True},
            clear=False,
        ):
            item = publish_property(
                self.owner,
                prop.pk,
                visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            )
            resp = self.owner_client.post(
                '/api/mobile/v1/agency/space/moderate/bulk',
                {'action': 'hide', 'item_ids': [item.pk]},
                format='json',
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()['data']
            self.assertEqual(data['succeeded'], 1)
            self.assertTrue(data['results'][0]['ok'])

            item.refresh_from_db()
            self.assertEqual(item.status, AgencySpaceItem.STATUS_MODERATION_HIDDEN)

            restore = self.owner_client.post(
                '/api/mobile/v1/agency/space/moderate/bulk',
                {'action': 'restore', 'item_ids': [item.pk]},
                format='json',
            )
            self.assertEqual(restore.json()['data']['succeeded'], 1)

    def test_audit_read_only_manager(self):
        resp = self.owner_client.get('/api/mobile/v1/agency/audit', {'limit': 10})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('timeline', resp.json()['data'])

    def test_agency_contracts_list_owner(self):
        resp = self.owner_client.get('/api/mobile/v1/agency/contracts')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn('items', body['data'])
        self.assertIn('stats', body['data'])
        self.assertIn('advisors', body['data'])

    def test_agency_contracts_forbidden_for_advisor(self):
        resp = self.advisor_client.get('/api/mobile/v1/agency/contracts')
        self.assertEqual(resp.status_code, 403)
