"""تست مرکز لایسنس — Range، Renewal، Snapshot و Render."""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_dashboard import _date_range, _previous_period_bounds
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active
from accounts.services.admin_licenses_center import (
    _licenses_new_between,
    _renewal_revenue_between,
    _renewals_between,
    get_licenses_center_context,
)
from licenses.models import License
from shop.models import LicensePlan, Order, Product

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran')
class LicensesCenterServiceTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user(username='lic1', password='x', phone='09120000031')
        self.product = Product.objects.create(title='محصول', slug='lic-p', is_active=True)
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=100000,
            duration_days=30,
            is_active=True,
        )

    def _paid_order(self, day, amount=100000, renewal_license=None):
        paid_at = timezone.make_aware(datetime.combine(day, time(12, 0)))
        return Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=Decimal(amount),
            status='paid',
            paid_at=paid_at,
            renewal_license=renewal_license,
        )

    def test_new_licenses_in_range(self):
        License.objects.create(
            order=self._paid_order(self.today),
            plan=self.plan,
            status='active',
        )
        start, end = _date_range(7)
        ctx = get_licenses_center_context(days=7)
        kpi = next(c for c in ctx['range_kpi_cards'] if c['key'] == 'licenses_new_period')
        self.assertEqual(kpi['value'], _licenses_new_between(start, end))

    def test_renewal_vs_new_license_distinction(self):
        first = self._paid_order(self.today - timedelta(days=40), 80000)
        lic = License.objects.create(order=first, plan=self.plan, status='active')
        self._paid_order(self.today, 120000, renewal_license=lic)

        start, end = _date_range(30)
        ctx = get_licenses_center_context(days=30)
        self.assertEqual(_renewals_between(start, end), 1)
        self.assertEqual(ctx['renewal_breakdown']['formal_renewals_range'], 1)
        self.assertEqual(ctx['renewal_breakdown']['renewal_revenue_range'], 120000)

    def test_snapshot_kpis(self):
        License.objects.create(
            order=self._paid_order(self.today),
            plan=self.plan,
            status='active',
        )
        ctx = get_licenses_center_context(days=30)
        keys = {c['key'] for c in ctx['snapshot_kpi_cards']}
        self.assertIn('licenses_active', keys)
        self.assertIn('active_devices', keys)

    def test_previous_period_same_length(self):
        start, end = _date_range(30)
        prev_start, prev_end = _previous_period_bounds(30)
        self.assertEqual((end - start).days + 1, (prev_end - prev_start).days + 1)

    def test_expiring_and_export_links(self):
        ctx = get_licenses_center_context(days=30)
        export_keys = {e['key'] for e in ctx['export_links']}
        self.assertIn('active_licenses', export_keys)
        self.assertIn('expiring_licenses', export_keys)
        self.assertIn('expired_licenses', export_keys)


@override_settings(TIME_ZONE='Asia/Tehran')
class AdminLicensesCenterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='licstaff', password='pass1234', phone='09127777781', is_staff=True,
        )

    def test_staff_only(self):
        self.assertEqual(self.client.get(reverse('admin_panel_licenses')).status_code, 302)
        user = User.objects.create_user(username='nolic', password='x', phone='09127777782')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('admin_panel_licenses')).status_code, 403)

    def test_template_render_sidebar_exports(self):
        self.client.force_login(self.staff)
        for days in ('1', '7', '30', '90'):
            resp = self.client.get(reverse('admin_panel_licenses'), {'days': days})
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode()
            self.assertIn('chart-licenses-activity', content)
            self.assertIn('chart-renewal-revenue', content)
            self.assertIn(f'data-range="{days}"', content)
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/licenses/'), 'licenses')
        resp = self.client.get(reverse('admin_panel_licenses'))
        content = resp.content.decode()
        self.assertIn(reverse('admin_panel_export', args=['active_licenses']), content)
        self.assertIn(reverse('admin_panel_export', args=['expiring_licenses']), content)

    def test_compare_and_anchor_fallback(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_licenses'), {'days': '30', 'compare': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('compare=1', resp.content.decode())
        dash = self.client.get(reverse('admin_panel'), {'days': '7'})
        self.assertIn('/accounts/admin-panel/licenses/', dash.content.decode())
