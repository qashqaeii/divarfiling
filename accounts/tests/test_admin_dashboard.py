"""تست داشبورد مدیریت سیستم."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.services.admin_dashboard import (
    build_action_queue,
    build_command_action_items,
    get_activity_feed,
    get_admin_dashboard_context,
    get_affiliate_partners,
    get_command_center_context,
    get_licensing_center_stats,
    get_plan_sales_breakdown,
    get_recent_affiliate_sales,
    get_recent_renewal_orders,
    get_today_stats,
    get_users_active_on_date,
    get_users_online_count,
)

User = get_user_model()


class AdminDashboardServiceTests(TestCase):
    def test_today_stats_keys(self):
        stats = get_today_stats()
        self.assertIn('revenue_today', stats)
        self.assertIn('signups_today', stats)
        self.assertIn('avg_order_value', stats)

    def test_dashboard_context_extended(self):
        ctx = get_admin_dashboard_context(days=30)
        self.assertIn('action_queue', ctx)
        self.assertIn('activity_feed', ctx)
        self.assertIn('health_indicators', ctx)
        self.assertIn('today_stats', ctx)
        self.assertIn('recovery_stats', ctx)
        self.assertIn('blog_stats', ctx)
        self.assertIn('academy_stats', ctx)
        self.assertIn('eligible_now', ctx['recovery_stats'])

    def test_action_queue_empty_when_no_pending(self):
        stats = get_admin_dashboard_context(days=30)['stats']
        queue = build_action_queue(stats)
        self.assertIsInstance(queue, list)

    def test_activity_feed_returns_list(self):
        feed = get_activity_feed(limit=5)
        self.assertIsInstance(feed, list)

    def test_plan_sales_includes_all_active_plans(self):
        from shop.bot_catalog import bot_license_plans
        from shop.models import LicensePlan, Product

        product = Product.objects.create(title='ربات تست', slug='test-bot-plans', is_active=True)
        for data in bot_license_plans():
            LicensePlan.objects.create(product=product, **data)

        expected = len(bot_license_plans())
        plans = get_plan_sales_breakdown()
        self.assertEqual(len(plans), expected)
        self.assertEqual(plans[0]['plan_type'], 'daily')
        self.assertIn('short_label', plans[0])
        self.assertIn('total', plans[0])

    def test_plan_sales_chart_payload(self):
        from accounts.services.admin_dashboard import build_plan_sales_chart_payload

        plans = get_plan_sales_breakdown()
        chart = build_plan_sales_chart_payload(plans)
        self.assertEqual(chart['chartKind'], 'plan_sales')
        self.assertEqual(len(chart['labels']), len(plans))
        self.assertIn('planTotals', chart)
        self.assertEqual(chart['planTotals'], [p['total'] for p in plans])
        self.assertEqual(len(chart['datasets'][0]['backgroundColor']), len(plans))

    def test_plan_sales_per_plan_id_not_plan_type(self):
        from shop.bot_catalog import bot_license_plans
        from shop.models import LicensePlan, Order, Product

        product = Product.objects.create(title='ربات تجمیع', slug='test-bot-agg', is_active=True)
        user = User.objects.create_user(username='buyer1', password='x', phone='09121111111')
        plan_data = bot_license_plans()[0]
        old_plan = LicensePlan.objects.create(product=product, **plan_data)
        Order.objects.create(
            user=user,
            product=product,
            plan=old_plan,
            amount=old_plan.price,
            status='paid',
        )
        old_plan.is_active = False
        old_plan.save(update_fields=['is_active'])
        new_plan = LicensePlan.objects.create(product=product, **plan_data)

        plans = get_plan_sales_breakdown()
        old_row = next(p for p in plans if p['plan_id'] == old_plan.id)
        new_row = next(p for p in plans if p['plan_id'] == new_plan.id)
        self.assertEqual(old_row['count'], 1)
        self.assertEqual(old_row['total'], int(old_plan.price))
        self.assertEqual(new_row['count'], 0)
        self.assertEqual(new_row['total'], 0)

    def test_affiliate_queries(self):
        partners = get_affiliate_partners(limit=5)
        sales = get_recent_affiliate_sales(limit=5)
        self.assertEqual(partners.model.__name__, 'Affiliate')
        self.assertEqual(sales.model.__name__, 'AffiliateSale')

    def test_licensing_renewal_stats_bought_and_renewed(self):
        from datetime import timedelta
        from decimal import Decimal

        from django.utils import timezone

        from licenses.models import License
        from shop.models import LicensePlan, Order, Product
        from shop.services.order_fulfillment import fulfill_order_after_payment

        product = Product.objects.create(title='ربات تمدید', slug='renew-kpi-bot', is_active=True)
        plan = LicensePlan.objects.create(
            product=product,
            name='ماهانه',
            plan_type='monthly',
            price=100000,
            duration_days=30,
            is_active=True,
        )
        buyer = User.objects.create_user(username='kpi_buyer', password='x', phone='09123334455')
        only_buyer = User.objects.create_user(username='kpi_only', password='x', phone='09123334456')
        repurchase_user = User.objects.create_user(username='kpi_rep', password='x', phone='09123334457')

        first = Order.objects.create(
            user=buyer, product=product, plan=plan, amount=plan.price, status='pending',
        )
        fulfill_order_after_payment(first)
        license_obj = License.objects.get(order=first)

        Order.objects.create(
            user=only_buyer, product=product, plan=plan, amount=plan.price, status='paid',
            paid_at=timezone.now() - timedelta(days=40),
        )

        # Formal same-key renewal
        renewal = Order.objects.create(
            user=buyer,
            product=product,
            plan=plan,
            amount=Decimal('90000'),
            status='pending',
            renewal_license=license_obj,
            quantity=1,
        )
        fulfill_order_after_payment(renewal)

        # New-key repurchase (no renewal_license)
        Order.objects.create(
            user=repurchase_user, product=product, plan=plan, amount=plan.price, status='paid',
            paid_at=timezone.now() - timedelta(days=20),
        )
        Order.objects.create(
            user=repurchase_user, product=product, plan=plan, amount=Decimal('80000'), status='paid',
            paid_at=timezone.now(),
        )

        stats = get_licensing_center_stats()
        self.assertEqual(stats['buyers_unique'], 3)
        self.assertEqual(stats['renewed_users'], 2)
        self.assertEqual(stats['renewal_orders'], 2)
        self.assertEqual(stats['formal_renewal_orders'], 1)
        self.assertEqual(stats['new_key_repurchase_orders'], 1)
        self.assertEqual(stats['renewal_rate_pct'], 66.7)
        self.assertEqual(stats['renewal_revenue'], 170000)

        recent = list(get_recent_renewal_orders())
        self.assertEqual(len(recent), 2)
        kinds = {(bool(o.renewal_license_id), o.user_id) for o in recent}
        self.assertIn((True, buyer.id), kinds)
        self.assertIn((False, repurchase_user.id), kinds)

        ctx = get_admin_dashboard_context(days=30)
        self.assertIn('recent_renewals', ctx)
        self.assertEqual(ctx['licensing_stats']['renewed_users'], 2)

    def test_users_active_on_date_web_and_mobile(self):
        from datetime import timedelta

        from django.utils import timezone

        from mobile_api.models import MobileDevice

        today = timezone.now().date()
        web_user = User.objects.create_user(username='web_u', password='x', phone='09120000001')
        web_user.last_login = timezone.now()
        web_user.save(update_fields=['last_login'])

        mobile_user = User.objects.create_user(username='mob_u', password='x', phone='09120000002')
        MobileDevice.objects.create(user=mobile_user, device_id='test-device-1')

        inactive = User.objects.create_user(
            username='old_u', password='x', phone='09120000003', is_active=False,
        )
        inactive.last_login = timezone.now()
        inactive.save(update_fields=['last_login'])

        stale = User.objects.create_user(username='stale_u', password='x', phone='09120000004')
        stale.last_login = timezone.now() - timedelta(days=2)
        stale.save(update_fields=['last_login'])

        self.assertEqual(get_users_active_on_date(today), 2)
        self.assertEqual(get_users_online_count(minutes=15), 1)

    def test_kpi_users_online_today_card(self):
        ctx = get_command_center_context(days=30)
        keys = {c['key'] for c in ctx['kpi_cards']}
        self.assertIn('users_active', keys)
        self.assertIn('retention_30d', keys)
        self.assertEqual(len(ctx['kpi_cards']), 6)
        self.assertIn('users_analytics', ctx)

    def test_command_center_context_slim(self):
        ctx = get_command_center_context(days=30)
        self.assertIn('command_action_items', ctx)
        self.assertIn('revenue_analytics', ctx['charts'])
        self.assertNotIn('order_status', ctx['charts'])
        self.assertEqual(len(ctx['kpi_cards']), 6)

    def test_command_action_items_deduped(self):
        stats = get_command_center_context(days=30)['stats']
        items = build_command_action_items(stats, {'ok': True, 'is_low': False})
        keys = [i['key'] for i in items]
        self.assertEqual(len(keys), len(set(keys)))


class AdminDashboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='admstaff', password='pass1234', phone='09126666666', is_staff=True,
        )
        self.user = User.objects.create_user(
            username='normal2', password='pass1234', phone='09127777777',
        )

    def test_staff_only(self):
        url = reverse('admin_panel')
        self.client.login(username='normal2', password='pass1234')
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (302, 403))

        self.client.login(username='admstaff', password='pass1234')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ecc-kpi-grid--cmd')
        self.assertContains(resp, 'نیازمند اقدام')
        self.assertContains(resp, 'ecc-cmd-actions')
        self.assertContains(resp, 'chart-revenue-analytics')
        self.assertContains(resp, 'ecc-cmd-summary')
        self.assertNotContains(resp, 'ecc-renewals')

    def test_dashboard_with_days_param(self):
        self.client.login(username='admstaff', password='pass1234')
        resp = self.client.get(reverse('admin_panel'), {'days': 7})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'chart-revenue-analytics')
