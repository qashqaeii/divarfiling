"""Epic 04 — Agency Mobile Operations API tests."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.constants import TEAM_VISIBILITY_INBOX
from workspace.models import CRMAgencyMember, Customer
from workspace.services.crm_agency import create_agency
from workspace.tests.agency_test_utils import ensure_agency_subscription

User = get_user_model()


class Epic04AgencyMobileTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='ep04owner', password='test')
        self.owner.phone = '09123001001'
        self.owner.save(update_fields=['phone'])
        self.advisor = User.objects.create_user(username='ep04advisor', password='test')
        self.advisor.phone = '09123001002'
        self.advisor.save(update_fields=['phone'])
        self.outsider = User.objects.create_user(username='ep04out', password='test')
        self.outsider.phone = '09123001099'
        self.outsider.save(update_fields=['phone'])

        self.agency = create_agency(self.owner, 'آژانس Epic04')
        ensure_agency_subscription(self.owner, self.agency)
        self.member = CRMAgencyMember.objects.create(
            agency=self.agency,
            user=self.advisor,
            role='advisor',
            is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        self.other_agency = create_agency(self.outsider, 'آژانس دیگر')
        ensure_agency_subscription(self.outsider, self.other_agency)

        self.client = APIClient()
        token = RefreshToken.for_user(self.owner)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

        self.lead = Customer.objects.create(
            user=self.owner,
            agency=self.agency,
            name='سرنخ صندوق',
            phone='09121110000',
            team_visibility=TEAM_VISIBILITY_INBOX,
            source='وب‌سایت',
        )

    def test_agency_home_manager(self):
        resp = self.client.get('/api/mobile/v1/agency/home')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertTrue(data['has_agency'])
        self.assertIn('logo_url', data['agency'])
        self.assertIn('kpis', data)
        self.assertIn('capabilities', data)
        self.assertTrue(data['permissions']['can_manage_agency'])

    def test_list_advisors(self):
        resp = self.client.get('/api/mobile/v1/agency/advisors')
        self.assertEqual(resp.status_code, 200)
        advisors = resp.json()['data']['advisors']
        self.assertTrue(any(a['user_id'] == self.advisor.id for a in advisors))

    def test_advisor_detail_cross_agency_denied(self):
        other_member = CRMAgencyMember.objects.filter(agency=self.other_agency).first()
        resp = self.client.get(f'/api/mobile/v1/agency/advisors/{other_member.pk}')
        self.assertEqual(resp.status_code, 404)

    def test_advisor_performance_scope(self):
        resp = self.client.get('/api/mobile/v1/agency/performance', {'days': 7})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('members', resp.json()['data'])

    def test_unauthorized_advisor_denied_seats(self):
        client = APIClient()
        token = RefreshToken.for_user(self.advisor)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        resp = client.get('/api/mobile/v1/agency/seats')
        self.assertEqual(resp.status_code, 403)

    def test_inbox_list(self):
        resp = self.client.get('/api/mobile/v1/crm/team/inbox')
        self.assertEqual(resp.status_code, 200)
        ids = [row['id'] for row in resp.json()['data']['leads']]
        self.assertIn(self.lead.pk, ids)

    def test_assign_lead(self):
        resp = self.client.post(
            f'/api/mobile/v1/crm/team/leads/{self.lead.pk}/assign',
            {'member_id': self.member.pk},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.user_id, self.advisor.id)

    def test_transfer_lead_manager(self):
        self.lead.user = self.advisor
        self.lead.assigned_to = self.advisor
        self.lead.team_visibility = 'assigned'
        self.lead.save()
        owner_member = CRMAgencyMember.objects.get(agency=self.agency, user=self.owner)
        resp = self.client.post(
            f'/api/mobile/v1/crm/team/leads/{self.lead.pk}/transfer',
            {'member_id': owner_member.pk, 'note': 'test'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

    def test_invite_validation(self):
        resp = self.client.post(
            '/api/mobile/v1/agency/invitations',
            {'phone': 'invalid'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_advisor_set_role(self):
        resp = self.client.post(
            f'/api/mobile/v1/agency/advisors/{self.member.pk}/actions',
            {'action': 'set_role', 'role': 'manager'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, 'manager')

    def test_advisor_workspace_contacts(self):
        Customer.objects.create(
            user=self.advisor,
            agency=self.agency,
            name='مخاطب مشاور',
            phone='09125556677',
            status='جدید',
        )
        resp = self.client.get(
            f'/api/mobile/v1/agency/advisors/{self.member.pk}/workspace',
            {'tab': 'contacts'},
        )
        self.assertEqual(resp.status_code, 200)
        items = resp.json()['data']['items']
        self.assertTrue(any(i['name'] == 'مخاطب مشاور' for i in items))

    def test_advisor_detail_includes_goals_and_roles(self):
        resp = self.client.get(f'/api/mobile/v1/agency/advisors/{self.member.pk}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('assignable_roles', data)
        self.assertTrue(any(r['value'] == 'advisor' for r in data['assignable_roles']))
        self.assertIn('stats', data)
        self.assertTrue(data['permissions']['can_set_role'])

    def test_agency_activity_feed(self):
        resp = self.client.get('/api/mobile/v1/agency/activity')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()['data']
        self.assertIn('events', body)
        self.assertTrue(body['can_filter_advisor'])

    def test_unauthorized_transfer(self):
        owned_by_owner = Customer.objects.create(
            user=self.owner,
            agency=self.agency,
            name='owner lead',
            phone='09122224444',
            assigned_to=self.advisor,
            team_visibility='assigned',
        )
        client = APIClient()
        token = RefreshToken.for_user(self.advisor)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        resp = client.post(
            f'/api/mobile/v1/crm/team/leads/{owned_by_owner.pk}/transfer',
            {'member_id': self.member.pk},
            format='json',
        )
        self.assertIn(resp.status_code, (403, 400))

    def test_advisor_cannot_list_performance(self):
        client = APIClient()
        token = RefreshToken.for_user(self.advisor)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        resp = client.get('/api/mobile/v1/agency/performance')
        self.assertEqual(resp.status_code, 403)
