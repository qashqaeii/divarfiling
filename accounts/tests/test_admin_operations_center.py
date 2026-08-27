"""تست مرکز عملیات — Health، KPI، Backup و Render."""
from datetime import datetime, time

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import SmsMessageLog
from accounts.services.admin_dashboard import _date_range, _previous_period_bounds
from accounts.services.admin_operations_center import (
    _datasets_in_range,
    _sms_in_range,
    build_operations_health,
    get_operations_center_context,
)
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active
from workspace.models import Dataset

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran')
class OperationsCenterServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ops1', password='x', phone='09120000041')

    def test_health_items_from_real_checks(self):
        ctx = get_operations_center_context(days=30)
        keys = {h['key'] for h in ctx['system_health']}
        self.assertIn('app', keys)
        self.assertIn('database', keys)
        self.assertIn('sms', keys)
        self.assertIn('backup', keys)
        for h in ctx['system_health']:
            self.assertIn(h['status'], ('ok', 'warning', 'critical'))

    def test_range_kpis_match_queries(self):
        SmsMessageLog.objects.create(phone='09121111111', purpose='test', status=SmsMessageLog.Status.SENT)
        start, end = _date_range(7)
        ctx = get_operations_center_context(days=7)
        sms_kpi = next(c for c in ctx['range_kpi_cards'] if c['key'] == 'sms_sent_period')
        self.assertEqual(sms_kpi['value'], _sms_in_range(start, end))

    def test_snapshot_kpis(self):
        ctx = get_operations_center_context(days=30)
        keys = {c['key'] for c in ctx['snapshot_kpi_cards']}
        self.assertIn('sms_balance', keys)
        self.assertIn('datasets_total', keys)
        self.assertIn('system_uptime', keys)

    def test_backup_info_excludes_sensitive_fields(self):
        ctx = get_operations_center_context(days=30)
        self.assertNotIn('database_name', ctx['backup_info'])

    def test_previous_period_same_length(self):
        start, end = _date_range(30)
        prev_start, prev_end = _previous_period_bounds(30)
        self.assertEqual((end - start).days + 1, (prev_end - prev_start).days + 1)

    def test_dataset_period_count(self):
        Dataset.objects.create(
            user=self.user,
            name='d1',
            original_filename='d1.csv',
            file_format='csv',
        )
        start, end = _date_range(30)
        self.assertEqual(_datasets_in_range(start, end), 1)


@override_settings(TIME_ZONE='Asia/Tehran')
class AdminOperationsCenterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='opsstaff', password='pass1234', phone='09127777791', is_staff=True,
        )

    def test_staff_only(self):
        self.assertEqual(self.client.get(reverse('admin_panel_operations')).status_code, 302)
        user = User.objects.create_user(username='noops', password='x', phone='09127777792')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('admin_panel_operations')).status_code, 403)

    def test_template_render_range_health_backup(self):
        self.client.force_login(self.staff)
        for days in ('1', '7', '30', '90'):
            resp = self.client.get(reverse('admin_panel_operations'), {'days': days})
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode()
            self.assertIn('ops-health', content)
            self.assertIn('ops-backup', content)
            self.assertIn(f'data-range="{days}"', content)
            self.assertIn(reverse('admin_panel_system_summary'), content)
            self.assertIn(reverse('admin_panel_database_backup'), content)
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/operations/'), 'operations')

    def test_compare_and_anchor_fallback(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_operations'), {'days': '30', 'compare': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('compare=1', resp.content.decode())
        dash = self.client.get(reverse('admin_panel'), {'days': '7'})
        self.assertIn('/accounts/admin-panel/operations/', dash.content.decode())

    def test_health_build_with_sms_error(self):
        health = build_operations_health(
            sms_balance={'error': 'خطا', 'ok': False},
            backup_info={'engine': 'django.db.backends.sqlite3', 'default_label': 'SQLite'},
            open_tickets=0,
            unread_tickets=0,
        )
        sms = next(h for h in health if h['key'] == 'sms')
        self.assertEqual(sms['status'], 'critical')
