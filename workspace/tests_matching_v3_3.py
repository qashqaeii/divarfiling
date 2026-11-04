"""Matching V3.3 — ترجیح جغرافیایی نرم."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from workspace.models import CRMProperty, Customer, Dataset, Listing
from workspace.services.advertiser_signal import ADVERTISER_SIGNAL_GENUINE_PERSONAL
from workspace.services.crm_matching import (
    _score_crm_property,
    _score_listing,
    _score_customer_for_property,
    match_divar_listings,
    match_crm_properties,
)
from workspace.services.crm_matching_eval import (
    MATCH_TIER_ALTERNATIVE,
    MATCH_TIER_STRONG,
    match_eligible_for_auto_notify,
)
from workspace.services.crm_matching_geo import (
    LOC_STATUS_DIFFERENT,
    LOC_STATUS_EXACT,
    LOC_STATUS_HINT,
    LOC_STATUS_UNKNOWN,
    evaluate_soft_location_match,
)

User = get_user_model()


class MatchingV33SoftGeoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09127770001', phone='09127770001', password='x')
        self.ds = Dataset.objects.create(user=self.user, name='ds-v33', is_active=True, subcategory='زمین')
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار محله',
            phone='09127770002',
            customer_type='خریدار',
            budget_min=8_000_000_000,
            budget_max=20_000_000_000,
            min_area=300,
            max_area=600,
            areas='بهارستان، امیری',
            property_type='زمین',
        )

    def _listing(self, **kwargs):
        defaults = dict(
            dataset=self.ds,
            title='فروش زمین',
            city='آبادان',
            price=10_000_000_000,
            area=400,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
        )
        defaults.update(kwargs)
        return Listing.objects.create(**defaults)

    def test_exact_neighborhood_ranks_high_and_can_be_strong(self):
        listing = self._listing(
            token='v33-exact',
            neighborhood='',
            data={
                'مکان_شهر': 'آبادان',
                'مکان_محله': 'بهارستان',
                'مکان_منبع_جزئیات': 'seo:city_persian,seo:district_persian',
            },
        )
        scored = _score_listing(self.buyer, listing)
        self.assertIsNotNone(scored)
        self.assertEqual(scored['location_match_status'], LOC_STATUS_EXACT)
        self.assertEqual(scored['match_tier'], MATCH_TIER_STRONG)

    def test_missing_neighborhood_not_rejected(self):
        listing = self._listing(
            token='v33-unknown',
            neighborhood='',
            data={'مکان_شهر': 'آبادان'},
        )
        scored = _score_listing(self.buyer, listing)
        self.assertIsNotNone(scored)
        self.assertEqual(scored['location_match_status'], LOC_STATUS_UNKNOWN)
        self.assertEqual(scored['match_tier'], MATCH_TIER_ALTERNATIVE)

    def test_different_neighborhood_is_alternative_not_strong(self):
        listing = self._listing(
            token='v33-diff',
            neighborhood='کوت عبدالله',
            city='آبادان',
            data={'مکان_شهر': 'آبادان'},
        )
        scored = _score_listing(self.buyer, listing)
        self.assertIsNotNone(scored)
        self.assertEqual(scored['location_match_status'], LOC_STATUS_DIFFERENT)
        self.assertEqual(scored['match_tier'], MATCH_TIER_ALTERNATIVE)
        self.assertFalse(match_eligible_for_auto_notify(scored))

    def test_title_hint_not_exact_and_not_strong(self):
        listing = self._listing(
            token='v33-hint',
            neighborhood='',
            data={
                'مکان_شهر': 'آبادان',
                'مکان_محله': 'بهارستان',
                'مکان_منبع_جزئیات': 'title:neighborhood,title:expandable_section',
            },
        )
        scored = _score_listing(self.buyer, listing)
        self.assertIsNotNone(scored)
        self.assertEqual(scored['location_match_status'], LOC_STATUS_HINT)
        self.assertNotEqual(scored['match_tier'], MATCH_TIER_STRONG)

    def test_street_name_only_not_verified_exact(self):
        geo = evaluate_soft_location_match(
            self.buyer,
            neighborhood='',
            city='آبادان',
            district='',
            extra_values=None,
            trusted_street='',
            unverified_hints=['امیری'],
        )
        self.assertEqual(geo.status, LOC_STATUS_HINT)

    def test_city_only_profile_gets_unknown_not_different(self):
        geo = evaluate_soft_location_match(
            self.buyer,
            neighborhood='',
            city='آبادان',
            district='',
            extra_values=None,
        )
        self.assertEqual(geo.status, LOC_STATUS_UNKNOWN)

    def test_windows_legacy_empty_geo_still_matches(self):
        listing = self._listing(
            token='v33-win',
            neighborhood='',
            city='آبادان',
            data={},
        )
        scored = _score_listing(self.buyer, listing)
        self.assertIsNotNone(scored)

    def test_crm_property_reverse_symmetry(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='زمین بهارستان',
            property_type='زمین',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            area=400,
            neighborhood='بهارستان',
            city='آبادان',
        )
        crm = _score_crm_property(self.buyer, prop)
        self.assertIsNotNone(crm)
        rev = _score_customer_for_property(self.buyer, prop)
        self.assertIsNotNone(rev)

    def test_match_lists_include_unknown_geo_listing(self):
        exact = self._listing(
            token='v33-list-exact',
            neighborhood='',
            data={
                'مکان_محله': 'بهارستان',
                'مکان_منبع_جزئیات': 'seo:district_persian',
            },
        )
        unknown = self._listing(
            token='v33-list-unk',
            neighborhood='',
            data={'مکان_شهر': 'آبادان'},
        )
        matches = match_divar_listings(self.buyer, self.user)
        tokens = {m['token'] for m in matches}
        self.assertIn(exact.token, tokens)
        self.assertIn(unknown.token, tokens)
        exact_idx = next(i for i, m in enumerate(matches) if m['token'] == exact.token)
        unk_idx = next(i for i, m in enumerate(matches) if m['token'] == unknown.token)
        self.assertLess(exact_idx, unk_idx)

    def test_multi_area_or_match(self):
        listing = self._listing(
            token='v33-multi',
            neighborhood='امیری',
            city='آبادان',
            data={'مکان_شهر': 'آبادان'},
        )
        scored = _score_listing(self.buyer, listing)
        self.assertIsNotNone(scored)
        self.assertEqual(scored['location_match_status'], LOC_STATUS_EXACT)

    def test_search_city_hint_still_hard_filter(self):
        buyer = Customer.objects.create(
            user=self.user,
            name='خریدار شیراز',
            phone='09127770003',
            customer_type='خریدار',
            budget_min=5_000_000_000,
            budget_max=30_000_000_000,
            areas='شیراز - صیاد',
            property_type='آپارتمان',
        )
        listing = self._listing(
            token='v33-wrong-city',
            city='تهران',
            neighborhood='صیاد',
            price=10_000_000_000,
            area=100,
            data={'category': 'apartment-sell', 'مکان_شهر': 'تهران'},
        )
        self.assertIsNone(_score_listing(buyer, listing))

    def test_crm_matches_include_other_neighborhood(self):
        CRMProperty.objects.create(
            user=self.user,
            title='زمین دیگر',
            property_type='زمین',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            area=400,
            neighborhood='کوت عبدالله',
            city='آبادان',
        )
        matches = match_crm_properties(self.buyer, self.user)
        self.assertGreaterEqual(len(matches), 1)
