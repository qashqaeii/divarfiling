"""Export permissions, spreadsheet-formula safety, and KPI/export contracts."""
import csv
import io
from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_dashboard import _new_users_for_period
from accounts.services.admin_export_permissions import can_export_report
from accounts.services.admin_exports import (
    _build_csv_response,
    _build_xlsx_response,
    _new_users_rows,
    get_export_count,
)
from accounts.services.admin_exports_center import get_exports_center_context

User = get_user_model()


class ExportAuthorizationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='reportstaff', phone='09121239981', password='pass1234',
            is_staff=True,
        )
        self.owner = User.objects.create_user(
            username='reportowner', phone='09121239982', password='pass1234',
            is_staff=True, is_superuser=True,
        )

    def grant(self, *permissions):
        for app_label, codename in permissions:
            permission = Permission.objects.get(
                content_type__app_label=app_label, codename=codename
            )
            self.staff.user_permissions.add(permission)

    def test_plain_staff_denied_before_builder_is_called(self):
        self.client.force_login(self.staff)
        with patch('accounts.admin_views.build_export') as build:
            resp = self.client.get(reverse('admin_panel_export', args=['all_users']))
        self.assertEqual(resp.status_code, 403)
        build.assert_not_called()

    def test_order_export_requires_order_and_user_view_permissions(self):
        self.grant(('shop', 'view_order'))
        self.client.force_login(self.staff)
        url = reverse('admin_panel_export', args=['paid_orders'])
        self.assertEqual(self.client.get(url).status_code, 403)

        self.grant(('accounts', 'view_user'))
        self.assertTrue(can_export_report(self.staff, 'paid_orders'))
        response = self.client.get(url, {'days': 'all', 'format': 'csv'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_user_view_permission_only_grants_scoped_user_reports(self):
        self.grant(('accounts', 'view_user'))
        ctx = get_exports_center_context(days=7, user=self.staff)
        keys = {item['key'] for item in ctx['export_items']}
        self.assertIn('all_users', keys)
        self.assertNotIn('paid_orders', keys)
        self.assertNotIn('users_management', keys)
        self.assertNotIn('pending_withdrawals', keys)

    def test_owner_access_and_unknown_keys(self):
        self.assertTrue(can_export_report(self.owner, 'pending_withdrawals'))
        self.assertTrue(can_export_report(self.owner, 'ai_usage'))
        self.assertFalse(can_export_report(self.owner, 'nonexistent'))
        self.assertFalse(can_export_report(self.staff, 'ai_usage'))

    def test_staff_only_not_enough_for_financial_exports(self):
        self.grant(('accounts', 'view_user'), ('shop', 'view_order'))
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_export', args=['pending_withdrawals']))
        self.assertEqual(resp.status_code, 403)

    def test_inactive_staff_denied(self):
        self.staff.is_active = False
        self.staff.save(update_fields=['is_active'])
        self.assertFalse(can_export_report(self.staff, 'all_users'))


class SpreadsheetFormulaSafetyTests(TestCase):
    def test_csv_escapes_formula_strings_not_numeric_values(self):
        rows = [
            {'value': '=SUM(1,2)', 'amount': 5},
            {'value': ' +COMMAND(1)', 'amount': -3},
            {'value': '\t@evil', 'amount': 0},
            {'value': 'normal', 'amount': 6},
        ]
        response = _build_csv_response(['value', 'amount'], rows, 'safe')
        parsed = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(parsed[0]['value'], "'=SUM(1,2)")
        self.assertEqual(parsed[1]['value'], "' +COMMAND(1)")
        self.assertEqual(parsed[2]['value'], "'\t@evil")
        self.assertEqual(parsed[3]['value'], 'normal')
        self.assertEqual(parsed[1]['amount'], '-3')
        self.assertEqual(rows[0]['value'], '=SUM(1,2)')

    def test_xlsx_strings_are_not_formula_cells(self):
        from openpyxl import load_workbook

        response = _build_xlsx_response(['value', 'amount'], [
            {'value': '=HYPERLINK("example.com")', 'amount': 7},
            {'value': '@SUM(1,2)', 'amount': 9},
        ], 'safe', 'Sheet')
        wb = load_workbook(io.BytesIO(response.content))
        ws = wb.active
        self.assertEqual(ws['A2'].value, "'=HYPERLINK(\"example.com\")")
        self.assertNotEqual(ws['A2'].data_type, 'f')
        self.assertEqual(ws['A3'].value, "'@SUM(1,2)")
        self.assertEqual(ws['B2'].value, 7)


@override_settings(TIME_ZONE='Asia/Tehran')
class UserKpiExportContractTests(TestCase):
    def test_new_users_export_uses_same_calendar_days_as_dashboard(self):
        today = timezone.now().date()
        current = User.objects.create_user(
            username='calendar_now', phone='09121230001', password='x',
        )
        previous = User.objects.create_user(
            username='calendar_old', phone='09121230002', password='x',
        )
        today_at_noon = timezone.make_aware(datetime.combine(today, time(12, 0)))
        yesterday_at_noon = timezone.make_aware(
            datetime.combine(today - timedelta(days=1), time(12, 0))
        )
        User.objects.filter(pk=current.pk).update(date_joined=today_at_noon)
        User.objects.filter(pk=previous.pk).update(date_joined=yesterday_at_noon)

        _, today_rows = _new_users_rows(days=1)
        self.assertEqual(get_export_count('new_users', days=1), len(today_rows))
        self.assertEqual(_new_users_for_period(1), len(today_rows))
        self.assertEqual(len(today_rows), 1)
