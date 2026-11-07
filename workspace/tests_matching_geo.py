"""تست تطبیق جغرافیایی."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty, Customer, Dataset, Listing
from workspace.services.advertiser_signal import ADVERTISER_SIGNAL_GENUINE_PERSONAL
from workspace.services.crm_matching import (
    _score_listing,
    get_customer_matches,
    match_crm_properties,
)
from workspace.services.crm_matching_geo import (
    LOC_STATUS_DIFFERENT,
    LOC_STATUS_STREET,
    LOC_STATUS_UNKNOWN,
    evaluate_soft_location_match,
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

    def test_wrong_neighborhood_is_alternative_not_excluded(self):
        CRMProperty.objects.create(
            user=self.user,
            title='زعفرانیه',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='زعفرانیه',
            city='تهران',
            area=100,
        )
        matches = match_crm_properties(self.buyer, self.user)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['location_match_status'], 'location_different')
        self.assertEqual(matches[0]['match_tier'], 'alternative')

    def test_identity_city_does_not_block_when_areas_empty(self):
        self.buyer.areas = ''
        self.buyer.save(update_fields=['areas'])
        prop = CRMProperty.objects.create(
            user=self.user,
            title='شیراز',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='',
            city='شیراز',
            area=100,
        )
        matches = match_crm_properties(self.buyer, self.user)
        ids = {m['property_id'] for m in matches}
        self.assertIn(prop.pk, ids)

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


class MatchingStreetPreferenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09121114444', phone='09121114444', password='x')
        self.ds = Dataset.objects.create(user=self.user, name='ds-street', is_active=True)
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار خیابان',
            phone='09121114445',
            customer_type='خریدار',
            budget_min=5_000_000_000,
            budget_max=20_000_000_000,
            property_type='آپارتمان',
            streets='ولیعصر، فرشته',
        )

    def test_evaluate_street_pref_exact(self):
        geo = evaluate_soft_location_match(
            self.buyer,
            neighborhood='',
            city='تهران',
            trusted_street='ولیعصر',
        )
        self.assertEqual(geo.status, LOC_STATUS_STREET)
        self.assertGreaterEqual(geo.hood_s, 0.78)

    def test_evaluate_street_pref_mismatch(self):
        geo = evaluate_soft_location_match(
            self.buyer,
            neighborhood='',
            city='تهران',
            trusted_street='جردن',
        )
        self.assertEqual(geo.status, LOC_STATUS_DIFFERENT)

    def test_evaluate_street_pref_unknown_without_street(self):
        geo = evaluate_soft_location_match(
            self.buyer,
            neighborhood='ونک',
            city='تهران',
            trusted_street='',
        )
        self.assertEqual(geo.status, LOC_STATUS_UNKNOWN)

    def test_crm_property_street_pref_matches(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان ولیعصر',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=100,
            feature_data={'خیابان': 'ولیعصر'},
        )
        matches = match_crm_properties(self.buyer, self.user)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['location_match_status'], LOC_STATUS_STREET)
        self.assertIn(prop.pk, {m['property_id'] for m in matches})

    def test_crm_property_wrong_street_is_different(self):
        CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان جردن',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='جردن',
            city='تهران',
            area=100,
            feature_data={'خیابان': 'جردن'},
        )
        matches = match_crm_properties(self.buyer, self.user)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['location_match_status'], LOC_STATUS_DIFFERENT)

    def test_listing_trusted_street_pref_matches(self):
        listing = Listing.objects.create(
            dataset=self.ds,
            token='street-match-1',
            title='فروش آپارتمان',
            city='تهران',
            price=10_000_000_000,
            area=100,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            neighborhood='',
            data={
                'مکان_خیابان': 'فرشته',
                'مکان_منبع_جزئیات': 'seo:city_persian,seo:street',
            },
        )
        scored = _score_listing(self.buyer, listing)
        self.assertIsNotNone(scored)
        self.assertEqual(scored['location_match_status'], LOC_STATUS_STREET)

    def test_street_and_area_pref_neighborhood_wins(self):
        self.buyer.areas = 'ونک'
        self.buyer.save(update_fields=['areas'])
        geo = evaluate_soft_location_match(
            self.buyer,
            neighborhood='ونک',
            city='تهران',
            trusted_street='جردن',
        )
        self.assertEqual(geo.status, 'exact_neighborhood')
