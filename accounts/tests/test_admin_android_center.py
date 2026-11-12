"""تست مرکز اندروید — Funnel، Pagination و امنیت."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_android_app import (
    ANDROID_FUNNEL_PAGE_SIZE,
    build_android_funnel_steps,
    build_android_range_summary,
    get_android_user_funnel,
    get_android_version_distribution,
    get_outdated_android_users,
    is_android_version_outdated,
    parse_app_version_tuple,
)
from accounts.services.admin_android_center import get_android_center_context
from accounts.services.admin_dashboard import _date_range
from accounts.services.admin_marketing import build_segment_recipients
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active
from licenses.models import License, LicenseActivation
from mobile_api.models import MobileDevice
from shop.models import LicensePlan, Order, Product

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran')
class AndroidCenterServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='andu1', password='x', phone='09120000201')
        self.product = Product.objects.create(title='ربات', slug='and-bot', is_active=True)
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
            amount=100000,
            status='paid',
            paid_at=timezone.now(),
        )

    def _create_device(self, **kwargs):
        defaults = {
            'user': self.user,
            'device_id': f'device-{MobileDevice.objects.count() + 1}',
            'device_model': 'Pixel 8',
            'os_version': '14',
            'app_version': '2.6.4',
            'is_active': True,
        }
        defaults.update(kwargs)
        return MobileDevice.objects.create(**defaults)

    def test_range_summary_counts(self):
        self._create_device()
        start, end = _date_range(7)
        summary = build_android_range_summary(start, end)
        self.assertGreaterEqual(summary['registrations'], 1)
        self.assertGreaterEqual(summary['install_users'], 1)
        self.assertGreaterEqual(summary['dau_today'], 0)

    def test_funnel_steps_progression(self):
        self._create_device(is_active=True)
        license_obj = License.objects.create(order=self.order, plan=self.plan, status='active')
        LicenseActivation.objects.create(
            license=license_obj,
            is_active=True,
            activated_at=timezone.now(),
            notes='device_type=mobile',
        )
        start, end = _date_range(7)
        steps = build_android_funnel_steps(start, end)
        self.assertEqual(steps[0]['count'], 1)
        self.assertEqual(steps[1]['count'], 1)
        self.assertEqual(steps[2]['count'], 1)

    def test_version_distribution(self):
        self._create_device(app_version='2.6.4')
        self._create_device(device_id='device-2', app_version='2.6.3')
        rows = get_android_version_distribution()
        self.assertGreaterEqual(len(rows), 1)
        self.assertIn('version', rows[0])

    def test_funnel_pagination(self):
        for i in range(ANDROID_FUNNEL_PAGE_SIZE + 2):
            u = User.objects.create_user(username=f'and{i}', password='x', phone=f'0915000{i:04d}')
            MobileDevice.objects.create(
                user=u,
                device_id=f'pag-device-{i}',
                device_model='Samsung',
                app_version='2.6.0',
            )
        start, end = _date_range(30)
        rows, total = get_android_user_funnel(start=start, end=end, page=2, page_size=ANDROID_FUNNEL_PAGE_SIZE)
        self.assertEqual(total, ANDROID_FUNNEL_PAGE_SIZE + 2)
        self.assertEqual(len(rows), 2)

    def test_context_no_sensitive_fields(self):
        self._create_device(device_id='secret-device-id-12345')
        ctx = get_android_center_context(days=7)
        payload = str(ctx['registration_rows']) + str(ctx['funnel_rows'])
        self.assertNotIn('0912', payload)
        self.assertNotIn('secret-device-id', payload)

    def test_export_urls_present(self):
        ctx = get_android_center_context(days=30)
        self.assertIn('devices', ctx['export_urls'])
        self.assertIn('android_devices', ctx['export_urls']['devices'])

    def test_version_outdated_detection(self):
        self.assertEqual(parse_app_version_tuple('2.6.4'), (2, 6, 4))
        self.assertTrue(is_android_version_outdated('2.6.3', '2.6.4'))
        self.assertFalse(is_android_version_outdated('2.6.4', '2.6.4'))
        self.assertTrue(is_android_version_outdated('', '2.6.4'))

    def test_outdated_segment_lists_user(self):
        self._create_device(app_version='2.0.0')
        recipients = build_segment_recipients('android_outdated')
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0].context.get('version'), '2.0.0')
        self.assertIn('latest_version', recipients[0].context)

    def test_sms_context_present(self):
        self._create_device(app_version='2.0.0')
        ctx = get_android_center_context(days=30)
        self.assertIn('sms', ctx)
        self.assertGreaterEqual(ctx['sms']['outdated_count'], 1)
        self.assertIn('default_template', ctx['sms'])
        self.assertIn('send_url', ctx['sms'])


@override_settings(TIME_ZONE='Asia/Tehran')
class AdminAndroidCenterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='andstaff', password='pass1234', phone='09120000202', is_staff=True,
        )
        self.user = User.objects.create_user(username='andu2', password='x', phone='09120000203')

    def test_staff_only(self):
        self.assertEqual(self.client.get(reverse('admin_panel_android')).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('admin_panel_android')).status_code, 403)

    def test_render_ranges_pagination_sidebar(self):
        MobileDevice.objects.create(
            user=self.user,
            device_id='view-device-1',
            device_model='Xiaomi',
            app_version='2.6.4',
            is_active=True,
        )
        self.client.force_login(self.staff)
        for days in ('1', '7', '30', '90'):
            resp = self.client.get(reverse('admin_panel_android'), {'days': days})
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode()
            self.assertIn('aac-page', content)
            self.assertIn('aac-overview', content)
            self.assertIn(f'data-range="{days}"', content)

        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/android/'), 'android')

    def test_compare_mode(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_android'), {'days': '30', 'compare': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('compare=1', resp.content.decode())

    def test_sms_preview_json(self):
        self.staff.is_superuser = True
        self.staff.save(update_fields=['is_superuser'])
        MobileDevice.objects.create(
            user=self.user,
            device_id='preview-device',
            app_version='1.0.0',
            is_active=True,
        )
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_android_sms_preview'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('ok'))
        self.assertEqual(data.get('key'), 'android_outdated')
        self.assertGreaterEqual(data.get('count', 0), 1)

    def test_android_page_renders_sms_section(self):
        MobileDevice.objects.create(
            user=self.user,
            device_id='sms-device',
            app_version='1.0.0',
            is_active=True,
        )
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_android'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('aac-sms', content)
        self.assertIn('فراز SMS', content)
