"""Post-call CRM resolve — mobile API."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import Customer
from workspace.services.crm_agency import create_agency
from workspace.tests.agency_test_utils import ensure_agency_subscription

User = get_user_model()


class PostCallResolveMobileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='pcowner', password='test')
        self.user.phone = '09123001111'
        self.user.save(update_fields=['phone'])
        self.agency = create_agency(self.user, 'آژانس PostCall')
        ensure_agency_subscription(self.user, self.agency)
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_existing_contact(self):
        Customer.objects.create(
            user=self.user,
            agency=self.agency,
            name='علی تست',
            phone='09121234567',
            customer_type='سرنخ',
            status='جدید',
            source='موبایل',
        )
        resp = self.client.post(
            '/api/mobile/v1/crm/post-call/resolve',
            {'phone': '0912 123 4567'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['status'], 'existing_contact')
        self.assertEqual(data['contact']['full_name'], 'علی تست')

    def test_new_contact(self):
        resp = self.client.post(
            '/api/mobile/v1/crm/post-call/resolve',
            {'phone': '09129998877'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['status'], 'new_contact')

    def test_ambiguous_shared_phone(self):
        phone = '09121112233'
        Customer.objects.create(
            user=self.user,
            agency=self.agency,
            name='اول',
            phone=phone,
            customer_type='سرنخ',
            status='جدید',
            source='موبایل',
        )
        Customer.objects.create(
            user=self.user,
            agency=self.agency,
            name='دوم',
            phone=phone,
            customer_type='خریدار',
            status='در حال پیگیری',
            source='موبایل',
        )
        resp = self.client.post(
            '/api/mobile/v1/crm/post-call/resolve',
            {'phone': phone},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['status'], 'ambiguous')
        self.assertEqual(len(data['contacts']), 2)
        self.assertIsNone(data['contact'])

    def test_invalid_phone(self):
        resp = self.client.post(
            '/api/mobile/v1/crm/post-call/resolve',
            {'phone': '123'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['status'], 'invalid_phone')
