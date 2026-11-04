"""Matching V3.3.2 — deal intent و امنیت strong/notify."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty, Customer, Dataset, Listing
from workspace.services.advertiser_signal import ADVERTISER_SIGNAL_GENUINE_PERSONAL
from workspace.services.crm_matching import (
    _listing_match_compatible,
    _score_listing,
    match_divar_listings,
)
from workspace.services.crm_matching_deal_intent import (
    customer_deal_intent,
    property_matches_customer_deal_intent,
)
from workspace.services.crm_matching_eval import (
    MATCH_TIER_ALTERNATIVE,
    MATCH_TIER_STRONG,
    match_eligible_for_auto_notify,
)
from workspace.services.crm_matching_index import MATCH_INDEX_CACHE_NAMESPACE

User = get_user_model()


class MatchingV332DealIntentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09126661001', phone='09126661001', password='x')
        self.ds = Dataset.objects.create(user=self.user, name='ds-deal', is_active=True)
        self.purchase_lead = Customer.objects.create(
            user=self.user,
            name='سرنخ خرید 1757',
            phone='09126661002',
            customer_type='سرنخ',
            budget_max=10_500_000_000,
            areas='ونک',
        )

    def test_purchase_only_lead_intent(self):
        intent = customer_deal_intent(self.purchase_lead)
        self.assertTrue(intent.sale)
        self.assertFalse(intent.rent)
        self.assertFalse(intent.unknown)

    def test_production_case_rent_listing_rejected(self):
        rent_listing = Listing.objects.create(
            dataset=self.ds,
            token='399398',
            title='اجاره',
            city='تهران',
            neighborhood='ونک',
            deposit=2_850_000_000,
            rent=1_000,
            price=0,
            area=100,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
        )
        self.assertFalse(
            property_matches_customer_deal_intent(
                self.purchase_lead,
                is_rent_listing=True,
                is_sale_listing=False,
            )
        )
        self.assertIsNone(_score_listing(self.purchase_lead, rent_listing))

    def test_production_case_sale_listing_alternative_not_strong(self):
        sale_listing = Listing.objects.create(
            dataset=self.ds,
            token='178759',
            title='فروش',
            city='تهران',
            neighborhood='ونک',
            price=10_600_000_000,
            area=100,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
        )
        scored = _score_listing(self.purchase_lead, sale_listing)
        self.assertIsNotNone(scored)
        self.assertEqual(scored['match_tier'], MATCH_TIER_ALTERNATIVE)
        self.assertFalse(match_eligible_for_auto_notify(scored))
        self.assertGreater(scored['score'], 0)

    def test_rent_only_lead_rejects_sale_listing(self):
        rent_lead = Customer.objects.create(
            user=self.user,
            name='سرنخ اجاره',
            phone='09126661003',
            customer_type='سرنخ',
            deposit_max=500_000_000,
            rent_max=20_000_000,
        )
        sale_listing = Listing.objects.create(
            dataset=self.ds,
            token='sale-only',
            title='فروش',
            city='تهران',
            price=8_000_000_000,
            area=90,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
        )
        self.assertIsNone(_score_listing(rent_lead, sale_listing))

    def test_dual_intent_lead_matches_both_deal_types(self):
        dual = Customer.objects.create(
            user=self.user,
            name='سرنخ دوگانه',
            phone='09126661004',
            customer_type='سرنخ',
            budget_max=12_000_000_000,
            deposit_max=400_000_000,
        )
        rent_listing = Listing.objects.create(
            dataset=self.ds,
            token='dual-rent',
            title='اجاره',
            city='تهران',
            deposit=300_000_000,
            rent=15_000_000,
            area=100,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
        )
        sale_listing = Listing.objects.create(
            dataset=self.ds,
            token='dual-sale',
            title='فروش',
            city='تهران',
            price=10_000_000_000,
            area=100,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
        )
        self.assertIsNotNone(_score_listing(dual, rent_listing))
        self.assertIsNotNone(_score_listing(dual, sale_listing))

    def test_unknown_intent_lead_keeps_discovery_without_strong_from_geo(self):
        lead = Customer.objects.create(
            user=self.user,
            name='سرنخ بدون بودجه',
            phone='09126661005',
            customer_type='سرنخ',
            areas='ونک',
        )
        listing = Listing.objects.create(
            dataset=self.ds,
            token='discover',
            title='فروش',
            city='تهران',
            neighborhood='ونک',
            price=9_000_000_000,
            area=100,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
        )
        scored = _score_listing(lead, listing)
        self.assertIsNotNone(scored)
        self.assertNotEqual(scored['match_tier'], MATCH_TIER_STRONG)
        self.assertFalse(match_eligible_for_auto_notify(scored))

    def test_buyer_strong_sale_match_unchanged(self):
        buyer = Customer.objects.create(
            user=self.user,
            name='خریدار',
            phone='09126661006',
            customer_type='خریدار',
            budget_min=9_000_000_000,
            budget_max=11_000_000_000,
            areas='ونک',
        )
        listing = Listing.objects.create(
            dataset=self.ds,
            token='buyer-ok',
            title='فروش',
            city='تهران',
            neighborhood='ونک',
            price=10_000_000_000,
            area=100,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
        )
        scored = _score_listing(buyer, listing)
        self.assertIsNotNone(scored)
        self.assertEqual(scored['match_tier'], MATCH_TIER_STRONG)

    def test_rent_listing_not_in_divar_matches_for_purchase_lead(self):
        Listing.objects.create(
            dataset=self.ds,
            token='rent-x',
            title='اجاره',
            city='تهران',
            deposit=1_000_000_000,
            rent=5_000_000,
            area=100,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
        )
        Listing.objects.create(
            dataset=self.ds,
            token='sale-y',
            title='فروش',
            city='تهران',
            price=10_000_000_000,
            area=100,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
        )
        matches = match_divar_listings(self.purchase_lead, self.user)
        tokens = {m['token'] for m in matches}
        self.assertIn('sale-y', tokens)
        self.assertNotIn('rent-x', tokens)

    def test_cache_namespace_v6(self):
        self.assertEqual(MATCH_INDEX_CACHE_NAMESPACE, 'v6')
