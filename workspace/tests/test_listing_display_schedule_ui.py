"""نمایش زمان‌بندی آگهی و dedupe تب تکمیلی — UI جزئیات فایلینگ."""
from datetime import datetime

from django.test import SimpleTestCase

from workspace.services.display import (
    build_listing_display_data,
    classify_field_for_display,
    dedupe_supplementary_rows,
    format_supplementary_groups,
    transaction_profile,
)
from workspace.services.divar_listing_datetime import (
    DATA_KEY_LAST_UPDATED_AT,
    SHAMSI_KEY_PUBLISH,
)


class ListingDisplayScheduleUiTests(SimpleTestCase):
    def test_build_listing_display_data_collapses_schedule_duplicates(self):
        class Listing:
            token = 'tok2'
            title = 'تست'
            link = ''
            area = 70
            rooms = '2'
            city = 'تهران'
            neighborhood = 'نارمک'
            price = None
            deposit = 1_000_000_000
            rent = 10_000_000
            business_type = 'مالک'
            latitude = None
            longitude = None
            published_at = datetime(2026, 10, 6, 8, 37)
            expires_at = datetime(2026, 11, 6, 8, 37)
            images = []
            description = ''
            data = {
                'ایجاد آگهی': '1405/07/15 12:07',
                'تاریخ انتشار': '1405/07/15 08:37',
                'انقضا آگهی': '1405/08/15 12:07',
                'تاریخ انقضا': '1405/08/15 08:37',
            }

        profile = transaction_profile('اجاره')
        data = build_listing_display_data(Listing(), {})
        self.assertIn('تاریخ انتشار', data)
        self.assertNotIn('ایجاد آگهی', data)
        self.assertIn('تاریخ انقضا', data)
        self.assertNotIn('انقضا آگهی', data)
        groups = format_supplementary_groups(data, profile, {})
        timing = next((g for g in groups if g.get('name') == 'زمان‌بندی'), None)
        self.assertIsNotNone(timing)
        labels = [r.get('key') for r in timing.get('fields', [])]
        self.assertEqual(labels.count('تاریخ انتشار'), 1)
        self.assertEqual(labels.count('تاریخ انقضا'), 1)
        self.assertNotIn('ایجاد آگهی', labels)
        self.assertNotIn('انقضا آگهی', labels)

    def test_supplementary_collapses_publish_and_update_aliases(self):
        class Listing:
            token = 'tok3'
            title = 'تست alias'
            link = ''
            area = 80
            rooms = '2'
            city = 'تهران'
            neighborhood = 'جردن'
            price = 10_000_000_000
            deposit = None
            rent = None
            business_type = 'مشاور'
            latitude = None
            longitude = None
            published_at = None
            expires_at = None
            images = []
            description = ''
            data = {
                'تاریخ انتشار': '1405/07/15 08:37',
                SHAMSI_KEY_PUBLISH: '1405/07/15 12:07',
                'published_at_iso': '2026-10-06T05:07:00+00:00',
                'آخرین به‌روزرسانی': '1405/07/20 09:00',
                'انتشار_آخرین_به‌روزرسانی_شمسی': '1405/07/20 09:00',
                DATA_KEY_LAST_UPDATED_AT: '2026-10-13T05:30:00+00:00',
                'مشاور_نام': 'آژانس نمونه',
                'آگهی‌های فعال مشاور': '12',
            }

        profile = transaction_profile('فروش')
        data = build_listing_display_data(Listing(), {})
        self.assertIn('تاریخ انتشار', data)
        self.assertNotIn('published_at_iso', data)
        self.assertNotIn(SHAMSI_KEY_PUBLISH, data)
        self.assertIn('آخرین به‌روزرسانی', data)
        self.assertNotIn(DATA_KEY_LAST_UPDATED_AT, data)

        groups = format_supplementary_groups(data, profile, {})
        all_labels = [r.get('key') for g in groups for r in g.get('fields', [])]
        self.assertEqual(all_labels.count('تاریخ انتشار'), 1)
        self.assertEqual(all_labels.count('آخرین به‌روزرسانی'), 1)
        self.assertNotIn('published_at_iso', all_labels)
        self.assertNotIn('last_updated_at', all_labels)
        self.assertNotIn('انتشار_تاریخ_شمسی', all_labels)

        other = next((g for g in groups if g.get('name') == 'سایر'), None)
        self.assertIsNotNone(other)
        other_labels = [r.get('key') for r in other.get('fields', [])]
        self.assertIn('مشاور_نام', other_labels)

    def test_supplementary_dedupe_rows_publish_aliases(self):
        rows = [
            classify_field_for_display('تاریخ انتشار', '1405/07/15 08:37', '1405/07/15 08:37'),
            classify_field_for_display('انتشار_تاریخ_شمسی', '1405/07/15 12:07', '1405/07/15 12:07'),
            classify_field_for_display('published_at_iso', '2026-10-06T05:07:00+00:00', '2026-10-06T05:07:00+00:00'),
        ]
        out = dedupe_supplementary_rows(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['key'], 'تاریخ انتشار')
