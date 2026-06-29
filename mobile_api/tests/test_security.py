"""تست‌های امنیتی API موبایل."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from licenses.models import License, LicenseActivation
from mobile_api.models import MobileExtractionRun, MobileExtractionSchedule
from shop.models import LicensePlan, Order, Product
from workspace.models import Dataset

User = get_user_model()


class MobileSecurityTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09129998877',
            phone='09129998877',
            password='testpass123',
        )
        product = Product.objects.create(title='ربات', slug='bot-sec', description='تست', is_active=True)
        plan = LicensePlan.objects.create(
            product=product,
            name='Pro',
            plan_type='yearly',
            price=1000000,
            duration_days=365,
            max_activations=1,
        )
        order = Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=1000000,
            status='paid',
        )
        self.license = License.objects.create(
            order=order,
            license_key='SEC-KEY-1234',
            plan=plan,
            status='active',
            max_activations=1,
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='فایل تست',
            original_filename='test.json',
            file_format='json',
            file_size=0,
            row_count=1,
            column_count=1,
            columns=['token'],
            is_active=True,
        )
        self.client = APIClient()

    def _login(self):
        resp = self.client.post('/api/mobile/v1/auth/login', {
            'username': '09129998877',
            'password': 'testpass123',
        }, format='json')
        self.assertTrue(resp.data.get('ok'), resp.data)
        token = resp.data['data']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        return resp.data['data']

    def test_filing_detail_blocked_without_license(self):
        self._login()
        self.license.status = 'expired'
        self.license.save(update_fields=['status'])
        resp = self.client.get(f'/api/mobile/v1/filing/datasets/{self.dataset.pk}')
        self.assertEqual(resp.status_code, 404)

    def test_device_register_respects_max_activations(self):
        self._login()
        LicenseActivation.objects.create(
            license=self.license,
            hardware_fingerprint='existing-device',
            label='Desktop',
            is_active=True,
        )
        resp = self.client.post('/api/mobile/v1/devices/register', {
            'device_id': 'new-android-device',
            'device_model': 'Pixel',
            'os_version': '14',
            'app_version': '2.4.3',
        }, format='json')
        self.assertFalse(resp.data.get('ok'))
        self.assertEqual(resp.status_code, 403)

    def test_completed_schedule_run_cannot_be_reused(self):
        self._login()
        schedule = MobileExtractionSchedule.objects.create(
            user=self.user,
            title='روزانه',
            filters={'category': 'apartment-rent'},
            is_enabled=True,
            next_run_at=timezone.now(),
        )
        run = MobileExtractionRun.objects.create(
            user=self.user,
            schedule=schedule,
            status=MobileExtractionSchedule.RUN_STATUS_SUCCESS,
            finished_at=timezone.now(),
        )
        resp = self.client.post('/api/mobile/v1/extractions/upload', {
            'run_id': run.pk,
            'filters': {'category': 'apartment-rent', 'max_items': 1, 'city_id': '1'},
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{
                'token': 'abc123',
                'title': 'تست',
                'price': 1000000,
            }],
        }, format='json')
        self.assertFalse(resp.data.get('ok'))
