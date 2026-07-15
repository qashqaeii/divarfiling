"""تست نمایش صحیح مقادیر امکانات در پروفایل آگهی."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import Dataset, Listing
from workspace.services.features import extract_listing_features, parse_bool_feature
from workspace.services.listing_features import (
    _format_item_display,
    _feature_state,
    build_listing_amenity_dossier_items,
    build_listing_feature_profile,
)

User = get_user_model()


class ListingFeatureDisplayTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09120001122',
            phone='09120001122',
            password='testpass123',
        )
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='تست',
            original_filename='t.xlsx',
            file_format='xlsx',
            transaction_type='فروش',
            subcategory='آپارتمان',
            city='تهران',
        )

    def test_count_fields_keep_numeric_value(self):
        item = _format_item_display('تعداد واحد در طبقه', '۲')
        self.assertEqual(item['value'], '۲')
        self.assertEqual(item['state'], 'neutral')

        item1 = _format_item_display('تعداد واحد در طبقه', '1')
        self.assertEqual(item1['value'], '1')
        self.assertEqual(item1['state'], 'neutral')

        item0 = _format_item_display('تعداد پارکینگ', '0')
        self.assertEqual(item0['value'], '0')
        self.assertEqual(item0['state'], 'neutral')

    def test_bool_fields_normalize_to_darad(self):
        item = _format_item_display('بالکن', 'دارد')
        self.assertEqual(item['value'], 'دارد')
        self.assertEqual(item['state'], 'yes')
        item_no = _format_item_display('بالکن', 'ندارد')
        self.assertEqual(item_no['value'], 'ندارد')
        self.assertEqual(item_no['state'], 'no')

    def test_feature_state_does_not_treat_12_as_bool(self):
        self.assertEqual(_feature_state('12'), 'neutral')
        self.assertEqual(_feature_state('10'), 'neutral')
        self.assertIsNone(parse_bool_feature('12'))
        self.assertTrue(parse_bool_feature('1'))
        self.assertFalse(parse_bool_feature('0'))

    def test_profile_preserves_count_and_text(self):
        listing = Listing.objects.create(
            dataset=self.dataset,
            token='feat001',
            title='آپارتمان',
            data={
                'تعداد واحد در طبقه': '۴',
                'جنس کف': 'پارکت',
                'بالکن': 'دارد',
                'آسانسور': 'ندارد',
            },
        )
        profile = build_listing_feature_profile(listing, extract_listing_features(listing))
        by_key = {
            item['key']: item
            for group in profile['groups']
            for item in group['items']
        }
        self.assertEqual(by_key['تعداد واحد در طبقه']['value'], '۴')
        self.assertEqual(by_key['جنس کف']['value'], 'پارکت')
        self.assertEqual(by_key['بالکن']['value'], 'دارد')
        core = {c['key']: c for c in profile['core']}
        self.assertEqual(core['آسانسور']['value'], 'ندارد')

    def test_amenity_dossier_includes_all_features_with_tips(self):
        listing = Listing.objects.create(
            dataset=self.dataset,
            token='feat002',
            title='آپارتمان',
            data={
                'آسانسور': 'دارد',
                'پارکینگ': 'ندارد',
                'انباری': 'دارد',
                'بالکن': 'دارد',
                'گرمایش': 'شوفاژ',
                'سرمایش': 'اسپلیت',
                'سند': 'تک‌برگ',
                'لابی': 'دارد',
                'استخر': 'ندارد',
            },
        )
        feat = extract_listing_features(listing)
        items = build_listing_amenity_dossier_items(listing, feat)
        by_key = {it['key']: it for it in items}
        self.assertIn('آسانسور', by_key)
        self.assertEqual(by_key['آسانسور']['tip'], 'آسانسور: دارد')
        self.assertEqual(by_key['آسانسور']['state'], 'yes')
        self.assertTrue(by_key['آسانسور']['is_core'])
        self.assertEqual(by_key['پارکینگ']['tip'], 'پارکینگ: ندارد')
        self.assertEqual(by_key['پارکینگ']['state'], 'no')
        self.assertEqual(by_key['بالکن']['tip'], 'بالکن: دارد')
        self.assertEqual(by_key['گرمایش']['tip'], 'گرمایش: شوفاژ')
        self.assertEqual(by_key['گرمایش']['icon'], 'fa-fire')
        self.assertEqual(by_key['سند']['tip'], 'سند: تک‌برگ')
        self.assertGreaterEqual(len(items), 7)
        for it in items:
            self.assertTrue(it['tip'])
            self.assertTrue(it['icon'].startswith('fa-'))

    def test_extract_core_specs_from_attributes_and_sale_columns(self):
        """فروش بدون ستون مستقیم طبقه — استخراج از attributes."""
        listing = Listing.objects.create(
            dataset=self.dataset,
            token='sell001',
            title='فروش ۸۵ متری',
            data={
                'attributes': 'متراژ:85|ساخت:1400|اتاق:2|طبقه:3 از 5',
                'قیمت': 5000000000,
            },
        )
        feat = extract_listing_features(listing)
        self.assertEqual(feat['rooms'], '2')
        self.assertEqual(feat['build_year'], 1400)
        self.assertEqual(feat['floor'], '3 از 5')

    def test_floor_special_values(self):
        from workspace.services.features import format_floor_display, parse_floor_int

        self.assertEqual(parse_floor_int('همکف'), 0)
        self.assertEqual(parse_floor_int('زیر همکف'), -1)
        self.assertEqual(parse_floor_int('3 از 5'), 3)
        self.assertEqual(format_floor_display('همکف'), 'همکف')
        self.assertEqual(format_floor_display('3 از 5', 5), '3 از 5')
        self.assertEqual(format_floor_display(-1), 'زیر همکف')

    def test_rent_listing_with_explicit_columns(self):
        rent_dataset = Dataset.objects.create(
            user=self.user,
            name='اجاره',
            original_filename='r.xlsx',
            file_format='xlsx',
            transaction_type='اجاره',
            subcategory='آپارتمان',
            city='تهران',
        )
        listing = Listing.objects.create(
            dataset=rent_dataset,
            token='rent001',
            title='اجاره ۵۵ متری',
            rooms='1',
            data={'ساخت': '1394', 'طبقه': 'همکف', 'اتاق': '۱'},
        )
        feat = extract_listing_features(listing)
        self.assertEqual(feat['rooms'], '1')
        self.assertEqual(feat['build_year'], 1394)
        self.assertEqual(feat['floor'], 'همکف')
