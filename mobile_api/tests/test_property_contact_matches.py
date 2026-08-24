"""تست API پیشنهاد مخاطب برای فایل شخصی."""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import CRMProperty, Customer, PropertyContact

User = get_user_model()


class PropertyContactMatchesApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09126667788', phone='09126667788', password='test')
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.property = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان سعادت‌آباد',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=3_000_000_000,
            neighborhood='سعادت‌آباد',
            city='تهران',
            area=110,
            rooms='3',
            property_type='آپارتمان',
        )
        self.customer = Customer.objects.create(
            user=self.user,
            name='خریدار موبایل',
            phone='09126660001',
            customer_type='خریدار',
            status='در حال پیگیری',
            budget_min=2_000_000_000,
            budget_max=5_000_000_000,
            areas='سعادت‌آباد',
            property_type='آپارتمان',
        )

    def test_get_property_contact_matches(self):
        resp = self.client.get(
            f'/api/mobile/v1/crm/properties/{self.property.pk}/contact-matches',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertTrue(data['eligible'])
        self.assertFalse(data.get('forbidden'))
        self.assertGreaterEqual(data['total_count'], 1)
        self.assertEqual(data.get('deal_mode'), 'فروش')
        ids = {m['customer_id'] for m in data['matches']}
        self.assertIn(self.customer.pk, ids)

    def test_suggest_property_contacts(self):
        resp = self.client.post(
            f'/api/mobile/v1/crm/properties/{self.property.pk}/suggest-contacts',
            {'customer_ids': [self.customer.pk]},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()['data']
        self.assertEqual(body['suggested_count'], 1)
        self.assertTrue(body['suggestions'])
        self.assertIn('whatsapp_text', body['suggestions'][0])
        self.assertTrue(
            PropertyContact.objects.filter(
                customer=self.customer,
                property=self.property,
                role='پیشنهادی',
            ).exists()
        )

    def test_not_found_property(self):
        resp = self.client.get('/api/mobile/v1/crm/properties/999999/contact-matches')
        self.assertEqual(resp.status_code, 404)

    def test_other_user_forbidden(self):
        other = User.objects.create_user(
            username='09126669900', phone='09126669900', password='test',
        )
        token = RefreshToken.for_user(other)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        resp = self.client.get(
            f'/api/mobile/v1/crm/properties/{self.property.pk}/contact-matches',
        )
        self.assertEqual(resp.status_code, 404)

    def test_link_owner_by_manual_name_and_phone(self):
        resp = self.client.post(
            f'/api/mobile/v1/crm/properties/{self.property.pk}/contacts',
            {
                'full_name': 'مالک جدید',
                'phone': '09125551234',
                'role': 'مالک',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()['data']
        self.assertEqual(data['role'], 'مالک')
        self.assertTrue(
            PropertyContact.objects.filter(
                property=self.property,
                role='مالک',
                customer__phone='09125551234',
            ).exists()
        )
        self.assertTrue(
            Customer.objects.filter(user=self.user, phone='09125551234', name='مالک جدید').exists()
        )

    def test_link_owner_reuses_existing_contact_by_phone(self):
        resp = self.client.post(
            f'/api/mobile/v1/crm/properties/{self.property.pk}/contacts',
            {
                'full_name': 'نام دیگر',
                'phone': '09126660001',
                'role': 'مالک',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()['data']
        self.assertEqual(data['customer_id'], self.customer.pk)
