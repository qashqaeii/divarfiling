"""تست آنالیز تبدیل پلن‌ها."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_plan_conversion import (
    build_plan_conversion_json,
    count_daily_to_monthly_upgrades,
    get_plan_conversion_context,
)
from shop.bot_catalog import bot_license_plans
from shop.models import LicensePlan, Order, PlanFunnelEvent, Product

User = get_user_model()


class PlanConversionServiceTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='ربات تست',
            slug='test-bot-conversion',
            is_active=True,
        )
        self.plans = {}
        for data in bot_license_plans():
            plan = LicensePlan.objects.create(product=self.product, **data)
            self.plans[plan.plan_type] = plan

        self.user_daily = User.objects.create_user(
            username='dailybuyer', password='x', phone='09120000001',
        )
        self.user_upgrade = User.objects.create_user(
            username='upgrader', password='x', phone='09120000002',
        )

    def _paid_order(self, user, plan_type, *, days_ago=1):
        paid_at = timezone.now() - timedelta(days=days_ago)
        return Order.objects.create(
            user=user,
            product=self.product,
            plan=self.plans[plan_type],
            amount=self.plans[plan_type].price,
            status='paid',
            paid_at=paid_at,
        )

    def test_daily_to_monthly_upgrade_within_7_days(self):
        daily = self._paid_order(self.user_upgrade, 'daily', days_ago=10)
        Order.objects.create(
            user=self.user_upgrade,
            product=self.product,
            plan=self.plans['monthly'],
            amount=self.plans['monthly'].price,
            status='paid',
            paid_at=daily.paid_at + timedelta(days=3),
        )
        stats = count_daily_to_monthly_upgrades()
        self.assertEqual(stats['upgrade_count'], 1)
        self.assertEqual(stats['daily_buyers'], 1)
        self.assertEqual(stats['upgrade_rate'], 100.0)

    def test_no_upgrade_after_7_days(self):
        daily = self._paid_order(self.user_daily, 'daily', days_ago=20)
        Order.objects.create(
            user=self.user_daily,
            product=self.product,
            plan=self.plans['monthly'],
            amount=self.plans['monthly'].price,
            status='paid',
            paid_at=daily.paid_at + timedelta(days=10),
        )
        stats = count_daily_to_monthly_upgrades()
        self.assertEqual(stats['upgrade_count'], 0)

    def test_conversion_context_jalali_and_precision(self):
        since = timezone.now() - timedelta(days=5)
        for i in range(5):
            PlanFunnelEvent.objects.create(
                event_type='pricing_view',
                session_key=f'session-{i}',
                product=self.product,
            )
        # backdate created_at if needed — auto_now_add uses now which is fine within 30d
        PlanFunnelEvent.objects.create(
            event_type='checkout_view',
            session_key='checkout-1',
            product=self.product,
        )
        self._paid_order(self.user_daily, 'daily', days_ago=2)
        self._paid_order(self.user_upgrade, 'monthly', days_ago=1)

        ctx = get_plan_conversion_context(days=30)
        summary = ctx['summary']
        self.assertGreaterEqual(summary['pricing_views'], 5)
        self.assertGreaterEqual(summary['daily_purchases'], 1)
        self.assertGreaterEqual(summary['monthly_purchases'], 1)
        self.assertEqual(summary['paid_count'], summary['daily_purchases'] + summary['monthly_purchases']
                         + summary['quarterly_purchases'] + summary['yearly_purchases'])
        self.assertIn('period_start_jalali', summary)
        self.assertIn('/', summary['period_start_jalali'])
        self.assertIn('funnel_stages', summary)
        self.assertIn('aov', summary)

        charts = ctx['charts']
        self.assertIn('labels', charts['funnel_daily'])
        self.assertEqual(len(charts['funnel_daily']['labels']), 30)
        self.assertEqual(len(charts['funnel_daily']['pricing_counts']), 30)

        daily_row = next(r for r in ctx['plan_rows'] if r['plan_type'] == 'daily')
        self.assertGreaterEqual(daily_row['purchases'], 1)
        self.assertIn('aov', daily_row)

        if ctx['cohorts']:
            self.assertIn('week_jalali', ctx['cohorts'][0])
            self.assertIn('week_label', ctx['cohorts'][0])

        payload = build_plan_conversion_json(days=30)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['meta']['version'], '1.1')
        self.assertIn('summary', payload)
        self.assertIn('plans', payload)
        self.assertIn('charts', payload)


class AdminPlanConversionPanelTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staffconv', password='pass1234', phone='09123333333', is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)

    def test_panel_requires_staff(self):
        guest = Client()
        resp = guest.get(reverse('admin_panel_plan_conversion'))
        self.assertEqual(resp.status_code, 302)

    def test_panel_loads(self):
        resp = self.client.get(reverse('admin_panel_plan_conversion'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'آنالیز')
        self.assertContains(resp, 'apc-chart-funnel')
        self.assertContains(resp, 'admPlanConversion')
        self.assertContains(resp, 'apc-gauge')
        self.assertContains(resp, 'دانلود JSON')
        self.assertContains(resp, 'apc-funnel-viz')

    def test_json_endpoint(self):
        resp = self.client.get(reverse('admin_panel_plan_conversion_json'), {'days': 30})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('summary', data)
        self.assertIn('period_start_jalali', data['meta'])

    def test_json_download(self):
        resp = self.client.get(
            reverse('admin_panel_plan_conversion_json'),
            {'days': 7, 'download': '1'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment', resp.get('Content-Disposition', ''))
