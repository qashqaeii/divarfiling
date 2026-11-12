"""فاز ۱ پنل مدیریت — تطابق خروجی، صف فرمان، کوهورت تبدیل."""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_command_queues import (
    build_command_action_items,
    count_fulfillment_incomplete,
    qs_orders_failed_today,
    qs_orders_pending,
)
from accounts.services.admin_dashboard import (
    ALL_TIME_DAYS,
    _orders_paid_for_period,
    _revenue_for_period,
    get_plan_sales_breakdown,
    paid_orders_queryset_for_panel_days,
)
from accounts.services.admin_exports import _paid_orders_rows, get_export_count
from accounts.services.admin_sales_center import get_sales_center_context
from accounts.services.admin_panel_shell import format_admin_panel_days_param
from shop.models import LicensePlan, Order, Product

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran')
class PaidOrdersExportAlignmentTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='خروجی', slug='export-p', is_active=True)
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=200000,
            duration_days=30,
            is_active=True,
        )
        self.today = timezone.localdate()
        self.buyer = User.objects.create_user(username='exbuyer', password='x', phone='09121110001')

    def _paid(self, day, amount=150000):
        paid_at = timezone.make_aware(datetime.combine(day, time(11, 0)))
        return Order.objects.create(
            user=self.buyer,
            product=self.product,
            plan=self.plan,
            amount=Decimal(amount),
            status='paid',
            paid_at=paid_at,
        )

    def _export_total(self, days: int) -> tuple[int, int]:
        _, rows = _paid_orders_rows(days=days)
        total = sum(r['مبلغ (تومان)'] for r in rows)
        return len(rows), total

    def test_today_export_matches_kpi(self):
        self._paid(self.today, 100000)
        self._paid(self.today - timedelta(days=3), 300000)

        kpi_count = _orders_paid_for_period(1)
        kpi_revenue = _revenue_for_period(1)
        ex_count, ex_total = self._export_total(1)

        self.assertEqual(ex_count, kpi_count)
        self.assertEqual(ex_count, paid_orders_queryset_for_panel_days(1).count())
        self.assertEqual(ex_total, kpi_revenue)
        self.assertEqual(get_export_count('paid_orders', days=1), kpi_count)

    def test_all_time_export_matches_kpi(self):
        self._paid(self.today, 120000)
        self._paid(self.today - timedelta(days=40), 80000)

        kpi_count = _orders_paid_for_period(ALL_TIME_DAYS)
        kpi_revenue = _revenue_for_period(ALL_TIME_DAYS)
        ex_count, ex_total = self._export_total(ALL_TIME_DAYS)

        self.assertEqual(ex_count, kpi_count)
        self.assertEqual(ex_total, kpi_revenue)
        self.assertEqual(get_export_count('paid_orders', days=ALL_TIME_DAYS), kpi_count)


@override_settings(TIME_ZONE='Asia/Tehran')
class ConversionCohortTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='تبدیل', slug='conv-p', is_active=True)
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=100000,
            duration_days=30,
            is_active=True,
        )
        self.today = timezone.localdate()
        paid_at = timezone.make_aware(datetime.combine(self.today, time(14, 0)))

        self.new_user = User.objects.create_user(username='newu', password='x', phone='09122220001')
        Order.objects.create(
            user=self.new_user,
            product=self.product,
            plan=self.plan,
            amount=Decimal(100000),
            status='paid',
            paid_at=paid_at,
        )

        old_user = User.objects.create_user(username='oldu', password='x', phone='09122220002')
        old_user.date_joined = timezone.make_aware(datetime.combine(self.today - timedelta(days=90), time(9, 0)))
        old_user.save(update_fields=['date_joined'])
        Order.objects.create(
            user=old_user,
            product=self.product,
            plan=self.plan,
            amount=Decimal(100000),
            status='paid',
            paid_at=paid_at,
        )

    def test_conversion_only_signup_cohort_not_legacy_buyers(self):
        ctx = get_sales_center_context(days=7)
        conv = next(c for c in ctx['kpi_cards'] if c['key'] == 'conversion_rate')
        self.assertEqual(conv['value'], 100.0)

    def test_legacy_buyer_does_not_inflate_conversion(self):
        ctx = get_sales_center_context(days=7)
        conv = next(c for c in ctx['kpi_cards'] if c['key'] == 'conversion_rate')
        buyers_card = next(c for c in ctx['kpi_cards'] if c['key'] == 'unique_buyers')
        self.assertEqual(conv['value'], 100.0)
        self.assertEqual(buyers_card['value'], 2)


@override_settings(TIME_ZONE='Asia/Tehran')
class PlanSalesAndCommandQueueTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='پلن', slug='plan-p', is_active=True)
        self.user = User.objects.create_user(username='pbuy', password='x', phone='09123330001')

    def test_two_active_plans_same_type_separate_totals(self):
        plan_a = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه الف',
            plan_type='monthly',
            price=100000,
            duration_days=30,
            is_active=True,
        )
        plan_b = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه ب',
            plan_type='monthly',
            price=120000,
            duration_days=30,
            is_active=True,
        )
        Order.objects.create(
            user=self.user, product=self.product, plan=plan_a,
            amount=Decimal(100000), status='paid', paid_at=timezone.now(),
        )
        Order.objects.create(
            user=self.user, product=self.product, plan=plan_b,
            amount=Decimal(120000), status='paid', paid_at=timezone.now(),
        )

        rows = {p['plan_id']: p for p in get_plan_sales_breakdown()}
        self.assertEqual(rows[plan_a.id]['count'], 1)
        self.assertEqual(rows[plan_b.id]['count'], 1)

    def test_inactive_plan_with_sales_still_listed(self):
        from shop.bot_catalog import bot_license_plans

        plan_data = bot_license_plans()[0]
        old = LicensePlan.objects.create(product=self.product, **plan_data)
        Order.objects.create(
            user=self.user,
            product=self.product,
            plan=old,
            amount=old.price,
            status='paid',
            paid_at=timezone.now(),
        )
        old.is_active = False
        old.save(update_fields=['is_active'])
        LicensePlan.objects.create(product=self.product, **plan_data)

        row = next(p for p in get_plan_sales_breakdown() if p['plan_id'] == old.id)
        self.assertEqual(row['count'], 1)

    def test_failed_today_queue_excludes_yesterday(self):
        today = timezone.localdate()
        plan = LicensePlan.objects.create(
            product=self.product,
            name='روزانه',
            plan_type='daily',
            price=10000,
            duration_days=1,
            is_active=True,
        )
        buyer_today = User.objects.create_user(username='ftoday', password='x', phone='09124440001')
        buyer_old = User.objects.create_user(username='fold', password='x', phone='09124440002')
        o_today = Order.objects.create(
            user=buyer_today,
            product=self.product,
            plan=plan,
            amount=Decimal(10000),
            status='failed',
        )
        o_old = Order.objects.create(
            user=buyer_old,
            product=self.product,
            plan=plan,
            amount=Decimal(10000),
            status='failed',
        )
        Order.objects.filter(pk=o_today.pk).update(
            created_at=timezone.make_aware(datetime.combine(today, time(10, 0))),
        )
        Order.objects.filter(pk=o_old.pk).update(
            created_at=timezone.make_aware(datetime.combine(today - timedelta(days=1), time(10, 0))),
        )
        self.assertEqual(qs_orders_failed_today().count(), 1)

    def test_fulfillment_queue_matches_sales_context(self):
        plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=100000,
            duration_days=30,
            is_active=True,
        )
        Order.objects.create(
            user=self.user,
            product=self.product,
            plan=plan,
            amount=Decimal(100000),
            status='paid',
            paid_at=timezone.now(),
            fulfillment_status=Order.FulfillmentStatus.PENDING,
        )
        ctx = get_sales_center_context(days=7)
        self.assertEqual(ctx['fulfillment_incomplete_count'], count_fulfillment_incomplete())
        item = next(
            (i for i in build_command_action_items(sms_balance={'ok': True, 'is_low': False}) if i['key'] == 'fulfillment_incomplete'),
            None,
        )
        self.assertIsNotNone(item)
        self.assertEqual(item['count'], count_fulfillment_incomplete())


@override_settings(TIME_ZONE='Asia/Tehran')
class AdminPanelPhase1ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='phase1staff', password='pass1234', phone='09128880088', is_staff=True,
        )
        self.client.login(username='phase1staff', password='pass1234')

    def test_command_kpi_tiers_render(self):
        resp = self.client.get(reverse('admin_panel'), {'days': '7'})
        self.assertContains(resp, 'گزارش بازه')
        self.assertContains(resp, 'وضعیت فعلی')
        self.assertContains(resp, 'مشاهده‌شده امروز')
        self.assertContains(resp, 'کاربران قدیمی فعال')

    def test_paid_orders_export_http_all_days_param(self):
        url = reverse('admin_panel_export', args=['paid_orders'])
        resp = self.client.get(url, {'format': 'xlsx', 'days': 'all'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(format_admin_panel_days_param(ALL_TIME_DAYS), 'all')
