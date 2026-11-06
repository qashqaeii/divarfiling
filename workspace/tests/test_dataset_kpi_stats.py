"""تست‌های آمار KPI صفحه فایلینگ — صحت شمارش، فیلتر، و visualization واقعی."""
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from workspace.models import Dataset, Listing
from workspace.views import _dataset_stats

User = get_user_model()


class DatasetStatsScopeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='kpi_ds_user', password='x', phone='09128880001',
        )
        self.other = User.objects.create_user(
            username='kpi_ds_other', password='x', phone='09128880002',
        )
        self.factory = RequestFactory()

        self.sale_a = Dataset.objects.create(
            user=self.user, name='فروش_۱', original_filename='s1.xlsx',
            file_format='xlsx', transaction_type='فروش', row_count=2, is_active=True,
        )
        self.sale_b = Dataset.objects.create(
            user=self.user, name='فروش_۲', original_filename='s2.xlsx',
            file_format='xlsx', transaction_type='فروش مسکونی', row_count=1, is_active=True,
        )
        self.rent_a = Dataset.objects.create(
            user=self.user, name='اجاره_۱', original_filename='r1.xlsx',
            file_format='xlsx', transaction_type='اجاره', row_count=3, is_active=True,
        )
        self.rent_b = Dataset.objects.create(
            user=self.user, name='اجاره_۲', original_filename='r2.xlsx',
            file_format='xlsx', transaction_type='اجاره', row_count=1, is_active=True,
        )
        self.mixed = Dataset.objects.create(
            user=self.user, name='ترکیبی', original_filename='m1.xlsx',
            file_format='xlsx', transaction_type='ترکیبی', row_count=1, is_active=True,
        )
        self.deleted = Dataset.objects.create(
            user=self.user, name='حذف‌شده', original_filename='d1.xlsx',
            file_format='xlsx', transaction_type='فروش', row_count=9, is_active=False,
        )
        Dataset.objects.create(
            user=self.other, name='دیگری', original_filename='o1.xlsx',
            file_format='xlsx', transaction_type='فروش', row_count=50, is_active=True,
        )

        for i in range(2):
            Listing.objects.create(dataset=self.sale_a, token=f'sa{i}', title=f'sa{i}')
        Listing.objects.create(dataset=self.sale_b, token='sb0', title='sb0')
        for i in range(3):
            Listing.objects.create(dataset=self.rent_a, token=f'ra{i}', title=f'ra{i}')
        Listing.objects.create(dataset=self.rent_b, token='rb0', title='rb0')
        Listing.objects.create(dataset=self.mixed, token='m0', title='m0')
        for i in range(9):
            Listing.objects.create(dataset=self.deleted, token=f'd{i}', title=f'd{i}')

    def test_counts_match_visible_active_datasets(self):
        stats = _dataset_stats(self.user)
        self.assertEqual(stats['files'], 5)
        self.assertEqual(stats['sale'], 2)
        self.assertEqual(stats['rent'], 2)
        self.assertEqual(stats['listings'], 8)

    def test_filters_narrow_stats(self):
        request = self.factory.get('/workspace/datasets/', {'tx': 'sale'})
        request.user = self.user
        stats = _dataset_stats(self.user, request)
        self.assertEqual(stats['files'], 2)
        self.assertEqual(stats['sale'], 2)
        self.assertEqual(stats['rent'], 0)
        self.assertEqual(stats['listings'], 3)

    def test_inactive_and_other_user_excluded(self):
        stats = _dataset_stats(self.user)
        self.assertEqual(stats['files'], 5)
        self.assertEqual(stats['listings'], 8)

    def test_mix_segments_sum_to_files(self):
        stats = _dataset_stats(self.user)
        mix_total = sum(s['count'] for s in stats['mix_segments'])
        self.assertEqual(mix_total, stats['files'])
        keys = {s['key'] for s in stats['mix_segments']}
        self.assertIn('sale', keys)
        self.assertIn('rent', keys)
        self.assertIn('other', keys)
        other = next(s for s in stats['mix_segments'] if s['key'] == 'other')
        self.assertEqual(other['count'], 1)

    def test_share_progress_from_same_scope(self):
        stats = _dataset_stats(self.user)
        self.assertEqual(stats['sale_share'], 40)
        self.assertEqual(stats['rent_share'], 40)
        self.assertEqual(stats['sale_meta'], '40٪ از پوشه‌ها')
        self.assertEqual(stats['rent_meta'], '40٪ از پوشه‌ها')

    def test_listing_bars_use_real_folder_counts(self):
        stats = _dataset_stats(self.user)
        self.assertTrue(stats['listing_bars'])
        self.assertEqual(stats['listing_bars_max'], 3)
        top = stats['listing_bars'][0]
        self.assertEqual(top['count'], 3)
        self.assertEqual(top['height'], 100)
        self.assertNotIn('files_spark', stats)
        self.assertNotIn('files_trend', stats)
        self.assertNotIn('hero_progress', stats)
