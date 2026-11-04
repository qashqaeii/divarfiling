"""رگرسیون Matching V3 — geo، نوع ملک، کیفیت پیشنهاد، تقارن."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from workspace.models import CRMProperty, Customer, Dataset, Listing, PropertyContact
from workspace.services.advertiser_signal import ADVERTISER_SIGNAL_GENUINE_PERSONAL
from workspace.services.crm_matching import (
    _score_crm_property,
    _score_listing,
    get_customer_matches,
    get_property_contact_matches,
    match_crm_properties,
)
from workspace.services.crm_matching_eval import (
    MATCH_TIER_ALTERNATIVE,
    MATCH_TIER_INSUFFICIENT,
    MATCH_TIER_STRONG,
    match_eligible_for_auto_notify,
)
from workspace.services.crm_matching_geo import (
    location_tokens_equivalent,
    parse_preferred_areas,
    strip_location_prefix,
)
from workspace.services.crm_matching_index import (
    MATCH_INDEX_CACHE_NAMESPACE,
    _index_cache_key,
    build_crm_index,
    get_or_build_index,
    slice_refs,
)
from workspace.services.crm_matching_types import infer_listing_property_type_detail

User = get_user_model()


class MatchingV3GeoSeparatorTests(TestCase):
    def test_dot_separator_in_areas(self):
        parts = parse_preferred_areas('صیاد.عدالت')
        self.assertEqual(len(parts), 2)
        self.assertIn('صیاد', parts[0])
        self.assertIn('عدالت', parts[1])

    def test_decimal_not_split_in_geo_normalize(self):
        text = '3.5'
        parts = parse_preferred_areas(text)
        self.assertEqual(parts, ['3.5'])

    def test_mahdode_ye_prefix_stripped(self):
        self.assertEqual(strip_location_prefix('محدوده ی معلم'), 'معلم')
        self.assertTrue(location_tokens_equivalent('معلم', 'محدوده ی معلم'))


class MatchingV3PropertyTypeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09128880001', phone='09128880001', password='x')
        self.ds = Dataset.objects.create(
            user=self.user, name='ds-v3', is_active=True, subcategory='خانه و ویلا',
        )

    def test_broad_dataset_subcategory_not_specific_villa(self):
        listing = Listing(
            dataset=self.ds,
            token='broad-ds',
            title='فروش فوری',
            data={},
        )
        detail = infer_listing_property_type_detail(listing)
        self.assertEqual(detail.property_type, '')
        self.assertEqual(detail.confidence, 'none')

    def test_title_villa_when_dataset_broad(self):
        listing = Listing(
            dataset=self.ds,
            token='villa-title',
            title='ویلا 300 متری',
            data={},
        )
        detail = infer_listing_property_type_detail(listing)
        self.assertEqual(detail.property_type, 'ویلا')
        self.assertEqual(detail.source, 'title')
        self.assertEqual(detail.confidence, 'low')

    def test_ambiguous_title_without_structured_stays_unknown(self):
        ds = Dataset.objects.create(user=self.user, name='ds-empty', is_active=True, subcategory='')
        listing = Listing(dataset=ds, token='unk', title='فروش فوری', data={})
        detail = infer_listing_property_type_detail(listing)
        self.assertEqual(detail.property_type, '')
        self.assertEqual(detail.confidence, 'none')


class MatchingV3TierAccuracyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09128880100', phone='09128880100', password='x')
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='ملک تست tier',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=100,
            rooms='2',
            has_parking=True,
        )

    def test_type_only_buyer_is_insufficient_not_strong(self):
        buyer = Customer.objects.create(
            user=self.user,
            name='فقط نوع',
            phone='09128880101',
            customer_type='خریدار',
            property_type='آپارتمان',
        )
        scored = _score_crm_property(buyer, self.prop)
        self.assertIsNotNone(scored)
        self.assertEqual(scored['match_tier'], MATCH_TIER_INSUFFICIENT)
        self.assertFalse(match_eligible_for_auto_notify(scored))

    def test_budget_only_buyer_can_be_strong(self):
        buyer = Customer.objects.create(
            user=self.user,
            name='فقط بودجه',
            phone='09128880102',
            customer_type='خریدار',
            budget_min=9_000_000_000,
            budget_max=11_000_000_000,
        )
        scored = _score_crm_property(buyer, self.prop)
        self.assertIsNotNone(scored)
        self.assertEqual(scored['match_tier'], MATCH_TIER_STRONG)

    def test_parking_only_without_other_need_is_insufficient(self):
        buyer = Customer.objects.create(
            user=self.user,
            name='فقط پارکینگ',
            phone='09128880103',
            customer_type='خریدار',
            want_parking=True,
        )
        scored = _score_crm_property(buyer, self.prop)
        self.assertIsNotNone(scored)
        self.assertEqual(scored['match_tier'], MATCH_TIER_INSUFFICIENT)

    def test_complete_profile_exact_match_is_strong(self):
        buyer = Customer.objects.create(
            user=self.user,
            name='کامل',
            phone='09128880104',
            customer_type='خریدار',
            budget_min=9_000_000_000,
            budget_max=11_000_000_000,
            areas='ونک',
            property_type='آپارتمان',
            min_area=90,
            max_area=110,
            want_parking=True,
        )
        scored = _score_crm_property(buyer, self.prop)
        self.assertEqual(scored['match_tier'], MATCH_TIER_STRONG)

    def test_slightly_over_budget_is_alternative_not_neutral_rooms(self):
        buyer = Customer.objects.create(
            user=self.user,
            name='بودجه نزدیک',
            phone='09128880105',
            customer_type='خریدار',
            budget_min=8_000_000_000,
            budget_max=9_500_000_000,
            areas='ونک',
            property_type='آپارتمان',
            min_area=90,
            max_area=110,
            matching_tolerance_percent=10,
        )
        scored = _score_crm_property(buyer, self.prop)
        self.assertEqual(scored['match_tier'], MATCH_TIER_ALTERNATIVE)


class MatchingV3ReverseLeadQualityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09128880002', phone='09128880002', password='x')
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='فروش شیراز',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=15_000_000_000,
            neighborhood='صیاد',
            city='شیراز',
            area=120,
        )
        self.empty_lead = Customer.objects.create(
            user=self.user,
            name='سرنخ خالی',
            phone='09128880003',
            customer_type='سرنخ',
            status='در حال پیگیری',
        )
        self.qualified_buyer = Customer.objects.create(
            user=self.user,
            name='خریدار',
            phone='09128880004',
            customer_type='خریدار',
            status='در حال پیگیری',
            budget_min=13_000_000_000,
            budget_max=18_000_000_000,
            areas='صیاد',
            property_type='آپارتمان',
        )

    def test_empty_lead_not_suggested_for_property(self):
        data = get_property_contact_matches(self.prop, self.user)
        ids = {m['customer_id'] for m in data['matches']}
        self.assertNotIn(self.empty_lead.pk, ids)

    def test_qualified_buyer_suggested_with_strong_tier(self):
        data = get_property_contact_matches(self.prop, self.user)
        card = next(m for m in data['matches'] if m['customer_id'] == self.qualified_buyer.pk)
        self.assertEqual(card.get('match_tier'), MATCH_TIER_STRONG)


class MatchingV3ShirazBuyerRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09128880005', phone='09128880005', password='x')
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار شیراز',
            phone='09128880006',
            customer_type='خریدار',
            budget_min=13_000_000_000,
            budget_max=18_000_000_000,
            areas='صیاد.عدالت.آپادانا',
            property_type='آپارتمان',
        )

    def test_dot_separated_neighborhoods_match_crm(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='صیاد',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=15_000_000_000,
            neighborhood='صیاد',
            city='شیراز',
            area=110,
        )
        matches = match_crm_properties(self.buyer, self.user)
        self.assertIn(prop.pk, {m['property_id'] for m in matches})


class MatchingV3BidirectionalSymmetryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09128880007', phone='09128880007', password='x')
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار تقارن',
            phone='09128880008',
            customer_type='خریدار',
            status='در حال پیگیری',
            budget_min=9_000_000_000,
            budget_max=11_000_000_000,
            areas='ونک',
            property_type='آپارتمان',
            min_area=85,
            max_area=115,
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='ونک',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=100,
        )

    def test_forward_and_reverse_paths_share_score_and_tier(self):
        forward = get_customer_matches(self.buyer, self.user, divar_enabled=False)
        forward_match = next(
            m for m in forward['crm_matches'] if m['property_id'] == self.prop.pk
        )
        reverse = get_property_contact_matches(self.prop, self.user)
        reverse_match = next(
            m for m in reverse['matches'] if m['customer_id'] == self.buyer.pk
        )
        self.assertEqual(forward_match['score'], reverse_match['score'])
        self.assertEqual(forward_match.get('match_tier'), reverse_match.get('match_tier'))

    def test_linked_contact_excluded_from_reverse_only(self):
        PropertyContact.objects.create(
            customer=self.buyer,
            property=self.prop,
            role='پیشنهادی',
            deal_type='خرید',
        )
        reverse = get_property_contact_matches(self.prop, self.user)
        self.assertNotIn(self.buyer.pk, {m['customer_id'] for m in reverse['matches']})
        forward = get_customer_matches(self.buyer, self.user, divar_enabled=False)
        self.assertIn(self.prop.pk, {m['property_id'] for m in forward['crm_matches']})

    def test_reverse_lists_buyer_in_property_matches(self):
        data = get_property_contact_matches(self.prop, self.user)
        self.assertIn(self.buyer.pk, {m['customer_id'] for m in data['matches']})

    def test_forward_lists_property_in_customer_matches(self):
        data = get_customer_matches(self.buyer, self.user, divar_enabled=False)
        self.assertIn(self.prop.pk, {m['property_id'] for m in data['crm_matches']})


class MatchingV3IndexCacheTests(TestCase):
    @override_settings(CACHES={
        'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
    })
    def test_index_cache_namespace_v2_and_pagination(self):
        cache.clear()
        user = User.objects.create_user(username='09128880200', phone='09128880200', password='x')
        buyer = Customer.objects.create(
            user=user,
            name='خریدار کش',
            phone='09128880201',
            customer_type='خریدار',
            budget_min=5_000_000_000,
            budget_max=20_000_000_000,
            areas='ونک',
        )
        for i in range(3):
            CRMProperty.objects.create(
                user=user,
                title=f'ونک {i}',
                property_type='آپارتمان',
                deal_mode='فروش',
                transaction_status='فعال',
                sale_price=10_000_000_000,
                neighborhood='ونک',
                city='تهران',
                area=100 + i,
            )
        key = _index_cache_key(
            user_id=user.pk,
            scope='cust',
            scope_id=buyer.pk,
            source='crm',
            fingerprint='testfp',
        )
        self.assertIn(f'crm_match_idx:{MATCH_INDEX_CACHE_NAMESPACE}:', key)
        refs, from_cache = get_or_build_index(key, lambda: build_crm_index(buyer, user, min_score=25))
        self.assertFalse(from_cache)
        self.assertGreaterEqual(len(refs), 1)
        page1 = slice_refs(refs, 1, 2)
        page2 = slice_refs(refs, 2, 2)
        self.assertEqual(len(page1), 2)
        self.assertGreaterEqual(len(page2), 1)
        refs_cached, from_cache2 = get_or_build_index(key, lambda: [])
        self.assertTrue(from_cache2)
        self.assertEqual(len(refs_cached), len(refs))


class MatchingV3UnknownTypeBuyerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09128880009', phone='09128880009', password='x')
        self.ds = Dataset.objects.create(user=self.user, name='ds-unk', is_active=True)
        self.land_buyer = Customer.objects.create(
            user=self.user,
            name='خریدار زمین',
            phone='09128880010',
            customer_type='خریدار',
            property_type='زمین',
            budget_min=5_000_000_000,
            budget_max=30_000_000_000,
        )

    def test_unknown_listing_not_scored_for_restricted_buyer(self):
        listing = Listing.objects.create(
            dataset=self.ds,
            token='no-type',
            title='فروش فوری',
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            price=10_000_000_000,
            city='شیراز',
            area=500,
            is_expired=False,
        )
        self.assertIsNone(_score_listing(self.land_buyer, listing))
