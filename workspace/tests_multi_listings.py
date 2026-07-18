"""تست‌های مرور چندمجموعه‌داده."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

from workspace.models import Dataset, Listing
from workspace.views import _merged_transaction_profile, _parse_dataset_ids_param


class _FakeRequest:
    def __init__(self, get):
        self.GET = get


class MultiDatasetListingsHelpersTests(TestCase):
    def test_parse_dataset_ids_comma_and_list(self):
        q = QueryDict('dataset_ids=a,b&dataset_ids=c')
        ids = _parse_dataset_ids_param(_FakeRequest(q))
        self.assertEqual(ids, ['a', 'b', 'c'])

    def test_merged_tx_mixed(self):
        sale = Dataset(transaction_type='فروش')
        rent = Dataset(transaction_type='اجاره')
        tx = _merged_transaction_profile([sale, rent])
        self.assertTrue(tx['is_mixed'])
        self.assertTrue(tx['show_price'])
        self.assertTrue(tx['show_deposit'])


class MultiDatasetListingsViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='multi_ds', password='x')
        self.client.force_login(self.user)
        self.ds1 = Dataset.objects.create(
            user=self.user, name='فایل فروش', original_filename='a.xlsx',
            file_format='xlsx', transaction_type='فروش', row_count=1,
        )
        self.ds2 = Dataset.objects.create(
            user=self.user, name='فایل اجاره', original_filename='b.xlsx',
            file_format='xlsx', transaction_type='اجاره', row_count=1,
        )
        Listing.objects.create(dataset=self.ds1, token='t1', title='آگهی فروش', price=1_000_000_000)
        Listing.objects.create(dataset=self.ds2, token='t2', title='آگهی اجاره', deposit=500_000_000)
        self.geo1 = Listing.objects.create(
            dataset=self.ds1, token='g1', title='فروش با مختصات',
            price=2_000_000_000, latitude=35.7, longitude=51.4,
        )
        self.geo2 = Listing.objects.create(
            dataset=self.ds2, token='g2', title='اجاره با مختصات',
            deposit=800_000_000, latitude=35.71, longitude=51.41,
        )
        self.geo_out = Listing.objects.create(
            dataset=self.ds1, token='g3', title='خارج از فیلتر قیمت',
            price=100_000_000, latitude=35.72, longitude=51.42,
        )

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_requires_ids(self, _mock_license):
        res = self.client.get(reverse('workspace:multi_listings'))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse('workspace:dataset_list'))

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_combined_page(self, _mock_license):
        url = reverse('workspace:multi_listings')
        res = self.client.get(url, {'dataset_ids': f'{self.ds1.id},{self.ds2.id}'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'آگهی فروش')
        self.assertContains(res, 'آگهی اجاره')
        self.assertContains(res, 'فایل فروش')
        self.assertTrue(res.context['show_dataset_column'])
        self.assertTrue(res.context['tx']['is_mixed'])
        self.assertContains(res, reverse('workspace:multi_map'))
        self.assertContains(res, 'مقایسه')
        self.assertContains(res, 'لایه‌های فایل')
        self.assertContains(res, 'ترکیب آگهی‌دهنده')

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_multi_map_combines_geo_listings(self, _mock_license):
        url = reverse('workspace:multi_map')
        res = self.client.get(url, {'dataset_ids': f'{self.ds1.id},{self.ds2.id}'})
        self.assertEqual(res.status_code, 200)
        marker_ids = {m['id'] for m in res.context['markers']}
        self.assertIn(self.geo1.pk, marker_ids)
        self.assertIn(self.geo2.pk, marker_ids)
        self.assertIn(self.geo_out.pk, marker_ids)
        self.assertTrue(res.context['is_multi_map'])
        self.assertEqual(res.context['geo_count'], 3)
        self.assertContains(res, 'نقشه چند فایل')
        self.assertContains(res, 'mk-map-multi-files')

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_multi_map_respects_listing_filters(self, _mock_license):
        url = reverse('workspace:multi_map')
        res = self.client.get(url, {
            'dataset_ids': f'{self.ds1.id},{self.ds2.id}',
            'price_min': '500000000',
        })
        self.assertEqual(res.status_code, 200)
        marker_ids = {m['id'] for m in res.context['markers']}
        self.assertIn(self.geo1.pk, marker_ids)
        self.assertNotIn(self.geo_out.pk, marker_ids)
        # اجاره بدون قیمت در فیلتر price_min حذف می‌شود
        self.assertNotIn(self.geo2.pk, marker_ids)
        self.assertTrue(res.context['is_map_filtered'])
        self.assertGreaterEqual(res.context['filter_count'], 1)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_multi_map_requires_ids(self, _mock_license):
        res = self.client.get(reverse('workspace:multi_map'))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse('workspace:dataset_list'))

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_single_dataset_map_respects_filters(self, _mock_license):
        url = reverse('workspace:dataset_map', kwargs={'dataset_id': self.ds1.id})
        res = self.client.get(url, {'price_min': '500000000'})
        self.assertEqual(res.status_code, 200)
        marker_ids = {m['id'] for m in res.context['markers']}
        self.assertIn(self.geo1.pk, marker_ids)
        self.assertNotIn(self.geo_out.pk, marker_ids)
        self.assertTrue(res.context['is_map_filtered'])
