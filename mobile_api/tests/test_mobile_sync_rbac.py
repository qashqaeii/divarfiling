"""ماتریس RBAC — API موبایل و Sync."""
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from mobile_api.services.crm_service import create_note
from mobile_api.services.deals_service import create_deal_from_mobile
from mobile_api.services.sync_service import push_sync
from workspace.models import CRMAgencyMember, CRMProperty, Customer, Reminder
from workspace.services.crm_agency import create_agency
from workspace.services.crm_sharing import revoke_share, share_customer
from workspace.tests.agency_test_utils import ensure_agency_subscription

User = get_user_model()


def _jwt_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
    return client


class MobileAgencyRbacMatrixTests(TestCase):
    def setUp(self):
        self._share_entitlement = patch(
            'workspace.services.crm_sharing.can_share_team_resources',
            return_value=True,
        )
        self._share_entitlement.start()
        suffix = uuid.uuid4().hex[:6]
        self.owner = User.objects.create_user(username=f'o{suffix}', password='x', phone=f'0915100{suffix[:4]}')
        self.advisor_a = User.objects.create_user(username=f'a{suffix}', password='x', phone=f'0915200{suffix[:4]}')
        self.advisor_b = User.objects.create_user(username=f'b{suffix}', password='x', phone=f'0915300{suffix[:4]}')
        self.other_agency = User.objects.create_user(username=f'x{suffix}', password='x', phone=f'0915400{suffix[:4]}')
        self.agency = create_agency(self.owner, 'RBAC Sync')
        ensure_agency_subscription(self.owner, self.agency)
        self.member_a = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor_a, role='advisor', is_active=True,
        )
        self.member_b = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor_b, role='advisor', is_active=True,
        )
        self.contact_b = Customer.objects.create(
            user=self.advisor_b,
            agency=self.agency,
            name='خصوصی B',
            phone=f'0916000{suffix[:4]}',
            status='جدید',
        )
        self.contact_a = Customer.objects.create(
            user=self.advisor_a,
            agency=self.agency,
            name='خصوصی A',
            phone=f'0917000{suffix[:4]}',
            status='جدید',
        )
        self.share = share_customer(
            self.advisor_b,
            self.contact_b,
            self.member_a.pk,
            share_mode='confidential',
        )

    def tearDown(self):
        self._share_entitlement.stop()

    def test_advisor_a_cannot_update_advisor_b_private_contact(self):
        client = _jwt_client(self.advisor_a)
        resp = client.post(
            '/api/mobile/v1/sync/push',
            {
                'operations': [{
                    'op_id': 'rbac-upd-1',
                    'entity': 'contact',
                    'action': 'update',
                    'payload': {'contact_id': self.contact_b.pk, 'status': 'در حال پیگیری'},
                }],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()['data']
        self.assertFalse(body['mapped'])
        self.contact_b.refresh_from_db()
        self.assertEqual(self.contact_b.status, 'جدید')

    def test_shared_readonly_contact_rejects_note_and_deal(self):
        with self.assertRaises(PermissionError):
            create_note(self.advisor_a, self.contact_b.pk, {'content': 'یادداشت غیرمجاز'})
        with self.assertRaises(PermissionError):
            create_deal_from_mobile(self.advisor_a, {
                'customer_id': self.contact_b.pk,
                'title': 'معامله غیرمجاز',
            })

    def test_owner_cannot_mutate_advisor_private_contact_without_share(self):
        with self.assertRaises(ValueError):
            create_note(self.owner, self.contact_a.pk, {'content': 'مدیر'})

    def test_cross_tenant_push_blocked(self):
        client = _jwt_client(self.other_agency)
        resp = client.post(
            '/api/mobile/v1/sync/push',
            {
                'operations': [{
                    'op_id': 'rbac-x-1',
                    'entity': 'contact',
                    'action': 'update',
                    'payload': {'contact_id': self.contact_a.pk, 'status': 'بایگانی'},
                }],
            },
            format='json',
        )
        body = resp.json()['data']
        self.assertEqual(body['mapped'], [])

    def test_revoked_share_blocks_mutations(self):
        revoke_share(self.advisor_b, self.share.pk)
        with self.assertRaises(ValueError):
            create_note(self.advisor_a, self.contact_b.pk, {'content': 'بعد از لغو'})

    def test_inactive_member_loses_agency_shared_visibility(self):
        member = CRMAgencyMember.objects.get(agency=self.agency, user=self.advisor_a)
        member.is_active = False
        member.save(update_fields=['is_active'])
        client = _jwt_client(self.advisor_a)
        resp = client.get('/api/mobile/v1/sync', {'entities': 'contacts', 'since': ''})
        ids = {c['id'] for c in resp.json()['data']['contacts']['upserted']}
        self.assertNotIn(self.contact_b.pk, ids)

    def test_cannot_complete_other_advisors_reminder_on_shared_contact(self):
        reminder = Reminder.objects.create(
            user=self.advisor_b,
            customer=self.contact_b,
            title='یادآور B',
            due_at=timezone.now(),
        )
        with self.assertRaises(PermissionError):
            from mobile_api.services.crm_service import complete_reminder
            complete_reminder(self.advisor_a, reminder.pk)


class MobileSyncSecurityTests(TestCase):
    def test_invalid_cursor_returns_400(self):
        user = User.objects.create_user(username='cur', password='x', phone='09155001122')
        client = _jwt_client(user)
        resp = client.get('/api/mobile/v1/sync', {'entities': 'contacts', 'cursor': 'not-valid-cursor'})
        self.assertEqual(resp.status_code, 400)

    def test_payload_mismatch_on_same_op_id(self):
        user = User.objects.create_user(username='fp', password='x', phone='09155003344')
        op1 = {
            'op_id': 'same-op',
            'entity': 'contact',
            'action': 'create',
            'payload': {'full_name': 'اول', 'phone': '09155005566'},
        }
        push_sync(user, [op1])
        op2 = dict(op1)
        op2['payload'] = {'full_name': 'دوم', 'phone': '09155007788'}
        out = push_sync(user, [op2])
        self.assertTrue(any(c.get('reason') == 'payload_mismatch' for c in out['conflicts']))

    @patch('mobile_api.services.sync_service.ENTITY_LIMITS', {'contacts': 3, 'deals': 200, 'properties': 200, 'reminders': 200, 'activities': 300})
    def test_archived_tombstones_paginate(self):
        user = User.objects.create_user(username='tomb', password='x', phone='09155009900')
        client = _jwt_client(user)
        since = (timezone.now() - timezone.timedelta(hours=1)).isoformat()
        created = []
        for i in range(5):
            c = Customer.objects.create(
                user=user, name=f'آ {i}', phone=f'0915600{i:04d}', status='جدید',
            )
            created.append(c)
        from workspace.services.crm_contact_archive import archive_contact
        for c in created:
            archive_contact(user, c, reason='تست')
        seen = set()
        cursor = None
        while True:
            params = {'entities': 'contacts', 'since': since}
            if cursor:
                params['cursor'] = cursor
            resp = client.get('/api/mobile/v1/sync', params)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()['data']
            for pk in data['contacts']['deleted_ids']:
                seen.add(pk)
            if not data.get('has_more'):
                break
            cursor = data['next_cursor']
        self.assertEqual(len(seen), 5)


class CrmImportDedupTests(TestCase):
    def test_same_title_different_neighborhood_creates_two_properties(self):
        from workspace.services.crm_sync import import_crm_payload

        user = User.objects.create_user(username='imp', password='x')
        payload = {
            'contacts': [],
            'properties': [
                {'id': 1, 'title': 'ملک مشترک', 'city': 'تهران', 'neighborhood': 'الف'},
                {'id': 2, 'title': 'ملک مشترک', 'city': 'تهران', 'neighborhood': 'ب'},
            ],
            'deals': [],
        }
        stats = import_crm_payload(user, payload, merge=False, dry_run=False)
        self.assertEqual(stats['properties'], 2)
        self.assertEqual(CRMProperty.objects.filter(user=user, title='ملک مشترک').count(), 2)
