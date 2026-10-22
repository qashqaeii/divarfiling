"""تست تشخیص نوع ملک آگهی."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import Customer, Dataset, Listing
from workspace.services.advertiser_signal import ADVERTISER_SIGNAL_GENUINE_PERSONAL
from workspace.services.crm_matching import match_divar_listings
from workspace.services.crm_matching_types import infer_listing_property_type

User = get_user_model()


class ListingPropertyTypeInferenceTests(TestCase):
    def setUp(self):
        self.ds = Dataset.objects.create(user=User.objects.create_user(
            username='09122223333', phone='09122223333', password='x',
        ), name='ds', is_active=True)

    def test_structured_category_land(self):
        listing = Listing(
            dataset=self.ds,
            token='land-1',
            title='فروش فوری',
            data={'category': 'land'},
        )
        self.assertEqual(infer_listing_property_type(listing), 'زمین')

    def test_unknown_title_not_default_apartment(self):
        listing = Listing(dataset=self.ds, token='unk-1', title='فروش فوری', data={})
        self.assertEqual(infer_listing_property_type(listing), '')


class LandBuyerDoesNotGetAmbiguousListing(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09124443333', phone='09124443333', password='x')
        self.ds = Dataset.objects.create(user=self.user, name='ds2', is_active=True)
        self.land_buyer = Customer.objects.create(
            user=self.user,
            name='خریدار زمین',
            phone='09124443333',
            customer_type='خریدار',
            property_type='زمین',
            budget_min=5_000_000_000,
            budget_max=30_000_000_000,
        )
        self.ambiguous = Listing.objects.create(
            dataset=self.ds,
            token='amb-1',
            title='فروش فوری',
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            price=10_000_000_000,
            city='تهران',
            area=500,
            is_expired=False,
        )
        self.land = Listing.objects.create(
            dataset=self.ds,
            token='land-real',
            title='زمین مسکونی',
            data={'category': 'land'},
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            price=12_000_000_000,
            city='تهران',
            area=600,
            is_expired=False,
        )

    def test_only_land_listing_matches_land_buyer(self):
        tokens = [m['token'] for m in match_divar_listings(self.land_buyer, self.user)]
        self.assertIn(self.land.token, tokens)
        self.assertNotIn(self.ambiguous.token, tokens)
