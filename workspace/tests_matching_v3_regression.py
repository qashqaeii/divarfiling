"""رگرسیون Matching V3 — geo، نوع ملک، کیفیت پیشنهاد، تقارن."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty, Customer, Dataset, Listing
from workspace.services.advertiser_signal import ADVERTISER_SIGNAL_GENUINE_PERSONAL
from workspace.services.crm_matching import (
    _score_crm_property,
    _score_listing,
    get_customer_matches,
    get_property_contact_matches,
    match_crm_properties,
)
from workspace.services.crm_matching_eval import MATCH_TIER_INSUFFICIENT, MATCH_TIER_STRONG
from workspace.services.crm_matching_geo import (
    location_tokens_equivalent,
    parse_preferred_areas,
    strip_location_prefix,
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

    def test_dataset_subcategory_medium_confidence(self):
        listing = Listing(
            dataset=self.ds,
            token='villa-ds',
            title='فروش فوری',
            data={},
        )
        detail = infer_listing_property_type_detail(listing)
        self.assertEqual(detail.property_type, 'ویلا')
        self.assertEqual(detail.source, 'dataset_subcategory')

    def test_ambiguous_title_without_structured_stays_unknown(self):
        ds = Dataset.objects.create(user=self.user, name='ds-empty', is_active=True, subcategory='')
        listing = Listing(dataset=ds, token='unk', title='فروش فوری', data={})
        detail = infer_listing_property_type_detail(listing)
        self.assertEqual(detail.property_type, '')
        self.assertEqual(detail.confidence, 'none')


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

    def test_forward_and_reverse_scores_align(self):
        forward = _score_crm_property(self.buyer, self.prop)
        reverse_item = _score_crm_property(self.buyer, self.prop)
        self.assertIsNotNone(forward)
        self.assertIsNotNone(reverse_item)
        self.assertEqual(forward['score'], reverse_item['score'])
        self.assertEqual(forward.get('match_tier'), reverse_item.get('match_tier'))

    def test_reverse_lists_buyer_in_property_matches(self):
        data = get_property_contact_matches(self.prop, self.user)
        self.assertIn(self.buyer.pk, {m['customer_id'] for m in data['matches']})

    def test_forward_lists_property_in_customer_matches(self):
        data = get_customer_matches(self.buyer, self.user, divar_enabled=False)
        self.assertIn(self.prop.pk, {m['property_id'] for m in data['crm_matches']})


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
