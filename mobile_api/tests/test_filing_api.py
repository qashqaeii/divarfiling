"""تست API فایلینگ موبایل — فیلتر و جستجوی سراسری."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import Dataset, Listing

User = get_user_model()


@patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True)
class FilingApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09123334444', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='فایل ونک',
            original_filename='venk.xlsx',
            file_format='xlsx',
            city='تهران',
            district='ونک',
        )
        Listing.objects.create(
            dataset=self.dataset,
            token='tok-venk-120',
            title='آپارتمان ۱۲۰ متری ونک',
            price=15_000_000_000,
            area=120,
            rooms='3',
            neighborhood='ونک',
            city='تهران',
        )
        Listing.objects.create(
            dataset=self.dataset,
            token='tok-small-65',
            title='آپارتمان ۶۵ متری',
            price=8_000_000_000,
            area=65,
            rooms='2',
            neighborhood='جردن',
            city='تهران',
        )

    def test_listings_price_filter(self, _license):
        resp = self.client.get(
            f'/api/mobile/v1/filing/datasets/{self.dataset.pk}/listings',
            {'price_min': 10_000_000_000},
        )
        self.assertEqual(resp.status_code, 200)
        tokens = [row['token'] for row in resp.json()['data']]
        self.assertEqual(tokens, ['tok-venk-120'])

    def test_listings_area_filter(self, _license):
        resp = self.client.get(
            f'/api/mobile/v1/filing/datasets/{self.dataset.pk}/listings',
            {'area_max': 80},
        )
        self.assertEqual(resp.status_code, 200)
        tokens = [row['token'] for row in resp.json()['data']]
        self.assertEqual(tokens, ['tok-small-65'])

    def test_global_search(self, _license):
        resp = self.client.get('/api/mobile/v1/filing/search', {'q': 'ونک'})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertGreaterEqual(body['meta']['total'], 1)
        self.assertTrue(any('ونک' in (row.get('title') or '') for row in body['data']))

    def test_global_search_scoped_to_dataset(self, _license):
        other_ds = Dataset.objects.create(
            user=self.user,
            name='فایل دیگر',
            original_filename='other.xlsx',
            file_format='xlsx',
        )
        Listing.objects.create(
            dataset=other_ds,
            token='tok-other',
            title='ملک دیگر ونک',
            price=1,
            area=50,
            neighborhood='ونک',
        )
        resp = self.client.get(
            '/api/mobile/v1/filing/search',
            {'q': 'ونک', 'dataset_id': str(self.dataset.pk)},
        )
        self.assertEqual(resp.status_code, 200)
        for row in resp.json()['data']:
            self.assertEqual(row['dataset_id'], str(self.dataset.pk))

    def test_dataset_insights(self, _license):
        resp = self.client.get(f'/api/mobile/v1/filing/datasets/{self.dataset.pk}/insights')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['ok'])
        self.assertIn('charts', body['data'])
        self.assertIn('l2', body['data'])
        self.assertGreaterEqual(body['data']['meta']['row_count'], 2)

    def test_dataset_map(self, _license):
        Listing.objects.filter(dataset=self.dataset).update(
            latitude=35.7575,
            longitude=51.41,
        )
        resp = self.client.get(f'/api/mobile/v1/filing/datasets/{self.dataset.pk}/map')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['ok'])
        self.assertGreaterEqual(len(body['data']['markers']), 2)

    def test_dataset_export_ok(self, _license):
        resp = self.client.get(
            f'/api/mobile/v1/filing/datasets/{self.dataset.pk}/export',
            {'format': 'json'},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/json', resp.get('Content-Type', ''))

    def test_dataset_export_requires_license(self, _license):
        with patch('mobile_api.services.filing_service.has_active_bot_license', return_value=False):
            resp = self.client.get(f'/api/mobile/v1/filing/datasets/{self.dataset.pk}/export')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['code'], 'LICENSE_REQUIRED')

    def test_dataset_export_not_found(self, _license):
        import uuid

        resp = self.client.get(f'/api/mobile/v1/filing/datasets/{uuid.uuid4()}/export')
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()['code'], 'NOT_FOUND')
