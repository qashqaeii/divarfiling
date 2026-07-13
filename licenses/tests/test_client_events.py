"""تست API رویدادهای اپ کلاینت ویندوز."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from licenses.models import ClientAppEvent, License, LicenseActivation
from shop.models import LicensePlan, Order, Product

User = get_user_model()

TEST_HW = 'd' * 64
TEST_KEY = 'WIND-1234-5678-9ABC'


@override_settings(LICENSE_ALLOW_LOCAL_DEV=True)
class ClientAppEventAPITests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='win_user',
            password='pass1234',
            phone='09123333333',
        )
        self.product = Product.objects.create(
            title='ربات',
            slug='bot-win-event-test',
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

    def _activate(self):
        resp = self.client.post('/api/licenses/activate/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()

    def test_first_launch_recorded_after_activation(self):
        self._activate()
        resp = self.client.post('/api/licenses/client-event/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
            'event_type': 'first_launch',
            'app_version': '1.0.0',
            'platform': 'windows',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['recorded'])
        self.assertEqual(
            ClientAppEvent.objects.filter(
                license=self.license,
                event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
                user=self.user,
            ).count(),
            1,
        )

    def test_first_launch_idempotent(self):
        self._activate()
        payload = {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
            'event_type': 'first_launch',
            'app_version': '1.0.0',
        }
        first = self.client.post('/api/licenses/client-event/', payload, format='json')
        second = self.client.post('/api/licenses/client-event/', payload, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(first.json()['recorded'])
        self.assertFalse(second.json()['recorded'])
        self.assertEqual(ClientAppEvent.objects.count(), 1)

    def test_requires_active_activation(self):
        self.license.status = 'active'
        self.license.save(update_fields=['status'])
        resp = self.client.post('/api/licenses/client-event/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
            'event_type': 'first_launch',
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_invalid_event_type_rejected(self):
        self._activate()
        resp = self.client.post('/api/licenses/client-event/', {
            'license_key': TEST_KEY,
            'hardware_fingerprint': TEST_HW,
            'event_type': 'unknown_event',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
