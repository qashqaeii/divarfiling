"""Idempotency Push Sync با op_id."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from mobile_api.models import MobileSyncOperation
from workspace.models import Customer

User = get_user_model()


class SyncPushIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09126667788', password='x')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.op = {
            'op_id': 'fixed-op-001',
            'entity': 'contact',
            'action': 'create',
            'payload': {'full_name': 'سرنخ Idempotent', 'phone': '09125556644'},
        }

    def test_duplicate_op_id_does_not_create_second_contact(self):
        for _ in range(2):
            resp = self.client.post('/api/mobile/v1/sync/push', {'operations': [self.op]}, format='json')
            self.assertEqual(resp.status_code, 200)
            body = resp.json()['data']
            self.assertEqual(len(body['mapped']), 1)
        self.assertEqual(Customer.objects.filter(user=self.user, phone='09125556644').count(), 1)
        self.assertEqual(MobileSyncOperation.objects.filter(user=self.user, op_id='fixed-op-001').count(), 1)
