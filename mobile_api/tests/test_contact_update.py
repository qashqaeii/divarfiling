"""تست به‌روزرسانی مخاطب با فیلدهای مالی پویا."""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import Customer

User = get_user_model()


class ContactUpdateApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09125556666', password='test')
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.customer = Customer.objects.create(
            user=self.user,
            name='متقاضی اجاره',
            phone='09125556666',
            customer_type='متقاضی اجاره',
            status='جدید',
        )

    def test_patch_rent_fields(self):
        resp = self.client.patch(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}',
            {
                'deposit_min': 200_000_000,
                'deposit_max': 500_000_000,
                'rent_min': 15_000_000,
                'rent_max': 25_000_000,
                'areas': 'ونک، نیاوران',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['deposit_min'], 200_000_000)
        self.assertEqual(data['rent_max'], 25_000_000)
        self.assertEqual(data['areas'], 'ونک، نیاوران')
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.deposit_min, 200_000_000)
        self.assertEqual(self.customer.rent_max, 25_000_000)

    def test_patch_budget_fields(self):
        buyer = Customer.objects.create(
            user=self.user,
            name='خریدار',
            phone='09127778888',
            customer_type='خریدار',
        )
        resp = self.client.patch(
            f'/api/mobile/v1/crm/contacts/{buyer.pk}',
            {
                'budget_min': 5_000_000_000,
                'budget_max': 8_000_000_000,
                'property_type': 'آپارتمان',
                'min_area': 90,
                'max_area': 130,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['budget_min'], 5_000_000_000)
        self.assertEqual(data['property_type'], 'آپارتمان')
        self.assertEqual(data['min_area'], 90)

    def test_patch_optional_identity_and_lease_deadline(self):
        resp = self.client.patch(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}',
            {
                'email': 'rent@example.com',
                'city': 'تهران',
                'district': 'ونک',
                'job': 'مهندس',
                'company_name': 'شرکت آریا',
                'national_id': '0012345678',
                'lease_deadline': '۱۴۰۵/۰۴/۲۷',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['email'], 'rent@example.com')
        self.assertEqual(data['job'], 'مهندس')
        self.assertEqual(data['company_name'], 'شرکت آریا')
        self.assertEqual(data['national_id'], '0012345678')
        self.assertEqual(data['lease_deadline'], '2026-07-18')
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.job, 'مهندس')
        self.assertEqual(str(self.customer.lease_deadline), '2026-07-18')

    def test_clear_lease_deadline(self):
        from datetime import date
        self.customer.lease_deadline = date(2026, 7, 18)
        self.customer.save(update_fields=['lease_deadline'])
        resp = self.client.patch(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}',
            {'lease_deadline': ''},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()['data']['lease_deadline'])
        self.customer.refresh_from_db()
        self.assertIsNone(self.customer.lease_deadline)
