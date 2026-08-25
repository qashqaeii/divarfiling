"""تست محاسبه کمیسیون، تقسیم مشاور/املاک و داشبورد مالی معاملات."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.constants import DEAL_STAGE_WON, DEFAULT_DEAL_FINANCE
from workspace.models import CRMDeal, Customer
from workspace.services.crm_deal_finance import (
    apply_deal_finance,
    apply_finance_defaults,
    compute_deal_finance,
    finance_dashboard,
    get_finance_defaults,
    save_finance_defaults,
    serialize_deal_finance,
)
from workspace.services.crm_deals import create_deal, update_deal_stage

User = get_user_model()


class DealFinanceServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09120002222', password='test')
        self.customer = Customer.objects.create(
            user=self.user, name='مشتری مالی', phone='09120002222', status='جدید',
        )

    def test_percent_sale_splits_advisor_and_agency(self):
        deal = create_deal(self.user, self.customer, title='فروش ونک', value=10_000_000_000)
        computed = compute_deal_finance(deal)
        self.assertEqual(deal.deal_kind, 'sale')
        self.assertEqual(computed['commission_amount'], 100_000_000)
        self.assertEqual(computed['buyer_commission_amount'], 50_000_000)
        self.assertEqual(computed['seller_commission_amount'], 50_000_000)
        self.assertEqual(computed['advisor_commission'], 70_000_000)
        self.assertEqual(computed['agency_commission'], 30_000_000)
        self.assertEqual(computed['net_advisor'], 70_000_000)

    def test_custom_rates_and_costs(self):
        deal = create_deal(self.user, self.customer, title='فروش سفارشی', value=2_000_000_000)
        apply_deal_finance(deal, {
            'buyer_commission_rate': 1.0,
            'seller_commission_rate': 0.5,
            'advisor_share_percent': 60,
            'agency_share_percent': 40,
            'deal_costs': 5_000_000,
            'received_amount': 10_000_000,
        })
        deal.refresh_from_db()
        self.assertEqual(deal.commission_amount, 30_000_000)
        self.assertEqual(deal.advisor_commission, 18_000_000)
        self.assertEqual(deal.agency_commission, 12_000_000)
        self.assertEqual(serialize_deal_finance(deal)['net_advisor'], 13_000_000)
        self.assertEqual(deal.payout_status, 'partial')
        self.assertEqual(serialize_deal_finance(deal)['outstanding'], 20_000_000)

    def test_fixed_mode(self):
        deal = create_deal(self.user, self.customer, title='مبلغ ثابت', value=1_000_000_000)
        apply_deal_finance(deal, {
            'commission_mode': 'fixed',
            'buyer_commission_amount': 8_000_000,
            'seller_commission_amount': 2_000_000,
            'advisor_share_percent': 50,
            'agency_share_percent': 50,
        })
        deal.refresh_from_db()
        self.assertEqual(deal.commission_amount, 10_000_000)
        self.assertEqual(deal.advisor_commission, 5_000_000)
        self.assertEqual(deal.agency_commission, 5_000_000)

    def test_defaults_persist(self):
        saved = save_finance_defaults(self.user, {
            'sale_buyer_rate': 0.25,
            'sale_seller_rate': 0.25,
            'advisor_share_percent': 80,
            'agency_share_percent': 20,
        })
        self.assertEqual(saved['advisor_share_percent'], 80)
        defaults = get_finance_defaults(self.user)
        self.assertEqual(defaults['sale_buyer_rate'], 0.25)
        deal = CRMDeal(user=self.user, customer=self.customer, title='با پیش‌فرض', value=4_000_000_000)
        apply_finance_defaults(deal, self.user)
        self.assertEqual(deal.buyer_commission_rate, 0.25)
        self.assertEqual(deal.advisor_share_percent, 80)

    def test_dashboard_counts_closed_deals(self):
        deal = create_deal(
            self.user, self.customer, title='بسته', value=1_000_000_000, stage=DEAL_STAGE_WON,
        )
        update_deal_stage(deal, DEAL_STAGE_WON)
        apply_deal_finance(deal, {'payout_status': 'paid', 'received_amount': deal.commission_amount})
        payload = finance_dashboard(self.user, 'all')
        self.assertGreaterEqual(payload['kpis']['closed_count'], 1)
        self.assertEqual(payload['kpis']['volume'], 1_000_000_000)
        self.assertEqual(payload['kpis']['advisor_income'], deal.advisor_commission)
        self.assertTrue(payload['defaults'])
        self.assertEqual(payload['defaults']['advisor_share_percent'], DEFAULT_DEAL_FINANCE['advisor_share_percent'])
