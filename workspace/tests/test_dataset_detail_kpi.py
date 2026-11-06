"""تست KPIهای تحلیلی جزئیات پوشه استخراج."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from workspace.models import Dataset, Listing
from workspace.services.dataset_detail_kpi import build_dataset_detail_insight_kpis
from workspace.services.display import transaction_profile

User = get_user_model()


class DatasetDetailInsightKpiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dd_kpi_u', password='x', phone='09128881101',
        )
        self.ds = Dataset.objects.create(
            user=self.user, name='اجاره_تست', original_filename='r.xlsx',
            file_format='xlsx', transaction_type='اجاره', row_count=0,
        )
        now = timezone.now()
        areas = (70, 80, 90, 100, 110)
        for i, area in enumerate(areas):
            Listing.objects.create(
                dataset=self.ds, token=f't{i}', title=f'آگهی {i}',
                deposit=200_000_000 + i * 10_000_000,
                rent=8_000_000 + i * 500_000,
                area=area,
                published_at=now - timedelta(days=i),
            )

    def test_rent_price_and_area(self):
        qs = self.ds.listings.all()
        total = qs.count()
        tx = transaction_profile('اجاره')
        kpis = build_dataset_detail_insight_kpis(
            listings_qs=qs,
            tx=tx,
            total_count=total,
            genuine_count=4,
            genuine_pct=50,
        )
        self.assertTrue(kpis['insight_price']['has_value'])
        self.assertEqual(kpis['insight_price']['mode'], 'rent')
        self.assertNotEqual(kpis['insight_price']['value_display'], '—')
        self.assertTrue(kpis['insight_new']['has_value'])
        self.assertTrue(kpis['insight_area']['has_value'])
        self.assertEqual(kpis['insight_area']['value'], 90)
        self.assertIn('70', kpis['insight_area']['secondary_display'])
        self.assertIn('110', kpis['insight_area']['secondary_display'])
        self.assertEqual(kpis['insight_area']['sample_count'], 5)
        self.assertNotIn('insight_review', kpis)

    def test_new_ads_dash_without_published_coverage(self):
        self.ds.listings.update(published_at=None)
        qs = self.ds.listings.all()
        kpis = build_dataset_detail_insight_kpis(
            listings_qs=qs,
            tx=transaction_profile('اجاره'),
            total_count=qs.count(),
            genuine_count=0,
            genuine_pct=0,
        )
        self.assertFalse(kpis['insight_new']['has_value'])
        self.assertEqual(kpis['insight_new']['value_display'], '—')

    def test_area_dash_without_enough_samples(self):
        self.ds.listings.update(area=None)
        Listing.objects.filter(dataset=self.ds).update(area=None)
        Listing.objects.filter(dataset=self.ds, token='t0').update(area=85)
        Listing.objects.filter(dataset=self.ds, token='t1').update(area=90)
        qs = self.ds.listings.all()
        kpis = build_dataset_detail_insight_kpis(
            listings_qs=qs,
            tx=transaction_profile('اجاره'),
            total_count=qs.count(),
            genuine_count=0,
            genuine_pct=0,
        )
        self.assertFalse(kpis['insight_area']['has_value'])
        self.assertEqual(kpis['insight_area']['value_display'], '—')
