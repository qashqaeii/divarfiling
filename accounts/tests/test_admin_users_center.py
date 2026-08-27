"""تست مرکز کاربران — Range، Snapshot، API و Render."""
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_dashboard import (
    _date_range,
    _new_users_for_period,
    _previous_period_bounds,
)
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active
from accounts.services.admin_users_center import (
    _users_active_between,
    get_users_center_context,
)

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran')
class UsersCenterServiceTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.user = User.objects.create_user(username='uc1', password='x', phone='09120000021')

    def test_new_users_respects_range(self):
        User.objects.create_user(username='uc2', password='x', phone='09120000022')
        old = User.objects.create_user(username='uc3', password='x', phone='09120000023')
        old.date_joined = timezone.make_aware(datetime.combine(self.today - timedelta(days=20), time(9, 0)))
        old.save(update_fields=['date_joined'])

        ctx7 = get_users_center_context(days=7)
        ctx30 = get_users_center_context(days=30)
        kpi7 = next(c for c in ctx7['range_kpi_cards'] if c['key'] == 'users_new_period')
        kpi30 = next(c for c in ctx30['range_kpi_cards'] if c['key'] == 'users_new_period')

        self.assertEqual(kpi7['value'], _new_users_for_period(7))
        self.assertEqual(kpi30['value'], _new_users_for_period(30))
        self.assertNotEqual(kpi7['value'], kpi30['value'])

    def test_snapshot_kpis_present(self):
        ctx = get_users_center_context(days=30)
        keys = {c['key'] for c in ctx['snapshot_kpi_cards']}
        self.assertIn('users_total', keys)
        self.assertIn('users_without_license', keys)
        self.assertIn('online_today', keys)
        for card in ctx['snapshot_kpi_cards']:
            self.assertEqual(card['kind'], 'snapshot')

    def test_active_users_in_range(self):
        self.user.last_login = timezone.make_aware(datetime.combine(self.today, time(10, 0)))
        self.user.save(update_fields=['last_login'])
        start, end = _date_range(7)
        ctx = get_users_center_context(days=7)
        kpi = next(c for c in ctx['range_kpi_cards'] if c['key'] == 'users_active_period')
        self.assertEqual(kpi['value'], _users_active_between(start, end))

    def test_previous_period_same_length(self):
        start, end = _date_range(30)
        prev_start, prev_end = _previous_period_bounds(30)
        self.assertEqual((end - start).days + 1, (prev_end - prev_start).days + 1)

    def test_recent_and_no_license_tables(self):
        ctx = get_users_center_context(days=30)
        self.assertGreaterEqual(len(ctx['recent_users']), 1)
        self.assertIn('users_without_license_list', ctx)


@override_settings(TIME_ZONE='Asia/Tehran')
class AdminUsersCenterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='ucstaff', password='pass1234', phone='09127777771', is_staff=True,
        )
        self.user = User.objects.create_user(
            username='uctarget', password='pass1234', phone='09127777772',
        )

    def test_staff_only(self):
        resp = self.client.get(reverse('admin_panel_users'))
        self.assertEqual(resp.status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('admin_panel_users')).status_code, 403)

    def test_template_render_and_sidebar(self):
        self.client.force_login(self.staff)
        for days in ('1', '7', '30', '90'):
            resp = self.client.get(reverse('admin_panel_users'), {'days': days})
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode()
            self.assertIn('مدیریت کاربران', content)
            self.assertIn('ecc-users-mgmt', content)
            self.assertIn('chart-signups', content)
            self.assertIn('chart-users-active', content)
            self.assertIn(f'data-range="{days}"', content)
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/users/'), 'users')

    def test_compare_query(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_users'), {'days': '30', 'compare': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('compare=1', resp.content.decode())

    def test_ajax_users_api_and_drawer_urls(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_users'))
        content = resp.content.decode()
        self.assertIn(reverse('admin_panel_users_json'), content)
        self.assertIn('.json', content)
        list_resp = self.client.get(reverse('admin_panel_users_json'), {'q': '09127777772'})
        self.assertEqual(list_resp.status_code, 200)
        self.assertTrue(list_resp.json()['ok'])
        detail_resp = self.client.get(reverse('admin_panel_user_detail_json', args=[self.user.id]))
        self.assertEqual(detail_resp.status_code, 200)
        self.assertTrue(detail_resp.json()['ok'])

    def test_ecc_users_hash_redirect(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel'), {'days': '7'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('/accounts/admin-panel/users/', resp.content.decode())
