"""تست مرکز فروش — Range، KPI، Snapshot و Render."""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_dashboard import (
    ALL_TIME_DAYS,
    _date_range,
    _orders_paid_between,
    _pct_change,
    _previous_period_bounds,
    _revenue_between,
)
from accounts.services.admin_panel_shell import format_admin_panel_days_param
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active
from accounts.services.admin_sales_center import get_sales_center_context
from shop.models import LicensePlan, Order, Product

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran')
class SalesCenterServiceTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='محصول تست', slug='sales-p', is_active=True)
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=200000,
            duration_days=30,
            is_active=True,
        )
        self.today = timezone.localdate()
        self.user = User.objects.create_user(username='buyer1', password='x', phone='09120000011')

    def _paid_order(self, day, amount=200000):
        paid_at = timezone.make_aware(datetime.combine(day, time(12, 0)))
        return Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=Decimal(amount),
            status='paid',
            paid_at=paid_at,
        )

    def test_kpi_revenue_respects_range(self):
        self._paid_order(self.today, 100000)
        self._paid_order(self.today - timedelta(days=20), 300000)

        ctx7 = get_sales_center_context(days=7)
        ctx30 = get_sales_center_context(days=30)
        rev7 = next(c for c in ctx7['kpi_cards'] if c['key'] == 'revenue_range')
        rev30 = next(c for c in ctx30['kpi_cards'] if c['key'] == 'revenue_range')

        self.assertEqual(rev7['value'], 100000)
        self.assertEqual(rev30['value'], 400000)

    def test_previous_period_same_length(self):
        start, end = _date_range(30)
        prev_start, prev_end = _previous_period_bounds(30)
        curr_len = (end - start).days + 1
        prev_len = (prev_end - prev_start).days + 1
        self.assertEqual(curr_len, prev_len)

        self._paid_order(self.today, 50000)
        self._paid_order(prev_start, 80000)

        ctx = get_sales_center_context(days=30)
        rev_card = next(c for c in ctx['kpi_cards'] if c['key'] == 'revenue_range')
        delta_card = next(c for c in ctx['kpi_cards'] if c['key'] == 'revenue_delta')

        self.assertEqual(rev_card['value'], _revenue_between(start, end))
        self.assertEqual(rev_card['delta'], delta_card['value'])

    def test_aov_and_unique_buyers(self):
        buyer2 = User.objects.create_user(username='buyer2', password='x', phone='09120000012')
        self._paid_order(self.today, 100000)
        Order.objects.create(
            user=buyer2,
            product=self.product,
            plan=self.plan,
            amount=Decimal(300000),
            status='paid',
            paid_at=timezone.make_aware(datetime.combine(self.today, time(14, 0))),
        )

        ctx = get_sales_center_context(days=7)
        aov = next(c for c in ctx['kpi_cards'] if c['key'] == 'aov')
        buyers = next(c for c in ctx['kpi_cards'] if c['key'] == 'unique_buyers')
        orders = next(c for c in ctx['kpi_cards'] if c['key'] == 'paid_orders_range')

        self.assertEqual(orders['value'], 2)
        self.assertEqual(buyers['value'], 2)
        self.assertEqual(aov['value'], 200000)

    def test_snapshot_action_items_for_pending_and_failed(self):
        Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=Decimal(100000),
            status='pending',
        )
        Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=Decimal(100000),
            status='failed',
        )

        ctx = get_sales_center_context(days=30)
        keys = {item['key'] for item in ctx['action_items']}
        self.assertIn('orders_pending', keys)
        self.assertIn('orders_failed_today', keys)
        self.assertGreaterEqual(len(ctx['pending_orders']), 1)
        self.assertGreaterEqual(len(ctx['failed_orders']), 1)

    def test_pct_change_no_baseline_is_none_not_100(self):
        self.assertIsNone(_pct_change(1000, 0))

    def test_conversion_ignores_legacy_buyers_without_signup_in_range(self):
        paid_at = timezone.make_aware(datetime.combine(self.today, time(12, 0)))
        User.objects.create_user(username='nc_new', password='x', phone='09120000021')
        legacy = User.objects.create_user(username='nc_old', password='x', phone='09120000022')
        legacy.date_joined = timezone.make_aware(datetime.combine(self.today - timedelta(days=60), time(9, 0)))
        legacy.save(update_fields=['date_joined'])
        Order.objects.create(
            user=legacy,
            product=self.product,
            plan=self.plan,
            amount=Decimal(100000),
            status='paid',
            paid_at=paid_at,
        )
        ctx = get_sales_center_context(days=7)
        conv = next(c for c in ctx['kpi_cards'] if c['key'] == 'conversion_rate')
        self.assertEqual(conv['value'], 0.0)

    def test_all_time_revenue_delta_not_fake_100(self):
        self._paid_order(self.today, 200000)
        ctx = get_sales_center_context(days=ALL_TIME_DAYS)
        delta_card = next(c for c in ctx['kpi_cards'] if c['key'] == 'revenue_delta')
        self.assertIsNone(delta_card['value'])

    def test_export_links_use_all_not_zero(self):
        links = get_sales_center_context(days=ALL_TIME_DAYS)['export_links']
        paid = next(link for link in links if link['key'] == 'paid_orders')
        self.assertIn('days=all', paid['url'])
        self.assertEqual(format_admin_panel_days_param(ALL_TIME_DAYS), 'all')

    def test_breakdown_filtered_by_range(self):
        self._paid_order(self.today, 150000)
        start, end = _date_range(7)
        ctx = get_sales_center_context(days=7)
        self.assertTrue(ctx['product_revenue'])
        self.assertEqual(ctx['product_revenue'][0]['total'], 150000)
        self.assertEqual(
            ctx['product_revenue'][0]['count'],
            _orders_paid_between(start, end),
        )


@override_settings(TIME_ZONE='Asia/Tehran')
class AdminSalesCenterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='salesstaff', password='pass1234', phone='09127777777', is_staff=True,
        )
        self.product = Product.objects.create(title='P', slug='sales-view', is_active=True)
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=100000,
            duration_days=30,
            is_active=True,
        )

    def test_staff_only(self):
        anon = self.client.get(reverse('admin_panel_sales'))
        self.assertEqual(anon.status_code, 302)

        user = User.objects.create_user(username='norm', password='pass1234', phone='09128888888')
        self.client.login(username='norm', password='pass1234')
        denied = self.client.get(reverse('admin_panel_sales'))
        self.assertEqual(denied.status_code, 403)

    def test_template_render_and_sidebar_active(self):
        self.client.login(username='salesstaff', password='pass1234')
        for days in ('1', '7', '30', '90'):
            resp = self.client.get(reverse('admin_panel_sales'), {'days': days})
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode()
            self.assertIn('فروش و درآمد', content)
            self.assertIn('chart-revenue', content)
            self.assertIn('chart-sales-trend', content)
            self.assertIn(f'data-range="{days}"', content)

        self.assertEqual(
            resolve_admin_panel_nav_active('/accounts/admin-panel/sales/'),
            'sales',
        )

    def test_compare_query_preserved_in_shell(self):
        self.client.login(username='salesstaff', password='pass1234')
        resp = self.client.get(reverse('admin_panel_sales'), {'days': '30', 'compare': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('compare=1', resp.content.decode())

    def test_export_links_intact(self):
        self.staff.is_superuser = True
        self.staff.save(update_fields=['is_superuser'])
        self.client.login(username='salesstaff', password='pass1234')
        resp = self.client.get(reverse('admin_panel_sales'), {'days': '30'})
        content = resp.content.decode()
        self.assertIn(reverse('admin_panel_export', args=['paid_orders']), content)
        self.assertIn(reverse('admin_panel_export', args=['pending_orders']), content)
        self.assertIn(reverse('admin_panel_export', args=['failed_orders']), content)

    def test_recovery_center_linked_not_duplicated(self):
        self.client.login(username='salesstaff', password='pass1234')
        resp = self.client.get(reverse('admin_panel_sales'))
        content = resp.content.decode()
        self.assertEqual(content.count('مرکز بازیابی'), 0)
        self.assertIn(reverse('admin_panel_recovery_center'), content)
