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
    LICENSES_PULSE_KEYS,
    _licenses_new_between,
    _renewal_revenue_between,
    _renewals_between,
    build_expiring_license_preview_rows,
    build_licenses_hero_status,
    build_recent_expired_license_preview_rows,
    build_recent_renewal_preview_rows,
    build_users_without_license_preview_rows,
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

    def test_licenses_hero_status_shares(self):
        ctx = get_licenses_center_context(days=30)
        st = ctx.get('licenses_hero_status') or {}
        self.assertIn('total', st)
        self.assertIn('pct_healthy', st)
        self.assertIn('expiring_7d', st)
        self.assertAlmostEqual(
            st.get('pct_healthy', 0) + st.get('pct_expiring', 0) + st.get('pct_expired', 0),
            100.0 if st.get('total') else 0.0,
            places=1,
        )

    def test_build_licenses_hero_status_from_snapshot(self):
        snapshot = {
            'licenses_active': 80,
            'licenses_expiring_14d': 10,
            'licenses_expiring_7d': 3,
            'licenses_expired': 20,
            'active_devices': 50,
            'users_without_license': 5,
        }
        st = build_licenses_hero_status(
            snapshot,
            renewal_breakdown={'renewal_rate_range': 12.5, 'formal_renewals_range': 2, 'new_key_repurchase_range': 1},
        )
        self.assertEqual(st['healthy'], 70)
        self.assertEqual(st['total'], 100)

    def test_licenses_revenue_chart_summary(self):
        ctx = get_licenses_center_context(days=30)
        summary = ctx.get('licenses_revenue_chart_summary') or []
        self.assertEqual(len(summary), 3)
        keys = {item['key'] for item in summary}
        self.assertEqual(keys, {'revenue_sum', 'revenue_peak', 'revenue_avg'})

    def test_licenses_hero_chart_summary(self):
        ctx = get_licenses_center_context(days=30)
        summary = ctx.get('licenses_hero_chart_summary') or []
        self.assertEqual(len(summary), 3)
        keys = {item['key'] for item in summary}
        self.assertEqual(keys, {'issued_sum', 'renew_sum', 'renewal_revenue'})

    def test_center_pulse_quad(self):
        ctx = get_licenses_center_context(days=30)
        pulse = ctx.get('center_pulse') or []
        self.assertEqual(len(pulse), 4)
        labels = {c['label'] for c in pulse}
        self.assertEqual(
            labels,
            {'لایسنس جدید', 'تمدید / خرید مجدد', 'لایسنس فعال', 'در شرف انقضا'},
        )
        keys = {c['key'] for c in pulse}
        self.assertEqual(keys, {key for key, _ in LICENSES_PULSE_KEYS})
        range_chips = [c for c in pulse if c.get('pulse_kind') == 'range']
        self.assertEqual(len(range_chips), 2)
        self.assertTrue(all(c.get('previous_value') is not None for c in range_chips))
        snapshot_chips = [c for c in pulse if c.get('pulse_kind') == 'snapshot']
        self.assertEqual(len(snapshot_chips), 2)
        self.assertTrue(all(c.get('hint') for c in snapshot_chips))

    def test_range_kpi_cards_have_previous_values(self):
        ctx = get_licenses_center_context(days=30)
        for card in ctx.get('range_kpi_cards') or []:
            self.assertIn('previous_value', card)
            self.assertIn('delta', card)

    def test_previous_period_same_length(self):
        start, end = _date_range(30)
        prev_start, prev_end = _previous_period_bounds(30)
        self.assertEqual((end - start).days + 1, (prev_end - prev_start).days + 1)

    def test_recent_renewal_preview_rows(self):
        ctx = get_licenses_center_context(days=30)
        rows = ctx.get('recent_renewal_rows') or []
        summary = ctx.get('recent_renewal_summary') or {}
        self.assertEqual(len(rows), len(ctx.get('recent_renewals') or []))
        self.assertEqual(summary.get('total'), len(rows))
        if rows:
            self.assertIn('kind', rows[0])
            self.assertIn('kind_label', rows[0])
        empty = build_recent_renewal_preview_rows([])
        self.assertEqual(empty['total'], 0)

    def test_users_without_license_preview_rows(self):
        ctx = get_licenses_center_context(days=30)
        rows = ctx.get('users_without_license_rows') or []
        summary = ctx.get('users_without_license_summary') or {}
        self.assertEqual(len(rows), len(ctx.get('users_without_license_list') or []))
        self.assertEqual(summary.get('total'), len(rows))
        if rows:
            self.assertIn('tier', rows[0])
            self.assertIn('pending_orders', rows[0])
        empty = build_users_without_license_preview_rows([])
        self.assertEqual(empty['total'], 0)

    def test_recent_expired_license_preview_rows(self):
        ctx = get_licenses_center_context(days=30)
        rows = ctx.get('recent_expired_rows') or []
        summary = ctx.get('recent_expired_summary') or {}
        self.assertEqual(len(rows), len(ctx.get('recent_expired') or []))
        self.assertEqual(summary.get('total'), len(rows))
        if rows:
            self.assertIn('days_since_expiry', rows[0])
            self.assertIn('lapse', rows[0])
        empty = build_recent_expired_license_preview_rows([])
        self.assertEqual(empty['total'], 0)

    def test_expiring_license_preview_rows(self):
        ctx = get_licenses_center_context(days=30)
        rows = ctx.get('expiring_license_rows') or []
        self.assertEqual(len(rows), len(ctx.get('expiring_licenses') or []))
        if rows:
            self.assertIn('days_left', rows[0])
            self.assertIn('urgency', rows[0])

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
        self.staff.is_superuser = True
        self.staff.save(update_fields=['is_superuser'])
        self.client.force_login(self.staff)
        for days in ('1', '7', '30', '90'):
            resp = self.client.get(reverse('admin_panel_licenses'), {'days': days})
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode()
            self.assertIn('chart-licenses-activity', content)
            self.assertIn('licenses-hero-chart-panel', content)
            self.assertIn('adm-overview-hero', content)
            self.assertIn('adm-licenses-hero-status__bars', content)
            self.assertIn('adm-licenses-action-queue', content)
            self.assertIn('adm-licenses-kpi-lux--pro', content)
            self.assertIn('adm-licenses-kpi-card', content)
            self.assertIn('adm-licenses-renewal', content)
            self.assertIn('adm-licenses-revenue-chart', content)
            self.assertIn('adm-licenses-table-card', content)
            self.assertIn('id="licenses-table-expiring"', content)
            self.assertIn('licenses-table-recent-renewals', content)
            self.assertIn('adm-licenses-renewal-kind-badge', content)
            self.assertIn('tab=licenses', content)
            self.assertIn('adm-user-360-link', content)
            self.assertIn('licenses-table-no-license', content)
            self.assertIn('adm-licenses-no-license-tier-badge', content)
            self.assertIn('licenses-table-expired', content)
            self.assertIn('adm-licenses-lapse-badge', content)
            self.assertIn('adm-licenses-exports', content)
            self.assertIn('adm-licenses-export-chip', content)
            self.assertIn('id="ecc-licensing"', content)
            self.assertIn('در یک نگاه ·', content)
            self.assertIn('adm-center-kpi-compare', content)
            self.assertIn('دوره قبل', content)
            self.assertNotIn('adm-prime-kpi-band', content)
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
