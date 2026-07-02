"""تست payload نقشه جزئیات ملک."""
import json

from django.test import SimpleTestCase

from workspace.services.display import location_accuracy_for_map, transaction_profile
from workspace.services.listing_map import build_listing_map_marker


class FakeListing:
    latitude = 35.7
    longitude = 51.4
    title = 'آپارتمان تست'
    token = 'tok1'
    link = 'https://divar.ir/v/abc'
    area = 80
    rooms = '2'
    price = 5_000_000_000
    deposit = 0
    rent = 0
    price_per_sqm = 62_500_000
    neighborhood = 'ونک'
    city = 'تهران'
    business_type = 'مشاور املاک'
    published_at = None
    data = {'نوع مختصات': 'تقریبی', 'در شعاع (متر)': '500'}


class ListingMapMarkerTests(SimpleTestCase):
    def test_approx_marker_has_radius_and_kind(self):
        listing = FakeListing()
        tx = transaction_profile('فروش')
        loc = location_accuracy_for_map(listing.data)
        marker = build_listing_map_marker(listing, tx, location_accuracy=loc, public=True)

        self.assertEqual(marker['location_kind'], 'approx')
        self.assertEqual(marker['location_radius_m'], 500)
        self.assertEqual(marker['token'], '')
        self.assertIn('ونک', marker['neighborhood'])

    def test_exact_marker_has_no_radius(self):
        listing = FakeListing()
        listing.data = {'نوع مختصات': 'دقیق'}
        tx = transaction_profile('فروش')
        loc = location_accuracy_for_map(listing.data)
        marker = build_listing_map_marker(listing, tx, location_accuracy=loc)

        self.assertEqual(marker['location_kind'], 'exact')
        self.assertEqual(marker['location_radius_m'], 0)

    def test_nan_benchmark_score_serializes_as_null(self):
        listing = FakeListing()
        tx = transaction_profile('فروش')
        marker = build_listing_map_marker(
            listing,
            tx,
            benchmark={'diff_pct': float('nan'), 'verdict': ''},
        )

        self.assertIsNone(marker['value_score'])
        self.assertEqual(marker['market_tier'], 'unknown')
        encoded = json.dumps(marker, ensure_ascii=False)
        self.assertNotIn('NaN', encoded)
        self.assertIn('"value_score": null', encoded)
