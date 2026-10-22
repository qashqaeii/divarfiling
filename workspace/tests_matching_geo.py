"""تست تطبیق جغرافیایی."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty, Customer
from workspace.services.crm_matching import get_customer_matches, match_crm_properties
from workspace.services.crm_matching_geo import (
    location_tokens_equivalent,
    normalize_geo_text,
)

User = get_user_model()


class MatchingGeoNormalizeTests(TestCase):
    def test_arabic_yeh_kaf_normalized(self):
        self.assertEqual(
            normalize_geo_text('سعادت آباد'),
            normalize_geo_text('سعادت‌آباد'),
        )

    def test_similar_but_distinct_neighborhoods_not_equivalent(self):
        self.assertFalse(location_tokens_equivalent('ونک', 'ولنجک'))
        self.assertFalse(location_tokens_equivalent('پونک', 'پونک جنوبی تهران'))


class MatchingGeoCityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09121113333', phone='09121113333', password='x')
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار شهر',
            phone='09121113333',
            customer_type='خریدار',
            city='تهران',
            budget_min=5_000_000_000,
            budget_max=20_000_000_000,
            areas='ونک',
        )

    def test_city_mismatch_excludes_property(self):
        CRMProperty.objects.create(
            user=self.user,
            title='شیراز',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='ونک',
            city='شیراز',
            area=100,
        )
        matches = match_crm_properties(self.buyer, self.user)
        self.assertEqual(matches, [])

    def test_arabic_neighborhood_still_matches(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='ونک',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='ونك',
            city='تهران',
            area=100,
        )
        data = get_customer_matches(self.buyer, self.user, divar_enabled=False)
        ids = {m['property_id'] for m in data['crm_matches']}
        self.assertIn(prop.pk, ids)
