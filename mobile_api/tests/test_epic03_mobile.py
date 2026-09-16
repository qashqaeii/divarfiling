"""Epic 03 — Mobile Daily Power API tests."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import CRMAgencyMember, CRMDeal, CRMProperty, Customer, Dataset, Listing
from workspace.services.crm_agency import create_agency
from workspace.tests.agency_test_utils import ensure_agency_subscription

User = get_user_model()


class Epic03MobileApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='epic03owner', password='test')
        self.user.phone = '09121112233'
        self.user.save(update_fields=['phone'])
        self.other = User.objects.create_user(username='epic03other', password='test')
        self.other.phone = '09124445566'
        self.other.save(update_fields=['phone'])
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

        self.customer = Customer.objects.create(
            user=self.user,
            name='رضا مشتری',
            phone='09121112233',
        )
        self.property = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان سعادت',
            city='تهران',
            neighborhood='سعادت‌آباد',
            latitude=35.78,
            longitude=51.42,
            sale_price=5_000_000_000,
            area=90,
        )
        self.deal = CRMDeal.objects.create(
            user=self.user,
            customer=self.customer,
            property=self.property,
            title='فروش سعادت',
            stage='مذاکره',
        )
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='فایل شمال',
            original_filename='n.xlsx',
            file_format='xlsx',
            city='تهران',
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='lst-epic03-a',
            title='آگهی شمال',
            price=10_000_000_000,
            area=100,
            neighborhood='نیاوران',
            city='تهران',
            latitude=35.81,
            longitude=51.47,
        )
        Listing.objects.create(
            dataset=self.dataset,
            token='lst-epic03-b',
            title='آگهی دوم',
            price=9_000_000_000,
            area=95,
            latitude=35.80,
            longitude=51.46,
        )

        self.agency = create_agency(self.user, 'آژانس Epic')
        ensure_agency_subscription(self.user, self.agency)
        self.member_user = User.objects.create_user(username='epic03member', password='test')
        self.member_user.phone = '09127778899'
        self.member_user.save(update_fields=['phone'])
        self.member = CRMAgencyMember.objects.create(
            agency=self.agency,
            user=self.member_user,
            role='advisor',
            is_active=True,
        )
        self.property.agency = self.agency
        self.property.save(update_fields=['agency_id'])

    def test_global_search_groups(self):
        resp = self.client.get('/api/mobile/v1/search/global', {'q': 'سعادت'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        keys = {g['key'] for g in data['groups']}
        self.assertIn('properties', keys)

        resp2 = self.client.get('/api/mobile/v1/search/global', {'q': 'ر'})
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()['data']['groups'], [])

    def test_global_search_does_not_leak_other_user(self):
        CRMProperty.objects.create(
            user=self.other,
            title='ملک مخفی دیگر',
            city='تهران',
        )
        resp = self.client.get('/api/mobile/v1/search/global', {'q': 'مخفی'})
        self.assertEqual(resp.status_code, 200)
        all_titles = []
        for group in resp.json()['data']['groups']:
            for item in group['items']:
                all_titles.append(item['title'])
        self.assertEqual(all_titles, [])

    @patch('mobile_api.services.global_search_mobile.has_active_bot_license', return_value=True)
    def test_global_search_listings(self, _lic):
        resp = self.client.get('/api/mobile/v1/search/global', {'q': 'شمال'})
        self.assertEqual(resp.status_code, 200)
        listing_groups = [g for g in resp.json()['data']['groups'] if g['key'] == 'listings']
        self.assertTrue(listing_groups)
        self.assertEqual(listing_groups[0]['items'][0]['destination']['token'], 'lst-epic03-a')

    def test_property_map_bounds(self):
        resp = self.client.get(
            '/api/mobile/v1/crm/properties/map',
            {
                'north': 35.79,
                'south': 35.77,
                'east': 51.43,
                'west': 51.41,
            },
        )
        self.assertEqual(resp.status_code, 200)
        markers = resp.json()['data']['markers']
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0]['property_id'], self.property.pk)

    def test_property_team_share_grant_and_revoke(self):
        url = f'/api/mobile/v1/crm/properties/{self.property.pk}/team-shares'
        list_resp = self.client.get(url)
        self.assertEqual(list_resp.status_code, 200)
        self.assertTrue(list_resp.json()['data']['can_share'])

        grant = self.client.post(
            url,
            {'member_id': self.member.pk, 'share_mode': 'confidential'},
            format='json',
        )
        self.assertEqual(grant.status_code, 201)

        other_prop = CRMProperty.objects.create(user=self.other, title='دیگری', city='تهران')
        denied = self.client.post(
            f'/api/mobile/v1/crm/properties/{other_prop.pk}/team-shares',
            {'member_id': self.member.pk},
            format='json',
        )
        self.assertIn(denied.status_code, (400, 404))

        share_id = grant.json()['data']['id']
        revoke = self.client.delete(f'{url}?share_id={share_id}')
        self.assertEqual(revoke.status_code, 200)

    @patch('mobile_api.services.listing_benchmark_mobile.has_active_bot_license', return_value=True)
    def test_listing_benchmark_payload(self, _lic):
        resp = self.client.get('/api/mobile/v1/filing/listings/lst-epic03-a/benchmark')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(resp.json()['data']['status'], ('ok', 'insufficient_data'))

    @patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True)
    def test_multi_dataset_search_filter(self, _lic):
        ds2 = Dataset.objects.create(
            user=self.user,
            name='جنوب',
            original_filename='s.xlsx',
            file_format='xlsx',
        )
        Listing.objects.create(
            dataset=ds2,
            token='lst-south',
            title='جنوب شهر',
            price=1_000_000_000,
            area=50,
        )
        resp = self.client.get(
            '/api/mobile/v1/filing/search',
            {'dataset_ids': f'{self.dataset.pk}', 'q': 'شمال'},
        )
        self.assertEqual(resp.status_code, 200)
        tokens = [row['token'] for row in resp.json()['data']]
        self.assertIn('lst-epic03-a', tokens)
        self.assertNotIn('lst-south', tokens)

    @patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True)
    def test_filing_listings_map_respects_bounds(self, _lic):
        resp = self.client.get(
            '/api/mobile/v1/filing/listings/map',
            {
                'north': 35.805,
                'south': 35.795,
                'east': 51.465,
                'west': 51.455,
                'dataset_ids': str(self.dataset.pk),
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()['data']['markers_shown'], 1)

    @patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True)
    def test_unauthorized_listing_benchmark(self, _lic):
        other_ds = Dataset.objects.create(
            user=self.other,
            name='other',
            original_filename='o.xlsx',
            file_format='xlsx',
        )
        Listing.objects.create(
            dataset=other_ds,
            token='secret-token',
            title='secret',
            price=1,
            area=1,
        )
        resp = self.client.get('/api/mobile/v1/filing/listings/secret-token/benchmark')
        self.assertEqual(resp.status_code, 404)
