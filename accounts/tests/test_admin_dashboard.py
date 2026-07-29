"""تست داشبورد مدیریت سیستم."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.services.admin_dashboard import (
    build_action_queue,
    get_activity_feed,
    get_admin_dashboard_context,
    get_affiliate_partners,
    get_licensing_center_stats,
    get_plan_sales_breakdown,
    get_recent_affiliate_sales,
    get_recent_renewal_orders,
    get_today_stats,
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

        plans = get_plan_sales_breakdown()
        self.assertEqual(len(plans), 4)
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

    def test_plan_sales_aggregates_by_plan_type(self):
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
        daily = next(p for p in plans if p['plan_type'] == 'daily')
        self.assertEqual(daily['plan_id'], new_plan.id)
        self.assertEqual(daily['count'], 1)
        self.assertEqual(daily['total'], int(old_plan.price))

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
        self.assertContains(resp, 'ecc-kpi-grid')
        self.assertContains(resp, 'تمدید اکانت')
        self.assertContains(resp, 'ecc-renewals')
        self.assertContains(resp, 'مرکز لایسنس')

    def test_dashboard_with_days_param(self):
        self.client.login(username='admstaff', password='pass1234')
        resp = self.client.get(reverse('admin_panel'), {'days': 7})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'chart-revenue-analytics')
