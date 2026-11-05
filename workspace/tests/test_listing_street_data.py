"""تست هم‌ترازی خیابان / مکان_خیابان در import."""
from django.test import SimpleTestCase
import pandas as pd

from workspace.services.columns import row_to_listing_fields
from workspace.services.listing_street_data import (
    listing_street_backfill_plan,
    sync_street_keys_in_listing_data,
)


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
