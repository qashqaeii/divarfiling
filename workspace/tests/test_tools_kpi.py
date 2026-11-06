"""تست KPI پریمیوم صفحه ابزارهای هوشمند."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import Dataset, Listing
from workspace.services.tools import build_tools_kpi_stats

User = get_user_model()


class ToolsKpiStatsTests(TestCase):
    def test_empty_snapshot(self):
        kpi = build_tools_kpi_stats(None)
        self.assertFalse(kpi['has_dataset'])
        self.assertEqual(kpi['rows'], 0)
        self.assertEqual(kpi['ratio_display'], '—')

    def test_rent_snapshot_fields(self):
        kpi = build_tools_kpi_stats({
            'dataset_name': 'فایل اجاره نمونه',
            'transaction_type': 'اجاره',
            'row_count': 42,
            'ratio': 30,
            'is_rent': True,
            'median_pps': 8_000_000,
            'median_area': 85,
            'pps_p10': 5_000_000,
            'pps_p25': 6_000_000,
            'pps_p75': 9_000_000,
            'pps_p90': 12_000_000,
        })
        self.assertTrue(kpi['has_dataset'])
        self.assertEqual(kpi['rows'], 42)
        self.assertIn('30', kpi['ratio_display'])
        self.assertTrue(kpi['price_has_value'])
        self.assertTrue(kpi['area_has_value'])
        self.assertEqual(len(kpi['mix_segments']), 4)


@patch('workspace.mixins.has_active_bot_license', return_value=True)
class ToolsPageKpiRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09129990011',
            phone='09129990011',
            password='pass12345',
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.ds = Dataset.objects.create(
            user=self.user,
            name='فایل تست ابزار',
            original_filename='test.xlsx',
            file_format='xlsx',
            transaction_type='اجاره',
            is_active=True,
        )
        Listing.objects.create(
            dataset=self.ds,
            token='tools-kpi-1',
            title='آگهی تست',
            area=90,
            deposit=500_000_000,
            rent=10_000_000,
        )

    def test_tools_page_renders_premium_kpi(self, _license):
        url = reverse('workspace:tools')
        resp = self.client.get(url, {'tool': 'mixed', 'dataset': str(self.ds.pk)})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'fl-kpi-pro--tools')
        self.assertContains(resp, 'آگهی‌های فایل')
        self.assertContains(resp, 'نرخ تبدیل بازار')
        self.assertTrue(resp.context['tools_kpi']['has_dataset'])
        self.assertIn('kpi', resp.context['market_snapshot'])
