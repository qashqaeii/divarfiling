"""تست هم‌ترازی خیابان / مکان_خیابان در import."""
from django.test import SimpleTestCase
import pandas as pd

from workspace.services.columns import row_to_listing_fields
from workspace.services.listing_street_data import (
    listing_street_backfill_plan,
    listing_street_for_display,
    property_street_for_display,
    sync_street_keys_in_listing_data,
)
from workspace.services.crm_property_share import location_display
from workspace.models import CRMProperty


class ListingStreetDataTest(SimpleTestCase):
    def test_sync_from_display_column_only(self):
        data = sync_street_keys_in_listing_data({'خیابان': 'خ میثاق دوم'})
        self.assertEqual(data['مکان_خیابان'], 'خ میثاق دوم')
        self.assertEqual(data['خیابان'], 'خ میثاق دوم')

    def test_does_not_overwrite_technical_key(self):
        data = sync_street_keys_in_listing_data({
            'مکان_خیابان': 'خ قدیم',
            'خیابان': 'خ جدید',
        })
        self.assertEqual(data['مکان_خیابان'], 'خ قدیم')

    def test_backfill_plan_skips_when_technical_present(self):
        ok, val = listing_street_backfill_plan({'مکان_خیابان': 'خ الف', 'خیابان': 'خ ب'})
        self.assertFalse(ok)
        self.assertEqual(val, '')

    def test_backfill_plan_when_technical_missing(self):
        ok, val = listing_street_backfill_plan({'خیابان': 'ک نیایش چهارم'})
        self.assertTrue(ok)
        self.assertEqual(val, 'ک نیایش چهارم')

    def test_row_to_listing_fields_maps_street(self):
        df = pd.DataFrame([{
            'شناسه': 'tok1',
            'عنوان': 't',
            'خیابان': 'خ آسایش ۱۱',
            'شهر': 'گرگان',
            'محله': '-',
        }])
        fields = row_to_listing_fields(df.iloc[0], df)
        self.assertEqual(fields['data'].get('مکان_خیابان'), 'خ آسایش ۱۱')

    def test_listing_street_for_display(self):
        class _Listing:
            data = {'مکان_خیابان': 'خ شهدای نفت'}

        self.assertEqual(listing_street_for_display(_Listing()), 'خ شهدای نفت')

    def test_location_display_includes_street(self):
        prop = CRMProperty(city='آبادان', feature_data={'خیابان': 'خ شهدای نفت'})
        self.assertEqual(
            location_display(prop, mask=False),
            'آبادان · خ شهدای نفت',
        )

    def test_property_street_from_amenities_text(self):
        prop = CRMProperty(
            city='آبادان',
            amenities='جنس کف: سرامیک\nخیابان: خ مهرآباد چهارم شرقی',
        )
        self.assertEqual(
            property_street_for_display(prop),
            'خ مهرآباد چهارم شرقی',
        )
        self.assertEqual(
            location_display(prop, mask=False),
            'آبادان · خ مهرآباد چهارم شرقی',
        )

    def test_amenity_dossier_excludes_street(self):
        from workspace.services.property_public_share import build_property_amenity_dossier_items

        prop = CRMProperty(
            amenities='خیابان: خ مهرآباد چهارم شرقی\nجنس کف: سرامیک',
        )
        labels = {i['label'] for i in build_property_amenity_dossier_items(prop)}
        self.assertNotIn('خیابان', labels)
        self.assertIn('جنس کف', labels)
