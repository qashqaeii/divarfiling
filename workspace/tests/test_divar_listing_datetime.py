"""F02/E01 — زمان آگهی دیوار (تهران، UTC، شمسی)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase
from django.utils import timezone as dj_tz

from workspace.services.divar_listing_datetime import (
    DATA_KEY_LAST_BUMPED_AT,
    DATA_KEY_LAST_UPDATED_AT,
    enrich_listing_schedule_data,
    listing_datetime_to_jalali_label,
    merge_listing_schedule_data,
    parse_divar_listing_datetime,
    resolve_listing_last_bump_jalali_label,
)
from workspace.services.display import to_jalali_display
from workspace.services.importer import _merge_listing_data, _update_listing_from_fields
from workspace.models import Listing


TEHRAN = ZoneInfo('Asia/Tehran')


class DivarListingDatetimeParseTest(SimpleTestCase):
    def test_jalali_wall_clock_tehran(self):
        dt = parse_divar_listing_datetime('1405/06/31 16:54')
        self.assertIsNotNone(dt)
        self.assertEqual(dt.tzinfo, TEHRAN)
        self.assertEqual(listing_datetime_to_jalali_label(dt), '1405/06/31 16:54')

    def test_utc_iso_not_double_shifted(self):
        dt = parse_divar_listing_datetime('2030-01-15T12:00:00Z')
        self.assertIsNotNone(dt)
        tehran = dt.astimezone(TEHRAN)
        self.assertEqual(tehran.hour, 15)
        self.assertEqual(tehran.minute, 30)

    def test_aware_tehran_not_reinterpreted(self):
        src = datetime(2026, 3, 21, 12, 0, tzinfo=TEHRAN)
        dt = parse_divar_listing_datetime(src)
        self.assertEqual(dt, src)

    def test_naive_gregorian_assumed_tehran(self):
        dt = parse_divar_listing_datetime('2026-03-21 12:00')
        self.assertEqual(dt.tzinfo, TEHRAN)

    def test_zero_and_invalid(self):
        self.assertIsNone(parse_divar_listing_datetime(''))
        self.assertIsNone(parse_divar_listing_datetime('invalid'))


class EnrichAndMergeScheduleTest(SimpleTestCase):
    def test_enrich_three_independent_dates(self):
        row = {
            'انتشار_تاریخ_شمسی': '1405/06/31 16:54',
            'انتشار_آخرین_نردبان_شمسی': '1405/07/25 10:00',
            'انتشار_آخرین_به‌روزرسانی_شمسی': '1405/07/25 10:00',
        }
        data = enrich_listing_schedule_data(row)
        self.assertIn(DATA_KEY_LAST_BUMPED_AT, data)
        self.assertIn(DATA_KEY_LAST_UPDATED_AT, data)
        self.assertNotEqual(data[DATA_KEY_LAST_BUMPED_AT], data.get('published_at_iso'))

    def test_merge_preserves_bump_when_incoming_missing(self):
        old = {
            DATA_KEY_LAST_BUMPED_AT: '2026-01-01T10:00:00+00:00',
            'انتشار_آخرین_نردبان_شمسی': '1405/07/25 10:00',
        }
        new = {'عنوان': 'جدید'}
        merged = merge_listing_schedule_data(old, new)
        self.assertEqual(merged.get(DATA_KEY_LAST_BUMPED_AT), old[DATA_KEY_LAST_BUMPED_AT])

    def test_merge_via_importer_helper(self):
        old = {'انتشار_آخرین_نردبان_شمسی': '1405/07/25 10:00', DATA_KEY_LAST_BUMPED_AT: 'x'}
        new = {'توضیحات': 'a'}
        merged = _merge_listing_data(old, new)
        self.assertEqual(merged.get(DATA_KEY_LAST_BUMPED_AT), 'x')


class ReimportSchedulePreserveTest(SimpleTestCase):
    def test_reimport_keeps_bump_without_explicit_incoming(self):
        listing = Listing(
            token='t',
            data={
                'انتشار_آخرین_نردبان_شمسی': '1405/07/25 10:00',
                DATA_KEY_LAST_BUMPED_AT: '2026-01-01T10:00:00+00:00',
            },
        )
        fields = {
            'published_at': None,
            'data': {'توضیحات': 'only desc'},
        }
        self.assertTrue(_update_listing_from_fields(listing, fields))
        self.assertEqual(listing.data.get(DATA_KEY_LAST_BUMPED_AT), '2026-01-01T10:00:00+00:00')


class ResolveLastBumpLabelTest(SimpleTestCase):
    def test_shamsi_bump_label(self):
        listing = Listing(
            token='t1',
            data={'انتشار_آخرین_نردبان_شمسی': '1405/07/25 10:00'},
        )
        self.assertEqual(resolve_listing_last_bump_jalali_label(listing), '1405/07/25 10:00')

    def test_iso_bump_label(self):
        listing = Listing(
            token='t2',
            data={DATA_KEY_LAST_BUMPED_AT: '2030-01-15T12:00:00Z'},
        )
        label = resolve_listing_last_bump_jalali_label(listing)
        self.assertTrue(label)
        self.assertIn('1408', label)

    def test_no_bump_when_only_last_updated(self):
        listing = Listing(
            token='t3',
            data={DATA_KEY_LAST_UPDATED_AT: '2030-01-15T12:00:00Z'},
        )
        self.assertEqual(resolve_listing_last_bump_jalali_label(listing), '')

    def test_no_bump_without_valid_date(self):
        listing = Listing(token='t4', data={})
        self.assertEqual(resolve_listing_last_bump_jalali_label(listing), '')


class ListingDisplayTimezoneTest(SimpleTestCase):
    def test_to_jalali_display_uses_localtime_once(self):
        dt = parse_divar_listing_datetime('1405/06/21 13:34')
        self.assertIsNotNone(dt)
        label = to_jalali_display(dt)
        self.assertEqual(label[:16], '1405/06/21 13:34')
