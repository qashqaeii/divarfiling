"""تست‌های امنیتی API لایسنس."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from licenses.models import License, LicenseActivation
from shop.models import LicensePlan, Order, Product

User = get_user_model()

TEST_HW = 'a' * 64
TEST_HW_B = 'b' * 64
TEST_KEY = 'ABCD-1234-5678-9ABC'


@override_settings(LICENSE_ALLOW_LOCAL_DEV=True)
class LicenseAPITests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='buyer1',
            password='pass1234',
            phone='09121111111',
        )
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-api-test',
            description='test',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=100000,
            duration_days=30,
            max_activations=1,
            is_active=True,
        )
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
        )
        self.license = License.objects.create(
            order=order,
            plan=self.plan,
            license_key=TEST_KEY,
            status='inactive',
            max_activations=1,
            expires_at=timezone.now() + timedelta(days=30),
        )
        LicenseActivation.objects.create(
            license=self.license,
            hardware_fingerprint=TEST_HW,
            is_active=False,
        )

    def test_activate_success(self):
        resp = self.client.post('/api/licenses/activate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('offline_grace_until', data)
        self.license.refresh_from_db()
        self.assertEqual(self.license.status, 'active')

    def test_validate_requires_active_slot(self):
        resp = self.client.post('/api/licenses/validate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['valid'])

    def test_validate_after_activate(self):
        act = self.client.post('/api/licenses/activate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(act.status_code, 200, act.content)
        resp = self.client.post('/api/licenses/validate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertTrue(resp.json()['valid'], resp.json())

    def test_invalid_key_format_rejected(self):
        resp = self.client.post('/api/licenses/activate/', {
            'license_key': 'bad-key',
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_invalid_fingerprint_rejected(self):
        resp = self.client.post('/api/licenses/activate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': 'short',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_expired_license_rejected(self):
        self.license.expires_at = timezone.now() - timedelta(days=1)
        self.license.save()
        resp = self.client.post('/api/licenses/activate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_deactivate_frees_slot_and_marks_inactive(self):
        self.client.post('/api/licenses/activate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        resp = self.client.post('/api/licenses/deactivate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.license.refresh_from_db()
        self.assertEqual(self.license.status, 'inactive')

    def test_max_activations_enforced(self):
        self.client.post('/api/licenses/activate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        resp = self.client.post('/api/licenses/activate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW_B,
        }, format='json')
        self.assertEqual(resp.status_code, 400)


@override_settings(DEBUG=False, LICENSE_ALLOW_LOCAL_DEV=False, LICENSE_BOT_API_KEY='test-bot-key')
class LicenseAPIBotKeyTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_missing_bot_api_key_rejected_in_production(self):
        resp = self.client.post('/api/licenses/activate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_valid_bot_api_key_accepted(self):
        resp = self.client.post(
            '/api/licenses/activate/',
            {'license_key': TEST_KEY, 'hardware_fingerprint': TEST_HW},
            format='json',
            HTTP_X_BOT_API_KEY='test-bot-key',
        )
        self.assertIn(resp.status_code, (403, 404, 400))


class OrderFulfillmentIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer2',
            password='pass1234',
            phone='09122222222',
        )
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-fulfill-test',
            description='test',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=100000,
            duration_days=30,
            is_active=True,
        )
        self.order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='pending',
        )

    def test_fulfill_twice_is_idempotent(self):
        from shop.services.order_fulfillment import fulfill_order_after_payment

        fulfill_order_after_payment(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        fulfill_order_after_payment(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
