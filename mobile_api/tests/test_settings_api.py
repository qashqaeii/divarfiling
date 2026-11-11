"""تست API تنظیمات و هشدار انقضای لایسنس."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from licenses.models import License
from mobile_api.models import MobileDevice, MobileNotification
from mobile_api.services.notification_scheduler import process_license_expiry, user_push_enabled
from shop.models import LicensePlan, Order, Product

User = get_user_model()


def _create_active_license(user, *, days_until_expiry: int = 7):
    product = Product.objects.create(title='ربات', slug=f'bot-{user.pk}', description='تست', is_active=True)
    plan = LicensePlan.objects.create(
        product=product,
        name='طلایی',
        plan_type='yearly',
        price=1000000,
        duration_days=365,
        max_activations=2,
    )
    order = Order.objects.create(
        user=user,
        product=product,
        plan=plan,
        amount=1000000,
        status='paid',
    )
    return License.objects.create(
        order=order,
        license_key=f'TEST-KEY-{user.pk}',
        plan=plan,
        status='active',
        max_activations=2,
        expires_at=timezone.now() + timedelta(days=days_until_expiry),
    )


class SettingsApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09126667788', password='test')
        self.user.first_name = 'حسین'
        self.user.last_name = 'مشاور'
        self.user.phone = '09126667788'
        self.user.save()
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {token.access_token}',
            HTTP_X_DEVICE_ID='settings-device-1',
        )
        MobileDevice.objects.create(
            user=self.user,
            device_id='settings-device-1',
            fcm_token='tok',
            notification_prefs={'crm_reminders': True},
        )

    def test_get_and_patch_profile(self):
        resp = self.client.get('/api/mobile/v1/settings/profile')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['full_name'], 'حسین مشاور')

        patch = self.client.patch(
            '/api/mobile/v1/settings/profile',
            {'full_name': 'رضا احمدی', 'phone': '09120000000'},
            format='json',
        )
        self.assertEqual(patch.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'رضا')
        self.assertEqual(self.user.phone, '09120000000')

    def test_preset_avatar_json_is_saved_and_returned(self):
        response = self.client.post(
            '/api/mobile/v1/settings/profile/avatar',
            {'avatar_key': 'avatar_09'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['data']['avatar_key'], 'avatar_09')
        self.assertFalse(response.json()['data']['has_custom_avatar'])
        self.assertEqual(
            self.client.get('/api/mobile/v1/settings/profile').json()['data']['avatar_key'],
            'avatar_09',
        )

    def test_invalid_preset_avatar_is_rejected(self):
        response = self.client.post(
            '/api/mobile/v1/settings/profile/avatar',
            {'avatar_key': 'avatar_99'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotEqual(
            self.client.get('/api/mobile/v1/settings/profile').json()['data']['avatar_key'],
            'avatar_99',
        )

    def test_notification_prefs_roundtrip(self):
        get_resp = self.client.get('/api/mobile/v1/settings/notifications')
        self.assertEqual(get_resp.status_code, 200)
        self.assertTrue(get_resp.json()['data']['crm_reminders'])

        patch = self.client.patch(
            '/api/mobile/v1/settings/notifications',
            {'crm_reminders': False, 'digest_hour': 9, 'license_alerts': False},
            format='json',
        )
        self.assertEqual(patch.status_code, 200)
        data = patch.json()['data']
        self.assertFalse(data['crm_reminders'])
        self.assertEqual(data['digest_hour'], 9)
        self.assertFalse(data['license_alerts'])

    def test_license_status_includes_days_remaining(self):
        _create_active_license(self.user, days_until_expiry=12)
        resp = self.client.get('/api/mobile/v1/license/status')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('days_remaining', data)
        self.assertGreaterEqual(data['days_remaining'], 11)


class LicenseExpirySchedulerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09128889999', password='test')
        MobileDevice.objects.create(
            user=self.user,
            device_id='lic-device',
            fcm_token='tok',
            notification_prefs={'license_alerts': True},
        )
        _create_active_license(self.user, days_until_expiry=7)

    def test_license_expiry_at_seven_days(self):
        sent = process_license_expiry()
        self.assertEqual(sent, 1)
        n = MobileNotification.objects.get(user=self.user)
        self.assertEqual(n.notification_type, 'license_expiry')
        self.assertEqual(n.data['threshold'], 7)

    def test_license_push_respects_pref(self):
        MobileDevice.objects.filter(user=self.user).update(
            notification_prefs={'license_alerts': False},
        )
        self.assertFalse(user_push_enabled(self.user, 'license_expiry'))
