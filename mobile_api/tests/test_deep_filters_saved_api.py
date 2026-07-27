"""تست فیلتر عمیق فایلینگ و Saved Filters (Sprint 2)."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import Dataset, Listing

User = get_user_model()


@patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True)
class DeepListingFiltersApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09120001122', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='فایل فیلتر',
            original_filename='f.xlsx',
            file_format='xlsx',
            city='تهران',
        )
        Listing.objects.create(
            dataset=self.dataset, token='a1', title='ونک ۱',
            price=12_000_000_000, area=100, rooms='3', neighborhood='ونک',
        )
        Listing.objects.create(
            dataset=self.dataset, token='a2', title='جردن ۱',
            price=9_000_000_000, area=70, rooms='2', neighborhood='جردن',
        )
        Listing.objects.create(
            dataset=self.dataset, token='a3', title='ونک ۲',
            price=11_000_000_000, area=95, rooms='3', neighborhood='ونک',
        )

    def test_neighborhood_and_sort(self, _license):
        resp = self.client.get(
            f'/api/mobile/v1/filing/datasets/{self.dataset.pk}/listings',
            {'neighborhood': 'ونک', 'sort': 'price'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertTrue(all('ونک' in (row.get('district') or '') for row in data))
        prices = [row.get('price') for row in data]
        self.assertEqual(prices, sorted(p for p in prices if p is not None))

    def test_unique_filter(self, _license):
        resp = self.client.get(
            f'/api/mobile/v1/filing/datasets/{self.dataset.pk}/listings',
            {'unique': '1'},
        )
        self.assertEqual(resp.status_code, 200)
        tokens = [row['token'] for row in resp.json()['data']]
        self.assertEqual(len(tokens), len(set(tokens)))
        self.assertGreaterEqual(len(tokens), 2)

    def test_meta_neighborhoods(self, _license):
        resp = self.client.get(f'/api/mobile/v1/filing/datasets/{self.dataset.pk}/listings')
        self.assertEqual(resp.status_code, 200)
        neighborhoods = resp.json()['meta'].get('neighborhoods') or []
        self.assertIn('ونک', neighborhoods)


class SavedFiltersApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09120003344', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_create_list_pin_delete_listings_filter(self):
        create = self.client.post(
            '/api/mobile/v1/crm/saved-filters',
            {
                'name': 'ونک زیر ۳',
                'scope': 'listings',
                'params': {'neighborhood': 'ونک', 'rooms': '3', 'unique': '1'},
                'is_pinned': True,
            },
            format='json',
        )
        self.assertEqual(create.status_code, 201, create.content)
        fid = create.json()['data']['id']
        self.assertEqual(create.json()['data']['scope'], 'listings')

        listed = self.client.get('/api/mobile/v1/crm/saved-filters', {'entity': 'listings'})
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(any(item['id'] == fid for item in listed.json()['data']))

        pin = self.client.post(f'/api/mobile/v1/crm/saved-filters/{fid}/pin')
        self.assertEqual(pin.status_code, 200)

        delete = self.client.delete(f'/api/mobile/v1/crm/saved-filters/{fid}')
        self.assertEqual(delete.status_code, 200)
        listed2 = self.client.get('/api/mobile/v1/crm/saved-filters', {'entity': 'listings'})
        self.assertFalse(any(item['id'] == fid for item in listed2.json()['data']))
