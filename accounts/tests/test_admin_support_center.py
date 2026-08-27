"""تست مرکز پشتیبانی — Action items، KPI، Tables و Render."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_dashboard import _date_range, _previous_period_bounds
from accounts.services.admin_operations_center import get_operations_center_context
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active
from accounts.services.admin_support_center import (
    _snapshot_counts,
    _tickets_created_between,
    build_support_action_items,
    get_support_center_context,
)
from affiliates.models import Affiliate, Wallet, Withdrawal
from shop.models import CardTransferSubmission, LicensePlan, Order, Product
from workspace.models import Ticket

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran')
class SupportCenterServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sup1', password='x', phone='09120000051')

    def test_snapshot_counts(self):
        Ticket.objects.create(
            user=self.user,
            ticket_number='T-1001',
            subject='تست',
            category='other',
            status='open',
            staff_has_unread=True,
        )
        snap = _snapshot_counts()
        self.assertEqual(snap['open_tickets'], 1)
        self.assertEqual(snap['unread_tickets'], 1)

    def test_range_tickets_created(self):
        Ticket.objects.create(
            user=self.user,
            ticket_number='T-1002',
            subject='جدید',
            category='other',
        )
        start, end = _date_range(7)
        ctx = get_support_center_context(days=7)
        kpi = next(c for c in ctx['range_kpi_cards'] if c['key'] == 'tickets_created_period')
        self.assertEqual(kpi['value'], _tickets_created_between(start, end))

    def test_action_items_only_when_count_positive(self):
        snap = {'open_tickets': 0, 'unread_tickets': 0, 'pending_card_transfers': 0, 'pending_withdrawals': 0}
        self.assertEqual(build_support_action_items(snap), [])

    def test_action_items_with_unread(self):
        Ticket.objects.create(
            user=self.user,
            ticket_number='T-1003',
            subject='خوانده نشده',
            category='other',
            staff_has_unread=True,
        )
        items = build_support_action_items(_snapshot_counts())
        self.assertTrue(any(i['key'] == 'unread_tickets' for i in items))

    def test_export_and_admin_urls_in_context(self):
        ctx = get_support_center_context(days=30)
        self.assertIn('open_tickets', ctx['export_urls'])
        self.assertIn('/admin/workspace/ticket/', ctx['admin_list_urls']['tickets'])

    def test_previous_period_same_length(self):
        start, end = _date_range(30)
        prev_start, prev_end = _previous_period_bounds(30)
        self.assertEqual((end - start).days + 1, (prev_end - prev_start).days + 1)


@override_settings(TIME_ZONE='Asia/Tehran')
class AdminSupportCenterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='supstaff', password='pass1234', phone='09127777801', is_staff=True,
        )
        self.user = User.objects.create_user(username='supu', password='x', phone='09127777802')

    def test_staff_only(self):
        self.assertEqual(self.client.get(reverse('admin_panel_support')).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('admin_panel_support')).status_code, 403)

    def test_template_render_tables_cta(self):
        Ticket.objects.create(
            user=self.user,
            ticket_number='T-2001',
            subject='باز',
            category='other',
            staff_has_unread=True,
        )
        product = Product.objects.create(title='P', slug='sup-p', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='م', plan_type='monthly', price=100000, duration_days=30, is_active=True,
        )
        order = Order.objects.create(
            user=self.user, product=product, plan=plan, amount=100000, status='pending_payment',
        )
        CardTransferSubmission.objects.create(
            order=order, reference_number='REF1', status='pending',
        )
        aff_user = User.objects.create_user(username='aff1', password='x', phone='09127777803')
        affiliate = Affiliate.objects.create(user=aff_user, code='AFF1', is_active=True)
        wallet = Wallet.objects.create(user=aff_user, balance=100000)
        Withdrawal.objects.create(
            wallet=wallet,
            amount=50000,
            bank_account='123',
            bank_name='ملی',
            account_holder='تست',
            status='pending',
        )

        self.client.force_login(self.staff)
        for days in ('1', '7', '30', '90'):
            resp = self.client.get(reverse('admin_panel_support'), {'days': days})
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode()
            self.assertIn('support-table-tickets', content)
            self.assertIn('support-table-card', content)
            self.assertIn('support-table-withdrawals', content)
            self.assertIn(f'data-range="{days}"', content)
            self.assertIn(reverse('admin_panel_export', args=['open_tickets']), content)
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/support/'), 'support')

    def test_compare_and_anchor_fallback(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_support'), {'days': '30', 'compare': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('compare=1', resp.content.decode())
        dash = self.client.get(reverse('admin_panel'), {'days': '7'})
        self.assertIn('/accounts/admin-panel/support/', dash.content.decode())

    def test_operations_links_to_support(self):
        Ticket.objects.create(
            user=self.user,
            ticket_number='T-3001',
            subject='unread',
            category='other',
            staff_has_unread=True,
        )
        ctx = get_operations_center_context(days=30)
        unread_item = next(i for i in ctx['action_items'] if i['key'] == 'unread_tickets')
        self.assertIn('/accounts/admin-panel/support/', unread_item['href'])
