"""Matching V3.2 — شواهد موقعیت ساختاریافته و رتبه‌بندی ثانویه."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from workspace.models import CRMProperty, Customer, Dataset, Listing
from workspace.services.advertiser_signal import ADVERTISER_SIGNAL_GENUINE_PERSONAL
from workspace.services.crm_matching import (
    _score_listing,
    match_divar_listings,
)
from workspace.services.crm_matching_eval import (
    MATCH_TIER_ALTERNATIVE,
    MATCH_TIER_INSUFFICIENT,
    MATCH_TIER_STRONG,
    index_sort_score,
)
from workspace.services.crm_matching_geo import (
    listing_location_evidence_level,
    listing_structured_location_extras,
    listing_trusted_neighborhood,
    location_tokens_equivalent,
)
from workspace.services.crm_matching_index import MATCH_INDEX_CACHE_NAMESPACE, ScoredRef, _sort_refs

User = get_user_model()


class MatchingV32StructuredLocationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09129990001', phone='09129990001', password='x')
        self.ds = Dataset.objects.create(user=self.user, name='ds-loc', is_active=True)
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار آبادان',
            phone='09129990002',
            customer_type='خریدار',
            budget_min=5_000_000_000,
            budget_max=30_000_000_000,
            areas='بهارستان، امیری',
            property_type='زمین',
        )

    def test_structured_makan_mahalle_enables_match(self):
        listing = Listing.objects.create(
            dataset=self.ds,
            token='loc-structured',
            title='فروش زمین',
            city='آبادان',
            neighborhood='',
            price=10_000_000_000,
            area=400,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            data={
                'مکان_شهر': 'آبادان',
                'مکان_محله': 'بهارستان',
                'مکان_منبع_جزئیات': 'seo:city_persian,seo:district_persian',
            },
        )
        listing.city = 'آبادان'
        listing.save(update_fields=['city'])
        self.assertIn('بهارستان', listing_structured_location_extras(listing))
        scored = _score_listing(self.buyer, listing)
        self.assertIsNotNone(scored)

    def test_title_only_neighborhood_not_used_for_filter(self):
        listing = Listing.objects.create(
            dataset=self.ds,
            token='loc-title',
            title='زمین 500 متری بهارستان آبادان',
            city='آبادان',
            neighborhood='',
            price=12_000_000_000,
            area=500,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            data={
                'مکان_شهر': 'آبادان',
                'مکان_محله': 'بهارستان',
                'مکان_منبع_جزئیات': 'title:neighborhood,title:expandable_section',
            },
        )
        extras = listing_structured_location_extras(listing)
        self.assertNotIn('بهارستان', extras)
        self.assertIsNone(_score_listing(self.buyer, listing))

    def test_city_only_listing_stays_rejected(self):
        listing = Listing.objects.create(
            dataset=self.ds,
            token='loc-city-only',
            title='فروش زمین',
            city='آبادان',
            neighborhood='',
            price=11_000_000_000,
            area=450,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            data={'مکان_شهر': 'آبادان'},
        )
        self.assertEqual(listing_location_evidence_level(listing), 'partial')
        self.assertIsNone(_score_listing(self.buyer, listing))

    def test_title_expandable_plus_seo_city_does_not_trust_makan_mahalle(self):
        listing = Listing.objects.create(
            dataset=self.ds,
            token='loc-mixed-src',
            title='زمین بهارستان',
            city='آبادان',
            neighborhood='',
            price=10_000_000_000,
            area=400,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            data={
                'مکان_شهر': 'آبادان',
                'مکان_محله': 'بهارستان',
                'مکان_منبع_جزئیات': 'title:expandable_section,seo:city_persian',
            },
        )
        self.assertNotIn('بهارستان', listing_structured_location_extras(listing))
        self.assertEqual(listing_location_evidence_level(listing), 'partial')

    def test_title_street_not_structured_neighborhood(self):
        listing = Listing.objects.create(
            dataset=self.ds,
            token='loc-street',
            title='زمین',
            city='آبادان',
            neighborhood='',
            price=10_000_000_000,
            area=400,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            data={
                'مکان_خیابان': 'امیری',
                'مکان_منبع_جزئیات': 'title:street',
            },
        )
        self.assertEqual(listing_structured_location_extras(listing), [])

    def test_listing_neighborhood_column_bypasses_with_title_sources(self):
        listing = Listing.objects.create(
            dataset=self.ds,
            token='loc-col-bypass',
            title='زمین',
            city='آبادان',
            neighborhood='بهارستان',
            price=10_000_000_000,
            area=400,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            data={
                'مکان_منبع_جزئیات': 'title:expandable_section,seo:city_persian',
            },
        )
        self.assertEqual(listing_trusted_neighborhood(listing), '')
        self.assertIsNone(_score_listing(self.buyer, listing))

    def test_structured_district_still_usable_with_title_sources(self):
        listing = Listing.objects.create(
            dataset=self.ds,
            token='loc-district-seo',
            title='زمین',
            city='آبادان',
            neighborhood='',
            price=10_000_000_000,
            area=400,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            data={
                'مکان_منطقه': 'امیری',
                'مکان_منبع_جزئیات': 'title:expandable_section,seo:district_persian',
            },
        )
        self.assertIn('امیری', listing_structured_location_extras(listing))
        scored = _score_listing(self.buyer, listing)
        self.assertIsNotNone(scored)

    def test_similar_name_different_city_not_equivalent(self):
        self.assertFalse(location_tokens_equivalent('امیری', 'امیری شیراز'))


class MatchingV32RankingTests(TestCase):
    def test_index_sort_display_score_beats_relevance_within_tier(self):
        high_score_low_rel = index_sort_score(88, MATCH_TIER_STRONG, 0)
        low_score_high_rel = index_sort_score(75, MATCH_TIER_STRONG, 9999)
        self.assertGreater(high_score_low_rel, low_score_high_rel)

    def test_index_sort_relevance_breaks_equal_display_score(self):
        a = index_sort_score(80, MATCH_TIER_STRONG, 5000)
        b = index_sort_score(80, MATCH_TIER_STRONG, 100)
        self.assertGreater(a, b)

    def test_index_sort_tier_precedes_display_score(self):
        alt_high = index_sort_score(95, MATCH_TIER_ALTERNATIVE, 9999)
        strong_low = index_sort_score(70, MATCH_TIER_STRONG, 0)
        self.assertGreater(strong_low, alt_high)

    def test_sort_refs_stable_item_id_tiebreak(self):
        refs = [
            ScoredRef(index_sort_score(80, MATCH_TIER_STRONG, 100), 10),
            ScoredRef(index_sort_score(80, MATCH_TIER_STRONG, 100), 20),
        ]
        _sort_refs(refs)
        self.assertEqual([r.item_id for r in refs], [20, 10])

    def setUp(self):
        self.user = User.objects.create_user(username='09129990010', phone='09129990010', password='x')
        self.ds = Dataset.objects.create(user=self.user, name='ds-rank', is_active=True, subcategory='آپارتمان')
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار رتبه',
            phone='09129990011',
            customer_type='خریدار',
            budget_min=9_000_000_000,
            budget_max=11_000_000_000,
            min_area=90,
            max_area=110,
        )
        now = timezone.now()

        self.closer = Listing.objects.create(
            dataset=self.ds,
            token='rank-close',
            title='آپارتمان',
            city='تهران',
            price=10_000_000_000,
            area=100,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            data={'category': 'apartment-sell'},
            published_at=now,
        )
        self.farther = Listing.objects.create(
            dataset=self.ds,
            token='rank-far',
            title='آپارتمان',
            city='تهران',
            price=10_500_000_000,
            area=105,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            data={'category': 'apartment-sell'},
            published_at=now,
        )

    def test_same_score_listings_order_by_relevance_rank(self):
        close = _score_listing(self.buyer, self.closer)
        far = _score_listing(self.buyer, self.farther)
        self.assertIsNotNone(close)
        self.assertIsNotNone(far)
        self.assertEqual(close['score'], far['score'])
        self.assertGreater(close['relevance_rank'], far['relevance_rank'])
        sort_close = index_sort_score(close['score'], close['match_tier'], close['relevance_rank'])
        sort_far = index_sort_score(far['score'], far['match_tier'], far['relevance_rank'])
        self.assertGreater(sort_close, sort_far)

    def test_match_list_preserves_total_and_orders(self):
        matches = match_divar_listings(self.buyer, self.user)
        tokens = [m['token'] for m in matches]
        self.assertGreaterEqual(len(tokens), 2)
        if self.closer.token in tokens and self.farther.token in tokens:
            self.assertLess(tokens.index(self.closer.token), tokens.index(self.farther.token))


class MatchingV32CacheNamespaceTests(TestCase):
    def test_cache_namespace_v4(self):
        self.assertEqual(MATCH_INDEX_CACHE_NAMESPACE, 'v4')
