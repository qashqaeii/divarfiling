"""تست مرکز CRM — KPI، Adoption، Action و امنیت."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_crm_center import (
    _customers_new_between,
    _deals_won_between,
    build_crm_action_items,
    get_crm_center_context,
)
from accounts.services.admin_dashboard import _date_range
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active
from workspace.constants import DEAL_STAGE_WON
from workspace.models import CRMDeal, CRMProperty, Customer, Reminder

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran')
class CrmCenterServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='crm1', password='x', phone='09120000201')

    def test_range_kpi_customers_new(self):
        Customer.objects.create(user=self.user, name='علی')
        start, end = _date_range(7)
        self.assertEqual(_customers_new_between(start, end), 1)
        ctx = get_crm_center_context(days=7)
        card = next(c for c in ctx['range_kpi_cards'] if c['key'] == 'customers_new_period')
        self.assertEqual(card['value'], 1)

    def test_deals_won_requires_closed_at(self):
        customer = Customer.objects.create(user=self.user, name='خریدار')
        CRMDeal.objects.create(
            user=self.user,
            customer=customer,
            title='فروش',
            stage=DEAL_STAGE_WON,
            closed_at=timezone.now(),
        )
        start, end = _date_range(7)
        self.assertEqual(_deals_won_between(start, end), 1)

    def test_adoption_stats(self):
        Customer.objects.create(user=self.user, name='مشتری')
        ctx = get_crm_center_context(days=30)
        self.assertGreaterEqual(ctx['adoption']['users_with_customer'], 1)
        self.assertIsNotNone(ctx['adoption']['adoption_pct'])

    def test_action_items_overdue_reminder(self):
        Customer.objects.create(user=self.user, name='c')
        Reminder.objects.create(
            user=self.user,
            title='تماس',
            due_at=timezone.now() - timezone.timedelta(days=1),
        )
        items = build_crm_action_items({'overdue_reminders': 1})
        self.assertTrue(any(i['key'] == 'overdue_reminders' for i in items))

    def test_no_sensitive_data_in_tables(self):
        Customer.objects.create(user=self.user, name='مشتری', phone='09121112222')
        CRMProperty.objects.create(user=self.user, title='ملک تست', phone='09123334444')
        ctx = get_crm_center_context(days=7)
        payload = str(ctx['open_deals_rows']) + str(ctx['active_user_rows'])
        self.assertNotIn('0912', payload)

    def test_charts_keys_when_data_exists(self):
        Customer.objects.create(user=self.user, name='ن')
        ctx = get_crm_center_context(days=7)
        self.assertTrue(ctx['charts_enabled'])
        self.assertIn('crm_usage_trend', ctx['charts'])


@override_settings(TIME_ZONE='Asia/Tehran')
class AdminCrmCenterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='crmstaff', password='pass1234', phone='09120000202', is_staff=True,
        )
        self.user = User.objects.create_user(username='crm2', password='x', phone='09120000203')

    def test_staff_only(self):
        self.assertEqual(self.client.get(reverse('admin_panel_crm')).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('admin_panel_crm')).status_code, 403)

    def test_render_ranges_compare_sidebar(self):
        Customer.objects.create(user=self.user, name='تست')
        self.client.force_login(self.staff)
        for days in ('1', '7', '30', '90'):
            resp = self.client.get(reverse('admin_panel_crm'), {'days': days})
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode()
            self.assertIn('ecc-crm', content)
            self.assertIn(f'data-range="{days}"', content)
            self.assertIn('CRM Adoption', content)

        resp = self.client.get(reverse('admin_panel_crm'), {'days': '30', 'compare': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('compare=1', resp.content.decode())
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/crm/'), 'crm')

    def test_anchor_fallback_in_dashboard(self):
        self.client.force_login(self.staff)
        dash = self.client.get(reverse('admin_panel'), {'days': '7'})
        content = dash.content.decode()
        self.assertIn('/accounts/admin-panel/crm/', content)
        self.assertIn('#ecc-crm', content)

    def test_open_deals_table_render_without_n_plus_one(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        customer = Customer.objects.create(user=self.user, name='c')
        for i in range(3):
            CRMDeal.objects.create(user=self.user, customer=customer, title=f'deal {i}', stage='سرنخ')
        self.client.force_login(self.staff)
        with CaptureQueriesContext(connection) as ctx:
            resp = self.client.get(reverse('admin_panel_crm'), {'days': '30'})
        self.assertEqual(resp.status_code, 200)
        self.assertLess(len(ctx.captured_queries), 100)
        self.assertIn('deal 0', resp.content.decode())
