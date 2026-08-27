"""تست مرکز همکاری در فروش — KPI، Action و امنیت."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_affiliates_center import (
    build_affiliate_action_items,
    get_affiliates_center_context,
)
from accounts.services.admin_dashboard import _date_range
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active
from affiliates.models import Affiliate, AffiliateSale, Wallet, Withdrawal
from shop.models import LicensePlan, Order, Product

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran')
class AffiliatesCenterServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='affbuyer', password='x', phone='09120000301')
        self.aff_user = User.objects.create_user(username='affpartner', password='x', phone='09120000302')
        self.affiliate = Affiliate.objects.create(user=self.aff_user, code='AFFX1', is_active=True)

    def test_snapshot_kpi_active_affiliate(self):
        ctx = get_affiliates_center_context(days=7)
        card = next(c for c in ctx['snapshot_kpi_cards'] if c['key'] == 'affiliates_active')
        self.assertGreaterEqual(card['value'], 1)

    def test_range_kpi_sales_in_period(self):
        product = Product.objects.create(title='P', slug='aff-p', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='م', plan_type='monthly', price=100000, duration_days=30, is_active=True,
        )
        order = Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=100000,
            status='paid',
            paid_at=timezone.now(),
        )
        AffiliateSale.objects.create(
            affiliate=self.affiliate,
            order=order,
            commission_rate=10,
            commission_amount=10000,
            status='paid',
        )
        start, end = _date_range(7)
        self.assertGreaterEqual(
            AffiliateSale.objects.filter(status='paid', created_at__date__gte=start, created_at__date__lte=end).count(),
            1,
        )
        ctx = get_affiliates_center_context(days=7)
        card = next(c for c in ctx['range_kpi_cards'] if c['key'] == 'sales_paid_period')
        self.assertGreaterEqual(card['value'], 1)

    def test_action_item_pending_withdrawal(self):
        wallet = Wallet.objects.create(user=self.aff_user, balance=50000)
        Withdrawal.objects.create(
            wallet=wallet,
            amount=20000,
            bank_account='123',
            bank_name='ملی',
            account_holder='تست',
            status='pending',
        )
        items = build_affiliate_action_items({'pending_withdrawals': 1})
        self.assertTrue(any(i['key'] == 'pending_withdrawals' for i in items))

    def test_no_phone_in_serialized_rows(self):
        wallet = Wallet.objects.create(user=self.aff_user, balance=50000)
        Withdrawal.objects.create(
            wallet=wallet,
            amount=20000,
            bank_account='1234567890',
            bank_name='ملی',
            account_holder='تست',
            status='pending',
        )
        ctx = get_affiliates_center_context(days=7)
        payload = str(ctx['partner_rows']) + str(ctx['withdrawal_rows'])
        self.assertNotIn('0912', payload)
        self.assertNotIn('1234567890', payload)


@override_settings(TIME_ZONE='Asia/Tehran')
class AdminAffiliatesCenterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='affstaff', password='pass1234', phone='09120000303', is_staff=True,
        )
        self.user = User.objects.create_user(username='affnorm', password='x', phone='09120000304')

    def test_staff_only(self):
        self.assertEqual(self.client.get(reverse('admin_panel_affiliates')).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('admin_panel_affiliates')).status_code, 403)

    def test_render_ranges_compare_sidebar(self):
        Affiliate.objects.create(user=self.user, code='AFFV1', is_active=True)
        self.client.force_login(self.staff)
        for days in ('1', '7', '30', '90'):
            resp = self.client.get(reverse('admin_panel_affiliates'), {'days': days})
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode()
            self.assertIn('ecc-affiliates', content)
            self.assertIn(f'data-range="{days}"', content)
            self.assertIn('affiliate-withdrawals', content)

        resp = self.client.get(reverse('admin_panel_affiliates'), {'days': '30', 'compare': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('compare=1', resp.content.decode())
        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/affiliates/'), 'affiliates')

    def test_anchor_fallback_in_dashboard(self):
        self.client.force_login(self.staff)
        dash = self.client.get(reverse('admin_panel'), {'days': '7'})
        content = dash.content.decode()
        self.assertIn('/accounts/admin-panel/affiliates/', content)
        self.assertIn('#ecc-affiliates', content)
