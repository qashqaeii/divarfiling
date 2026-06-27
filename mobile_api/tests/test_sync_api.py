"""تست API همگام‌سازی موبایل."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import CRMDeal, CRMProperty, Customer, Reminder

User = get_user_model()


class SyncApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09124445566', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.customer = Customer.objects.create(
            user=self.user,
            name='مشتری sync',
            phone='09124445566',
            status='جدید',
        )

    def test_pull_sync_returns_entities(self):
        CRMDeal.objects.create(user=self.user, customer=self.customer, title='معامله', stage='سرنخ')
        CRMProperty.objects.create(user=self.user, title='ملک', city='تهران')
        Reminder.objects.create(
            user=self.user,
            customer=self.customer,
            title='یادآور',
            due_at=timezone.now(),
        )
        resp = self.client.get(
            '/api/mobile/v1/sync',
            {'entities': 'contacts,deals,properties,reminders,activities'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('server_time', data)
        self.assertGreaterEqual(len(data['contacts']['upserted']), 1)
        self.assertGreaterEqual(len(data['deals']['upserted']), 1)
        self.assertGreaterEqual(len(data['properties']['upserted']), 1)

    def test_push_sync_quick_lead(self):
        resp = self.client.post(
            '/api/mobile/v1/sync/push',
            {
                'operations': [{
                    'op_id': 'local-1',
                    'entity': 'contact',
                    'action': 'create',
                    'payload': {'full_name': 'سرنخ جدید', 'phone': '09120001111'},
                }],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()['data']
        self.assertEqual(len(body['mapped']), 1)
        self.assertEqual(Customer.objects.filter(user=self.user, phone='09120001111').count(), 1)

    def test_push_sync_contact_update(self):
        resp = self.client.post(
            '/api/mobile/v1/sync/push',
            {
                'operations': [{
                    'op_id': 'local-2',
                    'entity': 'contact',
                    'action': 'update',
                    'payload': {
                        'contact_id': self.customer.pk,
                        'status': 'در حال پیگیری',
                    },
                }],
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.status, 'در حال پیگیری')

    def test_pull_delta_since(self):
        since = timezone.now().isoformat()
        resp = self.client.get('/api/mobile/v1/sync', {'since': since, 'entities': 'contacts'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['contacts']['upserted'], [])
