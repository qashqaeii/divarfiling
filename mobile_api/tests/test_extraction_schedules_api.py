"""تست API زمان‌بندی استخراج موبایل."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from licenses.models import License
from mobile_api.models import MobileExtractionRun, MobileExtractionSchedule
from mobile_api.services.extraction_ingest import EXTRACTIONS_DAILY_LIMIT
from shop.models import LicensePlan, Order, Product

User = get_user_model()


class ExtractionScheduleApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09127778899', password='test')
        product = Product.objects.create(title='ربات', slug='bot-schedule', description='تست', is_active=True)
        plan = LicensePlan.objects.create(
            product=product,
            name='Pro',
            plan_type='yearly',
            price=1000000,
            duration_days=365,
            max_activations=2,
        )
        order = Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=1000000,
            status='paid',
        )
        License.objects.create(
            order=order,
            license_key='SCHEDULE-KEY',
            plan=plan,
            status='active',
            max_activations=2,
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.filters = {
            'city_id': '1',
            'city_name': 'تهران',
            'category': 'apartment-rent',
            'category_label': 'آپارتمان',
            'transaction_type_label': 'اجاره مسکونی',
            'max_items': 20,
        }

    def test_create_schedule_with_15_minute_interval(self):
        resp = self.client.post(
            '/api/mobile/v1/extractions/schedules',
            {
                'interval_hours': 0.25,
                'filters': self.filters,
                'max_items': 20,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['data']['interval_hours'], 0.25)

    def test_create_list_and_toggle_schedule(self):
        resp = self.client.post(
            '/api/mobile/v1/extractions/schedules',
            {
                'interval_hours': 6,
                'filters': self.filters,
                'max_items': 20,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        schedule_id = resp.json()['data']['id']
        self.assertTrue(MobileExtractionSchedule.objects.filter(user=self.user).exists())

        list_resp = self.client.get('/api/mobile/v1/extractions/schedules')
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(len(list_resp.json()['data']), 1)

        toggle = self.client.post(f'/api/mobile/v1/extractions/schedules/{schedule_id}/toggle')
        self.assertEqual(toggle.status_code, 200)
        self.assertFalse(toggle.json()['data']['is_enabled'])

    def test_start_run_and_fail(self):
        schedule = MobileExtractionSchedule.objects.create(
            user=self.user,
            title='تست',
            filters=self.filters,
            max_items=20,
            is_enabled=True,
            next_run_at=timezone.now(),
        )
        start = self.client.post(f'/api/mobile/v1/extractions/schedules/{schedule.pk}/runs/start')
        self.assertEqual(start.status_code, 200)
        run_id = start.json()['data']['run']['id']
        self.assertEqual(MobileExtractionRun.objects.get(pk=run_id).status, 'running')

        fail = self.client.post(
            f'/api/mobile/v1/extractions/runs/{run_id}/fail',
            {'error': 'شبکه قطع شد'},
            format='json',
        )
        self.assertEqual(fail.status_code, 200)
        schedule.refresh_from_db()
        self.assertEqual(schedule.last_status, 'failed')

    def test_due_schedules_endpoint(self):
        MobileExtractionSchedule.objects.create(
            user=self.user,
            title='سررسید',
            filters=self.filters,
            is_enabled=True,
            next_run_at=timezone.now(),
        )
        resp = self.client.get('/api/mobile/v1/extractions/schedules/due')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()['data']), 1)

    def test_limits_include_remaining(self):
        resp = self.client.get('/api/mobile/v1/extractions/limits')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertIn('can_extract_now', data)
        self.assertIn('remaining_today', data)
        self.assertEqual(data['extractions_daily_limit'], EXTRACTIONS_DAILY_LIMIT)
