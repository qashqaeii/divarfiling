"""تست‌های یکپارچه Sync — صفحه‌بندی، بایگانی، دسترسی، Retry."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from mobile_api.services.sync_service import push_sync
from workspace.models import CRMProperty, Customer
from workspace.services.crm_contact_archive import archive_contact

User = get_user_model()


class SyncArchiveAndAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sync_a', password='x', phone='09121110001')
        self.other = User.objects.create_user(username='sync_b', password='x', phone='09121110088')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.mine = Customer.objects.create(
            user=self.user, name='مالک', phone='09121110011', status='جدید',
        )
        self.theirs = Customer.objects.create(
            user=self.other, name='دیگری', phone='09121110022', status='جدید',
        )

    def test_archived_contact_in_deleted_ids_on_delta_pull(self):
        since = (timezone.now() - timezone.timedelta(minutes=1)).isoformat()
        archive_contact(self.user, self.mine, reason='تست')
        resp = self.client.get(
            '/api/mobile/v1/sync',
            {'since': since, 'entities': 'contacts'},
        )
        self.assertEqual(resp.status_code, 200)
        deleted = resp.json()['data']['contacts']['deleted_ids']
        self.assertIn(self.mine.pk, deleted)
        upserted_ids = {c['id'] for c in resp.json()['data']['contacts']['upserted']}
        self.assertNotIn(self.mine.pk, upserted_ids)

    def test_push_update_other_users_contact_rejected(self):
        resp = self.client.post(
            '/api/mobile/v1/sync/push',
            {
                'operations': [{
                    'op_id': 'cross-tenant-1',
                    'entity': 'contact',
                    'action': 'update',
                    'payload': {'contact_id': self.theirs.pk, 'status': 'نامعتبر'},
                }],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()['data']
        self.assertEqual(body['mapped'], [])
        self.assertTrue(body['conflicts'])
        self.theirs.refresh_from_db()
        self.assertEqual(self.theirs.status, 'جدید')


class SyncLargePullTests(TestCase):
    @patch('mobile_api.services.sync_service.ENTITY_LIMITS', {'contacts': 25, 'deals': 200, 'properties': 25, 'reminders': 200, 'activities': 300})
    def test_pull_many_contacts_and_properties_without_loss(self):
        user = User.objects.create_user(username='09123330000', password='x')
        client = APIClient()
        token = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        for i in range(60):
            Customer.objects.create(
                user=user, name=f'ن {i}', phone=f'0913000{i:04d}', status='جدید',
            )
        for i in range(30):
            CRMProperty.objects.create(user=user, title=f'ملک {i}', city='تهران')
        seen_c, seen_p = set(), set()
        cursor = None
        while True:
            params = {'entities': 'contacts,properties', 'since': ''}
            if cursor:
                params['cursor'] = cursor
            resp = client.get('/api/mobile/v1/sync', params)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()['data']
            for c in data['contacts']['upserted']:
                self.assertNotIn(c['id'], seen_c)
                seen_c.add(c['id'])
            for p in data['properties']['upserted']:
                self.assertNotIn(p['id'], seen_p)
                seen_p.add(p['id'])
            if not data.get('has_more'):
                break
            cursor = data['next_cursor']
        self.assertEqual(len(seen_c), 60)
        self.assertEqual(len(seen_p), 30)


class SyncRetryPushTests(TestCase):
    def test_five_retries_same_op_id_single_contact(self):
        user = User.objects.create_user(username='retry_u', password='x', phone='09124440000')
        op = {
            'op_id': 'retry-op-99',
            'entity': 'contact',
            'action': 'create',
            'payload': {'full_name': 'Retry', 'phone': '09124449999'},
        }
        server_ids = set()
        for _ in range(5):
            out = push_sync(user, [op])
            if out['mapped']:
                server_ids.add(out['mapped'][0]['server_id'])
        self.assertEqual(Customer.objects.filter(user=user, phone='09124449999').count(), 1)
        self.assertEqual(len(server_ids), 1)
