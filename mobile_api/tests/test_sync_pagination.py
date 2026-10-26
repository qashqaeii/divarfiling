"""صفحه‌بندی Pull Sync."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import Customer

User = get_user_model()


class SyncPaginationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09127778899', password='x')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        for i in range(12):
            Customer.objects.create(
                user=self.user,
                name=f'مخاطب {i}',
                phone=f'0912000{i:04d}',
                status='جدید',
            )

    @patch('mobile_api.services.sync_service.ENTITY_LIMITS', {'contacts': 5, 'deals': 200, 'properties': 200, 'reminders': 200, 'activities': 300})
    def test_pull_paginates_contacts_without_loss(self):
        resp1 = self.client.get(
            '/api/mobile/v1/sync',
            {'entities': 'contacts', 'since': ''},
        )
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()['data']
        first_count = len(data1['contacts']['upserted'])
        self.assertEqual(first_count, 5)
        self.assertTrue(data1.get('has_more'))
        cursor = data1['next_cursor']
        seen = {c['id'] for c in data1['contacts']['upserted']}
        while data1.get('has_more'):
            resp = self.client.get(
                '/api/mobile/v1/sync',
                {'entities': 'contacts', 'cursor': cursor},
            )
            self.assertEqual(resp.status_code, 200)
            data1 = resp.json()['data']
            for c in data1['contacts']['upserted']:
                self.assertNotIn(c['id'], seen)
                seen.add(c['id'])
            cursor = data1.get('next_cursor')
        self.assertEqual(len(seen), 12)
