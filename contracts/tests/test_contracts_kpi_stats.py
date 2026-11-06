from django.contrib.auth import get_user_model
from django.test import TestCase

from contracts.constants import (
    CONTRACT_STATUS_FINALIZED,
    CONTRACT_STATUS_SENT,
    CONTRACT_TYPE_LEASE,
)
from contracts.services.dashboard import build_contracts_kpi_stats, filter_contracts
from contracts.services.lifecycle import create_contract
from contracts.tests.helpers import grant_bot_license
from workspace.models import CRMDeal, CRMProperty, Customer


User = get_user_model()


class ContractsKpiStatsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='kpi_ct', phone='09125550000', password='x')
        grant_bot_license(self.user)
        self.customer = Customer.objects.create(
            user=self.user, name='مشتری قرارداد', phone='09125550001',
        )
        self.prop = CRMProperty.objects.create(user=self.user, title='ملک KPI')
        self.deal = CRMDeal.objects.create(
            user=self.user, customer=self.customer, property=self.prop, title='معامله KPI',
        )

    def test_empty(self):
        stats = build_contracts_kpi_stats(self.user)
        self.assertEqual(stats['total'], 0)
        self.assertEqual(stats['needs_action'], 0)
        self.assertEqual(stats['draft'], 0)
        self.assertEqual(stats['finalized'], 0)
        self.assertEqual(stats['mix_segments'], [])

    def test_advisor_status_kpis_and_focus_filters(self):
        draft = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        pending = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        pending.status = CONTRACT_STATUS_SENT
        pending.save(update_fields=['status'])
        done = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        done.status = CONTRACT_STATUS_FINALIZED
        done.save(update_fields=['status'])

        stats = build_contracts_kpi_stats(self.user)
        self.assertEqual(stats['total'], 3)
        self.assertEqual(stats['draft'], 1)
        self.assertEqual(stats['needs_action'], 1)
        self.assertEqual(stats['pending'], 1)
        self.assertEqual(stats['finalized'], 1)
        self.assertEqual(len(stats['mix_segments']), 3)
        self.assertIn('پیش‌نویس', stats['hero_meta'])

        self.assertEqual(filter_contracts(self.user, {'focus': 'needs'}).count(), 1)
        self.assertEqual(filter_contracts(self.user, {'focus': 'active'}).count(), 2)
        self.assertEqual(filter_contracts(self.user, {'status': 'draft'}).count(), 1)
        self.assertEqual(draft.pk, filter_contracts(self.user, {'status': 'draft'}).get().pk)
