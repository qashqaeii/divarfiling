"""فعال‌سازی لایسنس موبایل پس از خرید — مسیر devices/register و license/status."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from licenses.models import License, LicenseActivation
from mobile_api.models import MobileDevice
from shop.models import LicensePlan, Order, Product

User = get_user_model()


def _bot_plan():
    product = Product.objects.create(
        title='ربات',
        slug='bot-mobile-lic',
        description='تست',
        is_active=True,
    )
    return LicensePlan.objects.create(
        product=product,
        name='Pro',
        plan_type='yearly',
        price=1_000_000,
        duration_days=365,
        max_activations=2,
    )


def _paid_order(user, plan):
    return Order.objects.create(
        user=user,
        product=plan.product,
        plan=plan,
        amount=plan.price,
        status='paid',
        paid_at=timezone.now(),
    )


def _inactive_license(user, plan, **kwargs):
    order = _paid_order(user, plan)
    defaults = {
        'order': order,
        'license_key': kwargs.pop('license_key', 'MOB-INACTIVE-KEY'),
        'plan': plan,
        'status': 'inactive',
        'max_activations': plan.max_activations,
        'expires_at': timezone.now() + timezone.timedelta(days=30),
    }
    defaults.update(kwargs)
    return License.objects.create(**defaults)


class MobileLicenseActivationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09127770001',
            phone='09127770001',
            password='testpass123',
        )
        self.plan = _bot_plan()
        self.client = APIClient()

    def _login(self):
        resp = self.client.post('/api/mobile/v1/auth/login', {
            'username': '09127770001',
            'password': 'testpass123',
        }, format='json')
        self.assertTrue(resp.data.get('ok'), resp.data)
        token = resp.data['data']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_inactive_license_activates_on_device_register(self):
        lic = _inactive_license(self.user, self.plan)
        self._login()
        resp = self.client.post('/api/mobile/v1/devices/register', {
            'device_id': 'android-post-purchase',
            'device_model': 'Pixel 8',
            'os_version': '15',
            'app_version': '3.0.0',
        }, format='json')
        self.assertTrue(resp.data.get('ok'), resp.data)
        lic.refresh_from_db()
        self.assertEqual(lic.status, 'active')
        self.assertTrue(
            LicenseActivation.objects.filter(
                license=lic,
                hardware_fingerprint='android-post-purchase',
                is_active=True,
            ).exists(),
        )
        self.assertTrue(resp.data['data']['license']['valid'])

    def test_license_status_pending_not_expired_for_inactive_valid(self):
        _inactive_license(self.user, self.plan)
        self._login()
        resp = self.client.get('/api/mobile/v1/license/status')
        self.assertTrue(resp.data.get('ok'), resp.data)
        data = resp.data['data']
        self.assertFalse(data['valid'])
        self.assertEqual(data['status'], 'pending')
        self.assertIsNotNone(data.get('plan'))

    def test_register_before_purchase_then_activate_via_devices_me(self):
        self._login()
        device_id = 'pre-install-device'
        resp = self.client.post('/api/mobile/v1/devices/register', {
            'device_id': device_id,
            'device_model': 'Samsung',
        }, format='json')
        self.assertTrue(resp.data.get('ok'), resp.data)
        self.assertFalse(resp.data['data']['license']['valid'])

        lic = _inactive_license(self.user, self.plan)
        resp = self.client.patch(
            '/api/mobile/v1/devices/me',
            {'fcm_token': 'new-fcm-token'},
            format='json',
            HTTP_X_DEVICE_ID=device_id,
        )
        self.assertTrue(resp.data.get('ok'), resp.data)
        lic.refresh_from_db()
        self.assertEqual(lic.status, 'active')
        device = MobileDevice.objects.get(device_id=device_id)
        self.assertIsNotNone(device.license_activation_id)

    def test_device_register_idempotent_same_device(self):
        lic = _inactive_license(self.user, self.plan, license_key='IDEM-KEY')
        self._login()
        payload = {
            'device_id': 'idem-android',
            'device_model': 'Phone',
        }
        for _ in range(2):
            resp = self.client.post('/api/mobile/v1/devices/register', payload, format='json')
            self.assertTrue(resp.data.get('ok'), resp.data)
        self.assertEqual(
            LicenseActivation.objects.filter(license=lic, is_active=True).count(),
            1,
        )
        lic.refresh_from_db()
        self.assertEqual(lic.status, 'active')

    def test_expired_license_shows_expired_status(self):
        lic = _inactive_license(self.user, self.plan, license_key='EXP-KEY')
        lic.expires_at = timezone.now() - timezone.timedelta(days=1)
        lic.status = 'expired'
        lic.save(update_fields=['expires_at', 'status'])
        self._login()
        resp = self.client.get('/api/mobile/v1/license/status')
        data = resp.data['data']
        self.assertEqual(data['status'], 'expired')
        resp_reg = self.client.post('/api/mobile/v1/devices/register', {
            'device_id': 'after-expired',
            'device_model': 'X',
        }, format='json')
        self.assertTrue(resp_reg.data.get('ok'))
        self.assertFalse(resp_reg.data['data']['license']['valid'])
        lic.refresh_from_db()
        self.assertEqual(lic.status, 'expired')

    def test_second_device_rejected_when_capacity_full(self):
        lic = _inactive_license(self.user, self.plan, license_key='FULL-KEY', max_activations=1)
        token = str(RefreshToken.for_user(self.user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        first = self.client.post('/api/mobile/v1/devices/register', {
            'device_id': 'first-phone',
            'device_model': 'A',
        }, format='json')
        self.assertTrue(first.data.get('ok'), first.data)
        lic.refresh_from_db()
        self.assertEqual(lic.status, 'active')
        second = self.client.post('/api/mobile/v1/devices/register', {
            'device_id': 'second-phone',
            'device_model': 'B',
        }, format='json')
        self.assertFalse(second.data.get('ok'))
        self.assertEqual(second.status_code, 403)
        self.assertEqual(
            LicenseActivation.objects.filter(license=lic, is_active=True).count(),
            1,
        )
