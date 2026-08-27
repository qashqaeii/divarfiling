"""تست Range/Compare مرکز فرمان."""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_dashboard import (
    _date_range,
    _new_users_for_period,
    _orders_paid_for_period,
    _previous_period_bounds,
    _revenue_for_period,
    get_command_center_context,
)
from accounts.services.admin_panel_shell import parse_admin_panel_range
from shop.models import LicensePlan, Order, Product

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran')
class CommandCenterRangeHelperTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='P', slug='range-p', is_active=True)
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='ماهانه',
            plan_type='monthly',
            price=100000,
            duration_days=30,
            is_active=True,
        )
        self.today = timezone.localdate()

    def _paid_order(self, user, day, amount=100000):
        paid_at = timezone.make_aware(datetime.combine(day, time(12, 0)))
        return Order.objects.create(
            user=user,
            product=self.product,
            plan=self.plan,
            amount=Decimal(amount),
            status='paid',
            paid_at=paid_at,
        )

    def test_today_window_is_single_calendar_day(self):
        start, end = _date_range(1)
        self.assertEqual(start, self.today)
        self.assertEqual(end, self.today)

    def test_seven_day_window_length(self):
        start, end = _date_range(7)
        self.assertEqual((end - start).days + 1, 7)

    def test_previous_window_same_length_as_current(self):
        curr_len = (_date_range(30)[1] - _date_range(30)[0]).days + 1
        prev_start, prev_end = _previous_period_bounds(30)
        prev_len = (prev_end - prev_start).days + 1
        self.assertEqual(curr_len, prev_len)

    def test_today_differs_from_seven_days(self):
        user = User.objects.create_user(username='u1', password='x', phone='09120000001')
        self._paid_order(user, self.today, 50000)
        self._paid_order(user, self.today - timedelta(days=3), 50000)

        self.assertEqual(_revenue_for_period(1), 50000)
        self.assertEqual(_revenue_for_period(7), 100000)

    def test_new_users_delta_is_range_aware(self):
        User.objects.create_user(username='u2', password='x', phone='09120000002')
        User.objects.create_user(username='u3', password='x', phone='09120000003')
        old = User.objects.create_user(username='u4', password='x', phone='09120000004')
        old.date_joined = timezone.make_aware(datetime.combine(self.today - timedelta(days=10), time(9, 0)))
        old.save(update_fields=['date_joined'])

        ctx7 = get_command_center_context(days=7)
        ctx30 = get_command_center_context(days=30)
        kpi7 = next(c for c in ctx7['kpi_cards'] if c['key'] == 'users_new_period')
        kpi30 = next(c for c in ctx30['kpi_cards'] if c['key'] == 'users_new_period')

        self.assertEqual(kpi7['value'], _new_users_for_period(7))
        self.assertEqual(kpi30['value'], _new_users_for_period(30))
        self.assertNotEqual(kpi7['value'], kpi30['value'])

    def test_orders_paid_respects_range(self):
        user = User.objects.create_user(username='u5', password='x', phone='09120000005')
        self._paid_order(user, self.today)
        self._paid_order(user, self.today - timedelta(days=20))

        self.assertEqual(_orders_paid_for_period(7), 1)
        self.assertEqual(_orders_paid_for_period(30), 2)


@override_settings(TIME_ZONE='Asia/Tehran')
class CommandCenterRangeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='admstaff', password='pass1234', phone='09126666666', is_staff=True,
        )
        self.client.login(username='admstaff', password='pass1234')

    def test_parse_admin_panel_range_today(self):
        factory = RequestFactory()
        request = factory.get('/accounts/admin-panel/', {'days': '1'})
        days, key = parse_admin_panel_range(request)
        self.assertEqual(days, 1)
        self.assertEqual(key, '1')

    def test_only_one_range_button_active_for_90(self):
        resp = self.client.get(reverse('admin_panel'), {'days': '90'})
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        active_count = content.count('ecc-range-btn is-active')
        self.assertEqual(active_count, 1)
        self.assertIn('data-range="90"', content)
        self.assertIn('ecc-range-btn is-active', content)

    def test_compare_preserved_in_range_links(self):
        resp = self.client.get(reverse('admin_panel'), {'days': '30', 'compare': '1'})
        self.assertContains(resp, '?days=7&amp;compare=1')

    def test_retention_label_fixed_30d(self):
        resp = self.client.get(reverse('admin_panel'), {'days': '1'})
        self.assertContains(resp, 'Retention 30 روزه')

    def test_new_users_sublabel_for_30_days(self):
        resp = self.client.get(reverse('admin_panel'), {'days': '30'})
        self.assertContains(resp, 'ثبت‌نام در 30 روز اخیر')

    def test_snapshot_kpi_labels(self):
        resp = self.client.get(reverse('admin_panel'), {'days': '7'})
        self.assertContains(resp, 'وضعیت فعلی')
