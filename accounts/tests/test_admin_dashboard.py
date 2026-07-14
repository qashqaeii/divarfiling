"""تست داشبورد مدیریت سیستم."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.services.admin_dashboard import (
    build_action_queue,
    get_activity_feed,
    get_admin_dashboard_context,
    get_affiliate_partners,
    get_plan_sales_breakdown,
    get_recent_affiliate_sales,
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
        self.assertContains(resp, 'Executive Command Center')
        self.assertContains(resp, 'ecc-kpi-grid')

    def test_dashboard_with_days_param(self):
        self.client.login(username='admstaff', password='pass1234')
        resp = self.client.get(reverse('admin_panel'), {'days': 7})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'chart-revenue-analytics')
