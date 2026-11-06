from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from workspace.models import Customer
from workspace.services.crm_deals import build_deals_kpi_stats, create_deal


User = get_user_model()


class DealsKpiStatsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='kpi_deals', password='x')
        self.customer = Customer.objects.create(
            user=self.user, name='مشتری KPI', phone='09121110000', status='جدید',
        )

    def test_empty(self):
        stats = build_deals_kpi_stats(self.user)
        self.assertEqual(stats['active'], 0)
        self.assertEqual(stats['stale'], 0)
        self.assertEqual(stats['pipeline_value'], 0)
        self.assertEqual(stats['weighted_forecast'], 0)
        self.assertEqual(stats['mix_segments'], [])
        self.assertIn('معامله', stats['hero_meta'])

    def test_advisor_pipeline_kpis(self):
        create_deal(
            self.user, self.customer,
            title='فعال تازه', stage='سرنخ', value=1_000_000_000, probability=20,
        )
        stale = create_deal(
            self.user, self.customer,
            title='راکد', stage='مذاکره', value=2_000_000_000, probability=40,
        )
        stale.stage_changed_at = timezone.now() - timedelta(days=30)
        stale.save(update_fields=['stage_changed_at'])

        stats = build_deals_kpi_stats(self.user)
        self.assertEqual(stats['active'], 2)
        self.assertEqual(stats['stale'], 1)
        self.assertEqual(stats['pipeline_value'], 3_000_000_000)
        self.assertEqual(stats['weighted_forecast'], 1_000_000_000)  # 200M + 800M
        self.assertGreaterEqual(len(stats['mix_segments']), 1)
        self.assertIn('مانده', stats['stale_meta'])
        self.assertGreater(stats['forecast_share'], 0)
