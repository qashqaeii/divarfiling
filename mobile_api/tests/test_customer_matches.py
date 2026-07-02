"""تست API تطبیق و پیشنهاد ملک برای مخاطب."""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import CRMProperty, Customer, PropertyMatchAlert
from workspace.services.crm_match_notifications import (
    discover_customer_matches,
    is_match_eligible,
    process_user_customer_matches,
)

User = get_user_model()


class CustomerMatchesApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09123334444', password='test')
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.customer = Customer.objects.create(
            user=self.user,
            name='خریدار تست',
            phone='09123334444',
            customer_type='خریدار',
            status='در حال پیگیری',
            budget_min=1_000_000_000,
            budget_max=3_000_000_000,
            areas='ونک',
        )
        self.property = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان ونک',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=2_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=90,
            rooms='2',
            property_type='آپارتمان',
        )

    def test_match_eligible_buyer(self):
        self.assertTrue(is_match_eligible(self.customer))
        seller = Customer.objects.create(
            user=self.user,
            name='فروشنده',
            phone='09120000001',
            customer_type='فروشنده',
        )
        self.assertFalse(is_match_eligible(seller))

    def test_get_contact_matches(self):
        resp = self.client.get(f'/api/mobile/v1/crm/contacts/{self.customer.pk}/matches')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertTrue(data['eligible'])
        self.assertGreaterEqual(data['total_count'], 1)

    def test_suggest_contact_matches(self):
        matches_resp = self.client.get(f'/api/mobile/v1/crm/contacts/{self.customer.pk}/matches')
        match = matches_resp.json()['data']['crm_matches'][0]
        resp = self.client.post(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}/suggest',
            {'matches': [match]},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['data']['suggested_count'], 1)
        self.assertTrue(
            PropertyMatchAlert.objects.filter(
                user=self.user,
                customer=self.customer,
                status=PropertyMatchAlert.STATUS_SUGGESTED,
            ).exists()
        )

    def test_discover_and_notify(self):
        from mobile_api.models import MobileDevice, MobileNotification

        MobileDevice.objects.create(
            user=self.user,
            device_id='match-test-device',
            fcm_token='fake',
            notification_prefs={'customer_match': True},
        )
        matches = discover_customer_matches(self.customer, self.user, divar_enabled=False)
        self.assertGreaterEqual(len(matches), 1)
        sent = process_user_customer_matches(self.user, divar_enabled=False)
        self.assertGreaterEqual(sent, 1)
        self.assertTrue(
            MobileNotification.objects.filter(
                user=self.user,
                notification_type='customer_match',
            ).exists()
        )
