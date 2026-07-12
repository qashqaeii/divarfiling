"""تست داشبورد مدیریت سیستم."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.services.admin_dashboard import (
    build_action_queue,
    get_activity_feed,
    get_admin_dashboard_context,
    get_affiliate_partners,
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
        self.assertContains(resp, 'مرکز فرمان')
        self.assertContains(resp, 'همکاری در فروش')
        self.assertContains(resp, 'adm-tbl-box')

    def test_dashboard_with_days_param(self):
        self.client.login(username='admstaff', password='pass1234')
        resp = self.client.get(reverse('admin_panel'), {'days': 7})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'chart-revenue')
