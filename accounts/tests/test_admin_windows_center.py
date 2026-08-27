"""تست مرکز ویندوز — Funnel، Pagination و امنیت."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_dashboard import _date_range
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active
from accounts.services.admin_windows_app import (
    WINDOWS_FUNNEL_PAGE_SIZE,
    build_windows_funnel_steps,
    build_windows_range_summary,
    get_windows_user_funnel,
)
from accounts.services.admin_windows_center import get_windows_center_context
from licenses.models import ClientAppEvent, License, LicenseActivation
from shop.models import DownloadLog, LicensePlan, Order, Product

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran')
class WindowsCenterServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='winu1', password='x', phone='09120000101')
        self.product = Product.objects.create(title='ربات', slug='win-bot', is_active=True)
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

    def _create_license(self):
        return License.objects.create(
            order=self.order,
            plan=self.plan,
            status='active',
        )

    def test_range_summary_counts(self):
        DownloadLog.objects.create(
            user=self.user,
            order=self.order,
            ip_address='127.0.0.1',
            user_agent='test',
        )
        start, end = _date_range(7)
        summary = build_windows_range_summary(start, end)
        self.assertGreaterEqual(summary['downloads'], 1)
        self.assertGreaterEqual(summary['download_users'], 1)

    def test_funnel_steps_progression(self):
        DownloadLog.objects.create(user=self.user, order=self.order, ip_address='1.1.1.1', user_agent='ua')
        license_obj = self._create_license()
        LicenseActivation.objects.create(
            license=license_obj,
            is_active=True,
            activated_at=timezone.now(),
        )
        start, end = _date_range(7)
        steps = build_windows_funnel_steps(start, end)
        self.assertEqual(steps[0]['count'], 1)
        self.assertEqual(steps[1]['count'], 1)

    def test_funnel_pagination(self):
        for i in range(WINDOWS_FUNNEL_PAGE_SIZE + 2):
            u = User.objects.create_user(username=f'win{i}', password='x', phone=f'0914000{i:04d}')
            order = Order.objects.create(
                user=u,
                product=self.product,
                plan=self.plan,
                amount=100000,
                status='paid',
                paid_at=timezone.now(),
            )
            DownloadLog.objects.create(user=u, order=order, ip_address='1.1.1.1', user_agent='ua')
        start, end = _date_range(30)
        rows, total = get_windows_user_funnel(start=start, end=end, page=2, page_size=WINDOWS_FUNNEL_PAGE_SIZE)
        self.assertEqual(total, WINDOWS_FUNNEL_PAGE_SIZE + 2)
        self.assertEqual(len(rows), 2)

    def test_context_no_sensitive_fields(self):
        DownloadLog.objects.create(user=self.user, order=self.order, ip_address='1.2.3.4', user_agent='secret-agent')
        ctx = get_windows_center_context(days=7)
        payload = str(ctx['download_rows']) + str(ctx['funnel_rows'])
        self.assertNotIn('0912', payload)
        self.assertNotIn('secret-agent', payload)
        self.assertNotIn('1.2.3.4', payload)

    def test_export_urls_present(self):
        ctx = get_windows_center_context(days=30)
        self.assertIn('downloads', ctx['export_urls'])
        self.assertIn('windows_downloads', ctx['export_urls']['downloads'])


@override_settings(TIME_ZONE='Asia/Tehran')
class AdminWindowsCenterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='winstaff', password='pass1234', phone='09120000102', is_staff=True,
        )
        self.user = User.objects.create_user(username='winu2', password='x', phone='09120000103')

    def test_staff_only(self):
        self.assertEqual(self.client.get(reverse('admin_panel_windows')).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('admin_panel_windows')).status_code, 403)

    def test_render_ranges_pagination_sidebar(self):
        product = Product.objects.create(title='W', slug='win-p', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='م', plan_type='monthly', price=100000, duration_days=30, is_active=True,
        )
        order = Order.objects.create(
            user=self.user, product=product, plan=plan, amount=100000, status='paid', paid_at=timezone.now(),
        )
        DownloadLog.objects.create(user=self.user, order=order, ip_address='9.9.9.9', user_agent='ua')
        license_obj = License.objects.create(order=order, plan=plan, status='active')
        activation = LicenseActivation.objects.create(
            license=license_obj, is_active=True, activated_at=timezone.now(),
        )
        ClientAppEvent.objects.create(
            license=license_obj,
            user=self.user,
            activation=activation,
            event_type=ClientAppEvent.EventType.FIRST_LAUNCH,
            platform=ClientAppEvent.Platform.WINDOWS,
            app_version='2.15.0',
            hardware_fingerprint='fp-secret',
            ip_address='9.9.9.9',
        )

        self.client.force_login(self.staff)
        for days in ('1', '7', '30', '90'):
            resp = self.client.get(reverse('admin_panel_windows'), {'days': days})
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode()
            self.assertIn('ecc-windows', content)
            self.assertIn('windows-funnel-table', content)
            self.assertIn(f'data-range="{days}"', content)

        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/windows/'), 'windows')

    def test_compare_and_anchor_fallback(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_windows'), {'days': '30', 'compare': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('compare=1', resp.content.decode())
        dash = self.client.get(reverse('admin_panel'), {'days': '7'})
        self.assertIn('/accounts/admin-panel/windows/', dash.content.decode())
        self.assertIn('#ecc-windows', dash.content.decode())
