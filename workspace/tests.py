from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from workspace.models import Dataset, Listing
from workspace.services.columns import _parse_datetime
from workspace.services.filters import sort_queryset

from workspace.services.folder_import import (
    build_file_identity,
    dataset_path_info_from_record,
    is_importable_file,
    normalize_file_identity,
    normalize_source_path,
    parse_output_relative_path,
    subcategory_match,
    transaction_match,
)
from workspace.services.importer import _bare_reupload_match, _match_score, _preserve_dataset_location_meta
from workspace.services.listing_edit import listing_edit_payload
from workspace.services.price_history import dedupe_price_history, should_record_price


class FakeDataset:
    def __init__(
        self,
        *,
        city,
        transaction_type,
        filename,
        file_identity,
        province='',
        district='',
        subcategory='',
    ):
        self.city = city
        self.district = district
        self.original_filename = filename
        self.transaction_type = transaction_type
        self.subcategory = subcategory
        self.metadata = {
            'file_identity': file_identity,
            'city': city,
            'province': province,
            'district': district,
            'subcategory': subcategory,
        }


class DateParseTests(SimpleTestCase):
    def test_jalali_datetime_becomes_aware_gregorian(self):
        dt = _parse_datetime('1405-02-27 11:20:17')
        self.assertIsNotNone(dt)
        self.assertTrue(timezone.is_aware(dt))
        self.assertEqual(dt.year, 2026)

    def test_gregorian_datetime_becomes_aware(self):
        dt = _parse_datetime('2026-03-18 10:00:00')
        self.assertIsNotNone(dt)
        self.assertTrue(timezone.is_aware(dt))
        self.assertEqual(dt.year, 2026)


class ListingEditTests(SimpleTestCase):
    def test_payload_preserves_description_newlines(self):
        class Listing:
            id = 1
            dataset_id = 9
            token = 'abc123'
            title = 'آپارتمان'
            price = None
            deposit = 2_000_000_000
            rent = 1_000
            area = 130.0
            rooms = '3'
            neighborhood = 'بریانک'
            city = 'تهران'
            latitude = 35.6
            longitude = 51.4
            business_type = 'مشاور'
            link = 'https://divar.ir/v/x'
            description = 'خط اول\n\nخط دوم'
            images = ['https://example.com/a.jpg']
            is_expired = False
            data = {
                'آدرس': 'خیابان آزادی',
                'منطقه': '۹',
                'جهت ساختمان': 'شمالی',
                'بالکن': 'دارد',
                'تعداد کل طبقات ساختمان': '5',
            }

        from workspace.services.listing_edit import apply_listing_edit_post, listing_edit_payload

        payload = listing_edit_payload(Listing())
        self.assertIn('\n\n', payload['description'])
        self.assertNotIn('\\u000A', payload['description'])
        self.assertEqual(payload['address'], 'خیابان آزادی')
        self.assertEqual(payload['district'], '۹')
        self.assertEqual(payload['total_floors'], '5')
        self.assertEqual(payload['latitude'], 35.6)
        self.assertEqual(payload['images'], ['https://example.com/a.jpg'])
        self.assertTrue(any(f['key'] == 'جهت ساختمان' for f in payload['feature_fields']))

    def test_apply_full_edit_updates_model_and_features(self):
        class Listing:
            id = 1
            dataset_id = 9
            token = 'tok'
            title = 'قدیمی'
            price = 1
            deposit = None
            rent = None
            area = 50.0
            rooms = '1'
            neighborhood = ''
            city = ''
            latitude = None
            longitude = None
            business_type = 'شخصی'
            link = ''
            description = ''
            images = []
            is_expired = False
            data = {'جهت ساختمان': 'جنوبی'}

        from workspace.services.listing_edit import apply_listing_edit_post
        import json

        listing = Listing()
        apply_listing_edit_post(listing, {
            'title': 'جدید',
            'price': '1000000000',
            'area': '85.5',
            'rooms': '2',
            'floor': '3',
            'total_floors': '8',
            'build_year': '1400',
            'elevator': '1',
            'parking': '0',
            'storage': '',
            'balcony': '1',
            'neighborhood': 'ونک',
            'city': 'تهران',
            'district': '۳',
            'address': 'خیابان ولیعصر',
            'latitude': '35.75',
            'longitude': '51.41',
            'business_type': 'مشاور',
            'is_expired': '0',
            'owner_phone': '09121234567',
            'owner_name': 'علی',
            'link': 'https://divar.ir/v/new',
            'description': 'توضیح کامل',
            'images_json': json.dumps(['https://cdn.example.com/1.jpg', 'https://cdn.example.com/2.jpg']),
            'features_json': json.dumps({'جهت ساختمان': 'شمالی', 'جنس کف': 'پارکت'}, ensure_ascii=False),
        })
        self.assertEqual(listing.title, 'جدید')
        self.assertEqual(listing.price, 1_000_000_000)
        self.assertEqual(listing.area, 85.5)
        self.assertEqual(listing.neighborhood, 'ونک')
        self.assertEqual(listing.latitude, 35.75)
        self.assertEqual(listing.longitude, 51.41)
        self.assertFalse(listing.is_expired)
        self.assertEqual(listing.images, ['https://cdn.example.com/1.jpg', 'https://cdn.example.com/2.jpg'])
        self.assertEqual(listing.data.get('آدرس'), 'خیابان ولیعصر')
        self.assertEqual(listing.data.get('منطقه'), '۳')
        self.assertEqual(listing.data.get('طبقه'), '3')
        self.assertEqual(listing.data.get('تعداد کل طبقات ساختمان'), '8')
        self.assertEqual(listing.data.get('آسانسور'), 'دارد')
        self.assertEqual(listing.data.get('پارکینگ'), 'ندارد')
        self.assertEqual(listing.data.get('بالکن'), 'دارد')
        self.assertEqual(listing.data.get('جهت ساختمان'), 'شمالی')
        self.assertEqual(listing.data.get('جنس کف'), 'پارکت')
        self.assertEqual(listing.data.get('شماره تماس'), '09121234567')
        self.assertEqual(listing.data.get('توضیحات'), 'توضیح کامل')
        self.assertEqual(listing.data.get('عنوان'), 'جدید')
        self.assertEqual(listing.data.get('محله'), 'ونک')


class PriceHistoryTests(SimpleTestCase):
    def test_dedupe_keeps_latest_per_price_snapshot(self):
        class Ph:
            def __init__(self, price, deposit, rent):
                self.price = price
                self.deposit = deposit
                self.rent = rent

        records = [
            Ph(100, 200, 300),
            Ph(100, 200, 300),
            Ph(100, 200, 300),
            Ph(100, 250, 300),
            Ph(100, 250, 300),
        ]
        out = dedupe_price_history(records)
        self.assertEqual(len(out), 2)
        self.assertEqual((out[0].deposit, out[1].deposit), (200, 250))

    def test_should_record_price_skips_unchanged(self):
        cache = {}
        self.assertTrue(should_record_price(cache, 'tok1', 100, 200, 300))
        self.assertFalse(should_record_price(cache, 'tok1', 100, 200, 300))
        self.assertTrue(should_record_price(cache, 'tok1', 100, 250, 300))
        self.assertFalse(should_record_price(cache, 'tok1', 100, 250, 300))


class FileIdentityTests(SimpleTestCase):
    def test_excel_lock_file_is_skipped(self):
        self.assertFalse(is_importable_file('تهران/بریانک/~$15اجاره_آپارتمان.xlsx'))
        self.assertTrue(is_importable_file('تهران/بریانک/اجاره_آپارتمان.xlsx'))

    def test_folder_path_strips_extension(self):
        pi = parse_output_relative_path('فارس/شیراز/فروش_آپارتمان.xlsx')
        ident = build_file_identity(pi, 'فروش_آپارتمان.xlsx')
        self.assertEqual(ident, 'فارس/شیراز/فروش_آپارتمان')
        self.assertNotIn('.xlsx', ident)

    def test_single_level_folder_is_city(self):
        pi = parse_output_relative_path('شیراز/فروش_آپارتمان.xlsx')
        self.assertEqual(pi['city'], 'شیراز')
        self.assertEqual(pi['province'], '')

    def test_legacy_single_upload_matches_folder(self):
        legacy = FakeDataset(
            city='شیراز',
            transaction_type='فروش مسکونی',
            filename='فروش_آپارتمان.xlsx',
            file_identity='شیراز/فروش_آپارتمان',
            subcategory='آپارتمان',
        )
        folder_pi = parse_output_relative_path('فارس/شیراز/فروش_آپارتمان.xlsx')
        folder_id = build_file_identity(folder_pi, 'فروش_آپارتمان.xlsx')
        score = _match_score(legacy, folder_pi, 'فروش_آپارتمان.xlsx', folder_id)
        self.assertGreaterEqual(score, 950)

    def test_rent_does_not_match_sale_dataset(self):
        sale = FakeDataset(
            city='شیراز',
            transaction_type='فروش مسکونی',
            filename='فروش_آپارتمان.xlsx',
            file_identity='شیراز/فروش_آپارتمان',
        )
        rent_pi = parse_output_relative_path('فارس/شیراز/اجاره_آپارتمان.xlsx')
        rent_id = build_file_identity(rent_pi, 'اجاره_آپارتمان.xlsx')
        score = _match_score(sale, rent_pi, 'اجاره_آپارتمان.xlsx', rent_id)
        self.assertEqual(score, 0)
        self.assertFalse(
            transaction_match(
                sale.transaction_type,
                sale.original_filename,
                rent_pi,
                'اجاره_آپارتمان.xlsx',
            )
        )

    def test_normalize_file_identity_legacy_with_extension(self):
        self.assertEqual(
            normalize_file_identity('فارس/شیراز/فروش_آپارتمان.xlsx'),
            'فارس/شیراز/فروش_آپارتمان',
        )

    def test_strip_output_from_parent_path(self):
        path = 'DIVAR-SCRAPER/output/فارس/شیراز/فروش_آپارتمان.xlsx'
        self.assertEqual(
            normalize_source_path(path),
            'فارس/شیراز/فروش_آپارتمان.xlsx',
        )
        pi = parse_output_relative_path(path)
        self.assertEqual(pi['city'], 'شیراز')
        self.assertEqual(pi['province'], 'فارس')

    def test_different_districts_do_not_match(self):
        a = FakeDataset(
            city='تهران',
            district='قیطریه',
            transaction_type='فروش مسکونی',
            filename='فروش_آپارتمان.xlsx',
            file_identity='تهران/تهران/قیطریه/فروش_آپارتمان',
            province='تهران',
        )
        b_pi = parse_output_relative_path('تهران/تهران/بریانک/فروش_آپارتمان.xlsx')
        b_id = build_file_identity(b_pi, 'فروش_آپارتمان.xlsx')
        self.assertEqual(_match_score(a, b_pi, 'فروش_آپارتمان.xlsx', b_id), 0)

    def test_canonical_identity_from_old_record(self):
        rec = dataset_path_info_from_record(
            'شیراز', '', 'فروش_آپارتمان.xlsx',
            {'file_identity': 'شیراز/فروش_آپارتمان', 'city': 'شیراز'},
        )
        folder_pi = parse_output_relative_path('output/فارس/شیراز/فروش_آپارتمان.xlsx')
        self.assertEqual(
            build_file_identity(rec, 'فروش_آپارتمان.xlsx'),
            'شیراز/فروش_آپارتمان',
        )
        folder_id = build_file_identity(folder_pi, 'فروش_آپارتمان.xlsx')
        legacy = FakeDataset(
            city='شیراز',
            transaction_type='فروش مسکونی',
            filename='فروش_آپارتمان.xlsx',
            file_identity='شیراز/فروش_آپارتمان',
            subcategory='آپارتمان',
        )
        self.assertGreaterEqual(
            _match_score(legacy, folder_pi, 'فروش_آپارتمان.xlsx', folder_id),
            950,
        )

    def test_different_subcategories_same_city_do_not_match(self):
        apt = FakeDataset(
            city='شهرک غرب',
            transaction_type='فروش مسکونی',
            filename='فروش_آپارتمان.xlsx',
            file_identity='شهرک غرب/فروش_آپارتمان',
            subcategory='آپارتمان',
        )
        office_name = 'فروش اداری تجاری_دفتر_کار_اتاق_اداری_مطب.xlsx'
        office_pi = parse_output_relative_path(f'شهرک غرب/{office_name}')
        office_id = build_file_identity(office_pi, office_name)
        self.assertEqual(
            _match_score(apt, office_pi, office_name, office_id),
            0,
        )
        self.assertFalse(
            subcategory_match(
                apt.subcategory,
                apt.original_filename,
                apt.metadata,
                office_pi,
                office_name,
            )
        )

    def test_shop_rent_does_not_match_apartment_rent(self):
        apt = FakeDataset(
            city='شهرک غرب',
            transaction_type='اجاره مسکونی',
            filename='اجاره_آپارتمان.xlsx',
            file_identity='شهرک غرب/اجاره_آپارتمان',
            subcategory='آپارتمان',
        )
        shop_name = 'اجاره اداری تجاری_مغازه_و_غرفه.xlsx'
        shop_pi = parse_output_relative_path(f'شهرک غرب/{shop_name}')
        shop_id = build_file_identity(shop_pi, shop_name)
        self.assertEqual(_match_score(apt, shop_pi, shop_name, shop_id), 0)

    def test_bare_reupload_matches_folder_briyanak_rent(self):
        """آپلود تکی اجاره_آپارتمان باید به فایل قبلی بریانک وصل شود."""
        folder_ds = FakeDataset(
            city='تهران',
            district='بریانک',
            transaction_type='اجاره مسکونی',
            filename='اجاره_آپارتمان.xlsx',
            file_identity='تهران/تهران/بریانک/اجاره_آپارتمان',
            province='تهران',
            subcategory='آپارتمان',
        )
        bare_pi = {
            'tx_slug': 'اجاره_آپارتمان',
            'transaction_type': 'اجاره مسکونی',
            'subcategory': 'آپارتمان',
        }
        bare_id = build_file_identity(bare_pi, 'اجاره_آپارتمان.xlsx')
        score = _match_score(folder_ds, bare_pi, 'اجاره_آپارتمان.xlsx', bare_id)
        self.assertGreaterEqual(score, 950)

    def test_bare_reupload_match_single_candidate(self):
        class _FakeQS:
            def __init__(self, items):
                self._items = items

            def filter(self, **kwargs):
                if 'original_filename' in kwargs:
                    fn = kwargs['original_filename']
                    return _FakeQS([i for i in self._items if i.original_filename == fn])
                return self

            def __iter__(self):
                return iter(self._items)

        ds = FakeDataset(
            city='تهران',
            district='بریانک',
            transaction_type='اجاره مسکونی',
            filename='اجاره_آپارتمان.xlsx',
            file_identity='تهران/تهران/بریانک/اجاره_آپارتمان',
            subcategory='آپارتمان',
        )
        bare_pi = {
            'tx_slug': 'اجاره_آپارتمان',
            'transaction_type': 'اجاره مسکونی',
            'subcategory': 'آپارتمان',
        }
        hit = _bare_reupload_match(_FakeQS([ds]), 'اجاره_آپارتمان.xlsx', bare_pi)
        self.assertIs(hit, ds)

    def test_preserve_location_meta_on_bare_reupload(self):
        class DS:
            city = 'تهران'
            district = 'بریانک'
            transaction_type = 'اجاره مسکونی'
            subcategory = 'آپارتمان'
            metadata = {
                'file_identity': 'تهران/تهران/بریانک/اجاره_آپارتمان',
                'source_path': 'تهران/تهران/بریانک/اجاره_آپارتمان.xlsx',
                'province': 'تهران',
                'city': 'تهران',
                'district': 'بریانک',
            }

        out = _preserve_dataset_location_meta(
            {'file_identity': 'اجاره_آپارتمان'},
            {'tx_slug': 'اجاره_آپارتمان'},
            DS(),
        )
        self.assertEqual(out['district'], 'بریانک')
        self.assertEqual(out['file_identity'], 'تهران/تهران/بریانک/اجاره_آپارتمان')
        self.assertEqual(out['source_path'], 'تهران/تهران/بریانک/اجاره_آپارتمان.xlsx')


class ListingMapPriceLabelTests(SimpleTestCase):
    def test_motaref_rent_shows_label_not_dash(self):
        from workspace.services.display import listing_map_price_label, transaction_profile

        class Listing:
            price = None
            deposit = None
            rent = None
            transaction_type = 'اجاره مسکونی'
            data = {
                'اجاره_ودیعه_نمایش': 'متعارف',
                'اجاره_ماهانه_نمایش': 'متعارف',
            }

        tx = transaction_profile('اجاره مسکونی')
        self.assertEqual(listing_map_price_label(Listing(), tx), 'متعارف')

    def test_numeric_rent_still_formatted(self):
        from workspace.services.display import listing_map_price_label, transaction_profile

        class Listing:
            price = None
            deposit = 500_000_000
            rent = 15_000_000
            transaction_type = 'اجاره مسکونی'
            data = {}

        tx = transaction_profile('اجاره مسکونی')
        self.assertIn('اجاره', listing_map_price_label(Listing(), tx))


class ListingFeatureTests(SimpleTestCase):
    def test_collects_extended_excel_columns(self):
        from workspace.services.listing_features import build_listing_feature_profile

        class Listing:
            data = {
                'شناسه': 'abc',
                'قیمت': 1_000_000_000,
                'سند': 'تک برگ',
                'تعداد پارکینگ': '2',
                'جنس کف': 'سنگ',
                'گرمایش': 'شوفاژ',
                'سرمایش': 'داکت اسپلیت',
                'جنس کابینت': 'های‌گلاس',
                'وضعیت سکونت': 'تخلیه',
            }
            token = 'abc'
            title = 'تست'
            business_type = ''

        profile = build_listing_feature_profile(Listing())
        raw = profile['raw']
        self.assertEqual(raw.get('سند'), 'تک برگ')
        self.assertEqual(raw.get('تعداد پارکینگ'), '2')
        self.assertEqual(raw.get('جنس کف'), 'سنگ')
        self.assertTrue(profile['has_details'])
        group_titles = {g['title'] for g in profile['groups']}
        self.assertIn('سند و مجوزها', group_titles)
        self.assertIn('امکانات رفاهی', group_titles)

    def test_core_prefers_raw_positive_over_false_base_feat(self):
        from workspace.services.listing_features import build_listing_feature_profile

        class Listing:
            data = {'آسانسور': 'دارد', 'پارکینگ': 'دارد', 'انباری': 'دارد'}
            token = 'abc'
            title = 'تست'
            business_type = ''

        profile = build_listing_feature_profile(
            Listing(),
            {'elevator': False, 'parking': False, 'storage': False},
        )
        core = {item['label']: item['state'] for item in profile['core']}
        self.assertEqual(core['آسانسور'], 'yes')
        self.assertEqual(core['پارکینگ'], 'yes')
        self.assertEqual(core['انباری'], 'yes')


class ListingFeatureMatchTests(SimpleTestCase):
    def test_parse_bool_negative_before_positive(self):
        from workspace.services.features import parse_bool_feature

        self.assertFalse(parse_bool_feature('ندارد'))
        self.assertFalse(parse_bool_feature('نداره'))
        self.assertTrue(parse_bool_feature('دارد'))
        self.assertIsNone(parse_bool_feature('-'))
        self.assertIsNone(parse_bool_feature(''))
        self.assertIsNone(parse_bool_feature(None))

    def test_build_year_not_leaked_into_direction_or_facade(self):
        from workspace.services.listing_features import _collect_raw_features

        data = {
            'ساخت': '1403',
            'جهت ساختمان': 'شمالی',
            'نمای ساختمان': 'سنگ',
            'مجوز ساخت': 'دارد',
            'تعداد کل طبقات ساختمان': '6',
            'تعداد پارکینگ': '2',
            'پارکینگ': 'دارد',
        }
        raw = _collect_raw_features(data)
        self.assertNotIn('ساخت', raw)
        self.assertEqual(raw.get('جهت ساختمان'), 'شمالی')
        self.assertEqual(raw.get('نمای ساختمان'), 'سنگ')
        self.assertEqual(raw.get('مجوز ساخت'), 'دارد')
        self.assertEqual(raw.get('تعداد کل طبقات ساختمان'), '6')
        self.assertEqual(raw.get('تعداد پارکینگ'), '2')

    def test_parking_count_rejects_boolean_has(self):
        from workspace.services.listing_features import _collect_raw_features

        data = {'تعداد پارکینگ': 'دارد', 'پارکینگ': 'دارد'}
        raw = _collect_raw_features(data)
        self.assertNotIn('تعداد پارکینگ', raw)
        self.assertEqual(raw.get('پارکینگ'), 'دارد')

    def test_get_from_data_does_not_match_sakht_substring(self):
        from workspace.services.features import _get_from_data

        data = {'ساخت': '1403', 'جهت ساختمان': 'جنوبی'}
        self.assertEqual(_get_from_data(data, ('جهت ساختمان',)), 'جنوبی')
        self.assertEqual(_get_from_data(data, ('ساخت',)), '1403')


class ListingImportMergeTests(SimpleTestCase):
    def test_merge_listing_data_keeps_existing_and_adds_features(self):
        from workspace.services.importer import _merge_listing_data, _update_listing_from_fields

        class Listing:
            title = 'قدیم'
            price = 100
            deposit = None
            rent = None
            area = 80.0
            rooms = '2'
            neighborhood = 'تست'
            city = 'تهران'
            latitude = None
            longitude = None
            business_type = ''
            description = ''
            link = ''
            images = []
            published_at = None
            expires_at = None
            data = {'جنس کف': 'سرامیک'}

        fields = {
            'title': 'جدید',
            'price': 200,
            'deposit': None,
            'rent': None,
            'area': 80.0,
            'rooms': '2',
            'neighborhood': 'تست',
            'city': 'تهران',
            'latitude': None,
            'longitude': None,
            'business_type': '',
            'description': '',
            'link': '',
            'images': [],
            'published_at': None,
            'expires_at': None,
            'data': {
                'سند': 'تک برگ',
                'گرمایش': 'شوفاژ',
                'جنس کف': '-',
            },
        }
        merged = _merge_listing_data(Listing.data, fields['data'])
        self.assertEqual(merged['جنس کف'], 'سرامیک')
        self.assertEqual(merged['سند'], 'تک برگ')
        self.assertEqual(merged['گرمایش'], 'شوفاژ')

        listing = Listing()
        self.assertTrue(_update_listing_from_fields(listing, fields))
        self.assertEqual(listing.title, 'جدید')
        self.assertEqual(listing.data['سند'], 'تک برگ')


class ListingDisplaySectionTests(SimpleTestCase):
    def test_radius_field_goes_to_location_tab(self):
        from workspace.services.display import format_sections, transaction_profile

        data = {
            'متراژ': 95,
            'شهر': 'تهران',
            'محله': 'سعادت‌آباد',
            'در شعاع (متر)': '500',
            'نوع مختصات': 'تقریبی',
        }
        sections = format_sections(data, transaction_profile('فروش'))
        self.assertIn('در شعاع (متر)', sections['مکان'])
        self.assertNotIn('در شعاع (متر)', format_sections(data, transaction_profile('فروش')).get('سایر', {}))

    def test_location_accuracy_for_map(self):
        from workspace.services.display import location_accuracy_for_map

        exact = location_accuracy_for_map({'نوع مختصات': 'دقیق'})
        self.assertEqual(exact['kind'], 'exact')
        self.assertIn('دقیق', exact['label'])

        approx = location_accuracy_for_map({
            'نوع مختصات': 'تقریبی',
            'در شعاع (متر)': '500',
        })
        self.assertEqual(approx['kind'], 'approx')
        self.assertIn('۵۰۰', approx['label'])
        self.assertIn('شعاع', approx['label'])

        fuzzy_only = location_accuracy_for_map({'نوع مختصات': 'FUZZY'})
        self.assertEqual(fuzzy_only['kind'], 'approx')
        self.assertIn('تقریبی', fuzzy_only['label'])

        radius_only = location_accuracy_for_map({'در شعاع (متر)': 300})
        self.assertEqual(radius_only['kind'], 'approx')
        self.assertIn('۳۰۰', radius_only['label'])

        empty = location_accuracy_for_map({})
        self.assertEqual(empty['label'], '')
        self.assertEqual(empty['kind'], '')
        self.assertEqual(empty['radius_m'], 0)

    def test_market_tier_from_score(self):
        from workspace.services.display import market_tier_from_score

        self.assertEqual(market_tier_from_score(-15), 'under')
        self.assertEqual(market_tier_from_score(15), 'over')
        self.assertEqual(market_tier_from_score(0), 'fair')
        self.assertEqual(market_tier_from_score(None), 'unknown')

    def test_build_listing_display_data_enriches_property_tab(self):
        from workspace.services.display import build_listing_display_data, format_sections, transaction_profile

        class Listing:
            token = 'tok1'
            title = 'آپارتمان ۹۰ متری'
            link = ''
            area = 90
            rooms = '2'
            city = 'تهران'
            neighborhood = 'صادقیه'
            price = 5_000_000_000
            deposit = None
            rent = None
            business_type = 'مشاور'
            latitude = 35.7
            longitude = 51.4
            published_at = None
            expires_at = None
            images = []
            data = {'متراژ': 90}

        feat = {'floor': '3', 'build_year': 1398, 'rooms': '2'}
        data = build_listing_display_data(Listing(), feat)
        sections = format_sections(data, transaction_profile('فروش'))

        self.assertIn('متراژ', sections['ملک'])
        self.assertIn('اتاق', sections['ملک'])
        self.assertIn('طبقه', sections['ملک'])
        self.assertIn('سال ساخت', sections['ملک'])
        self.assertIn('شهر', sections['مکان'])
        self.assertIn('محله', sections['مکان'])
        self.assertIn('عرض جغرافیایی', sections['مکان'])

    def test_feature_columns_stay_out_of_property_tab(self):
        from workspace.services.display import format_sections, transaction_profile

        data = {
            'متراژ': 80,
            'گرمایش': 'شوفاژ',
            'جنس کف': 'سرامیک',
            'مجوز ساخت': 'دارد',
        }
        sections = format_sections(data, transaction_profile('فروش'))
        self.assertIn('متراژ', sections['ملک'])
        self.assertNotIn('گرمایش', sections.get('ملک', {}))
        self.assertNotIn('مجوز ساخت', sections.get('ملک', {}))


class MarketAnalysisTests(SimpleTestCase):
    def _sample_df(self):
        import pandas as pd
        from workspace.services.valuation import _add_market_columns

        rows = []
        for i, (area, price, elev, park) in enumerate([
            (95, 22_000_000_000, True, True),
            (105, 24_000_000_000, True, False),
            (110, 23_500_000_000, False, True),
            (88, 20_000_000_000, False, False),
            (102, 22_800_000_000, True, True),
            (115, 26_000_000_000, True, True),
        ]):
            rows.append({
                'listing_id': i + 1, 'token': f't{i}', 'title': f'آگهی {i}',
                'price': price, 'deposit': None, 'rent': None, 'area': area,
                'rooms': '2', 'neighborhood': 'صادقیه', 'city': 'تهران',
                'business_type': 'مشاور', 'link': '', 'build_year': 1398,
                'floor': '3', 'elevator': elev, 'parking': park, 'storage': False,
                'amenity_count': int(elev) + int(park), 'price_per_sqm': int(price / area),
            })
        return _add_market_columns(pd.DataFrame(rows))

    def test_enrich_stats_context_links_price_and_area(self):
        from workspace.services.analyzer import compute_statistics
        from workspace.services.display import transaction_profile

        df = self._sample_df()
        tx = transaction_profile('فروش')
        stats = compute_statistics(df, 'فروش')
        self.assertIn('subtitle', stats['price'])
        self.assertIn('implied_fmt', stats['price'])
        self.assertIn('context_lines', stats['price'])

    def test_build_analysis_dashboard_segments(self):
        from workspace.services.analyzer import build_analysis_dashboard, compute_statistics
        from workspace.services.valuation import analyze_market

        df = self._sample_df()
        stats = compute_statistics(df, 'فروش')
        market = analyze_market(df, 'فروش')
        dash = build_analysis_dashboard(df, stats, market, 'فروش')
        self.assertTrue(dash['area_segments'])
        self.assertTrue(dash['professional'])
        prof = dash['professional']
        self.assertIn('price_analysis', prof)
        self.assertIn('market_depth', prof)
        self.assertIn('confidence', prof)
        self.assertTrue(prof['area_segments'])

    def test_professional_percentiles_and_depth(self):
        from workspace.services.analyzer import build_analysis_dashboard, compute_statistics
        from workspace.services.market_analytics import distribution_stats, market_depth_distribution
        from workspace.services.valuation import analyze_market

        df = self._sample_df()
        stats = compute_statistics(df, 'فروش')
        self.assertIn('p10', stats['price_per_sqm'])
        self.assertIn('range_80_fmt', stats['price_per_sqm'])
        depth = market_depth_distribution(df, 'price_per_sqm')
        self.assertIn('under_market', depth)
        market = analyze_market(df, 'فروش')
        dash = build_analysis_dashboard(df, stats, market, 'فروش', df_raw=df)
        self.assertTrue(dash['professional']['insights'])

    def test_chart_neighborhood_bar_handles_nan_median(self):
        import math
        import pandas as pd
        from workspace.services.charts import build_all_charts, chart_neighborhood_bar

        df = pd.DataFrame({
            'neighborhood': ['الهیه', 'الهیه', 'ونک', 'ونک', 'جردن'],
            'price': [float('nan'), float('nan'), 30_000_000_000, 32_000_000_000, 28_000_000_000],
            'area': [float('nan'), float('nan'), 100, 110, 90],
            'price_per_sqm': [float('nan'), float('nan'), 300_000_000, 290_000_000, 310_000_000],
        })
        chart = chart_neighborhood_bar(df)
        self.assertTrue(chart)
        self.assertFalse(any(math.isnan(v) for v in chart['datasets'][0]['data']))
        charts = build_all_charts(df, transaction_type='فروش', report={})
        self.assertIsInstance(charts, list)


class OutlierFilterTests(SimpleTestCase):
    def test_median_ratio_removes_absurd_price_per_sqm(self):
        import pandas as pd
        from workspace.services.analyzer import filter_outliers

        rows = []
        for i in range(20):
            rows.append({
                'price': 500_000_000_000,
                'area': 100.0,
                'price_per_sqm': 5_000_000_000,
            })
        rows.append({'price': 500_000, 'area': 34.0, 'price_per_sqm': 14_705})
        rows.append({'price': 600_000, 'area': 34.0, 'price_per_sqm': 17_647})
        df = pd.DataFrame(rows)
        clean = filter_outliers(df, 'فروش مسکونی')
        self.assertEqual(len(clean), 20)
        self.assertTrue((clean['price_per_sqm'] >= 100_000_000).all())


class FormattingCommercialTests(SimpleTestCase):
    def test_full_deposit_equiv_uses_30_ratio(self):
        from workspace.services.formatting import full_deposit_equiv, format_toman

        total = full_deposit_equiv(500_000_000, 12_000_000)
        self.assertEqual(total, 860_000_000)
        self.assertEqual(format_toman(total), '860 میلیون تومان')

    def test_full_deposit_equiv_handles_nan(self):
        import math

        from workspace.services.formatting import full_deposit_equiv

        self.assertIsNone(full_deposit_equiv(float('nan'), float('nan')))
        self.assertEqual(full_deposit_equiv(float('nan'), 10_000_000), 300_000_000)
        self.assertEqual(full_deposit_equiv(500_000_000, float('nan')), 500_000_000)

    def test_shop_segment_hides_build_year(self):
        from workspace.services.market_context import detect_market_context

        ctx = detect_market_context('شهرک غرب — مغازه', 'مغازه و غرفه', 'فروش اداری و تجاری')
        self.assertEqual(ctx['subcategory_key'], 'shop')
        self.assertFalse(ctx['show_build_year'])
        self.assertFalse(ctx['show_residential_amenities'])
        self.assertTrue(ctx['scenario_range_first'])


class SmartToolsTests(SimpleTestCase):
    def test_mixed_rent_calc(self):
        from workspace.services.tools import mixed_rent_calc

        r = mixed_rent_calc(deposit=50_000_000, rent=5_000_000, rate=30)
        self.assertEqual(r['full_deposit'], 200_000_000)
        self.assertEqual(r['full_rent'], 6_666_666)

    def test_compare_properties_sale(self):
        from workspace.services.tools import compare_properties

        r = compare_properties(
            {'label': 'الف', 'price': 10_000_000_000, 'area': 100},
            {'label': 'ب', 'price': 9_000_000_000, 'area': 100},
        )
        self.assertEqual(r['winner'], 'b')
        self.assertEqual(r['a']['per_sqm'], 100_000_000)

    def test_discount_calc(self):
        from workspace.services.tools import discount_calc

        r = discount_calc(10_000_000_000, 5)
        self.assertEqual(r['final_price'], 9_500_000_000)
        self.assertEqual(r['savings'], 500_000_000)

    def test_budget_max_area(self):
        from workspace.services.tools import budget_calc

        r = budget_calc(5_000_000_000, price_per_sqm=50_000_000)
        self.assertEqual(r['max_area'], 100.0)

    def test_pricing_suggest(self):
        from workspace.services.tools import pricing_suggest

        r = pricing_suggest(80, 120_000_000, adjustment_pct=5)
        self.assertEqual(r['suggested_pps'], 126_000_000)
        self.assertEqual(r['suggested_total'], 10_080_000_000)


    def test_pricing_suggest_negative(self):
        from workspace.services.tools import pricing_suggest

        base = pricing_suggest(80, 120_000_000, adjustment_pct=0)
        low = pricing_suggest(80, 120_000_000, adjustment_pct=-5)
        high = pricing_suggest(80, 120_000_000, adjustment_pct=5)
        self.assertLess(low['suggested_total'], base['suggested_total'])
        self.assertGreater(high['suggested_total'], base['suggested_total'])

    def test_pricing_suggest_banded(self):
        from workspace.services.tools_market import pricing_suggest_banded

        snap = {'median_pps': 100_000_000, 'pps_p25': 90_000_000, 'pps_p75': 110_000_000}
        r = pricing_suggest_banded(80, snap, 0)
        self.assertEqual(r['band_low'], 7_200_000_000)
        self.assertEqual(r['band_high'], 8_800_000_000)

    def test_find_value_picks_includes_sale_listings(self):
        import pandas as pd
        from workspace.services.valuation import find_value_picks

        df = pd.DataFrame([
            {
                'listing_id': 1, 'token': 'a', 'title': 'فروش ارزان', 'price': 10_000_000_000,
                'deposit': 0, 'rent': 0, 'area': 100, 'neighborhood': 'اکباتان',
                'value_score': -76.1, 'price_per_sqm': 100_000_000,
            },
            {
                'listing_id': 2, 'token': 'b', 'title': 'فروش گران', 'price': 50_000_000_000,
                'deposit': 0, 'rent': 0, 'area': 100, 'neighborhood': 'اکباتان',
                'value_score': 5.0, 'price_per_sqm': 500_000_000,
            },
        ])
        picks = find_value_picks(df, direction='below', limit=15)
        self.assertEqual(len(picks), 1)
        self.assertEqual(picks[0]['listing_id'], 1)
        self.assertIn('تومان', picks[0]['price_fmt'])


class ConsultantLandscapeTests(SimpleTestCase):
    def test_analyze_consultant_landscape_top_agency(self):
        import pandas as pd

        from workspace.services.analyzer import (
            analyze_consultant_landscape,
            build_consultant_landscape_lines,
        )

        df = pd.DataFrame([
            {'business_type': 'مشاور', 'consultant_name': 'آژانس الف', 'neighborhood': 'سعادت‌آباد'},
            {'business_type': 'مشاور', 'consultant_name': 'آژانس الف', 'neighborhood': 'سعادت‌آباد'},
            {'business_type': 'مشاور', 'consultant_name': 'آژانس ب', 'neighborhood': 'سعادت‌آباد'},
            {'business_type': 'شخصی', 'consultant_name': '', 'neighborhood': 'ونک'},
        ])
        landscape = analyze_consultant_landscape(df)
        self.assertTrue(landscape['has_data'])
        self.assertEqual(landscape['top_agency'], 'آژانس الف')
        self.assertEqual(landscape['top_agency_count'], 2)
        lines = build_consultant_landscape_lines(landscape)
        self.assertTrue(any('آژانس الف' in line for line in lines))


class AmenityValuationTests(SimpleTestCase):
    def _df_with_amenities(self):
        import pandas as pd
        from workspace.services.valuation import _add_market_columns

        rows = []
        specs = [
            (90, 20_000_000_000, True, True, True),
            (92, 19_500_000_000, True, True, True),
            (88, 21_000_000_000, True, True, True),
            (95, 17_500_000_000, False, False, False),
            (100, 18_000_000_000, False, False, False),
            (85, 17_000_000_000, False, False, False),
        ]
        for i, (area, price, elev, park, stor) in enumerate(specs):
            rows.append({
                'listing_id': i + 1, 'token': f't{i}', 'title': f'آگهی {i}',
                'price': price, 'deposit': None, 'rent': None, 'area': area,
                'rooms': '2', 'neighborhood': 'نواب', 'city': 'تهران',
                'business_type': 'شخصی', 'link': '', 'build_year': 1398,
                'floor': '3', 'elevator': elev, 'parking': park, 'storage': stor,
                'amenity_count': int(elev) + int(park) + int(stor),
                'price_per_sqm': int(price / area),
            })
        return _add_market_columns(pd.DataFrame(rows))

    def test_full_amenities_expected_higher_than_bare(self):
        from workspace.services.valuation import compute_expected_values

        df = self._df_with_amenities()
        scored = compute_expected_values(df, mode='sale')
        full_row = scored[scored['amenity_tier'] == 'full'].iloc[0]
        bare_row = scored[scored['amenity_tier'] == 'bare'].iloc[0]
        self.assertGreater(full_row['expected_total'], bare_row['expected_total'])

    def test_same_price_full_scores_better_than_bare(self):
        from workspace.services.valuation import compute_expected_values

        df = self._df_with_amenities().copy()
        same_price = 18_500_000_000
        df['price'] = same_price
        df['price_per_sqm'] = (df['price'] / df['area']).astype(int)
        scored = compute_expected_values(df, mode='sale')
        full_scored = scored[scored['amenity_tier'] == 'full'].iloc[0]
        bare_scored = scored[scored['amenity_tier'] == 'bare'].iloc[0]
        self.assertLess(full_scored['value_score'], bare_scored['value_score'])

    def test_unknown_amenities_not_penalized_as_bare(self):
        from workspace.services.valuation import classify_amenity_tier, _amenity_adjustment
        import pandas as pd

        row = pd.Series({'elevator': None, 'parking': None, 'storage': None})
        self.assertEqual(classify_amenity_tier(row), 'unknown')
        seg = pd.DataFrame({
            'elevator': [True, False, True],
            'parking': [True, False, True],
            'storage': [False, False, True],
        })
        adj = _amenity_adjustment(row, seg)
        self.assertAlmostEqual(adj, 1.0, places=2)

    def test_newer_build_year_higher_expected_value(self):
        from workspace.services.valuation import compute_expected_values, _add_market_columns
        import pandas as pd

        rows = []
        for i, year in enumerate([1390, 1392, 1391, 1400, 1402, 1401]):
            rows.append({
                'listing_id': i + 1, 'token': f'y{i}', 'title': f'آگهی {i}',
                'price': 20_000_000_000, 'deposit': None, 'rent': None, 'area': 90,
                'rooms': '2', 'neighborhood': 'نواب', 'city': 'تهران',
                'business_type': 'شخصی', 'link': '', 'build_year': year,
                'floor': '3', 'elevator': True, 'parking': True, 'storage': True,
                'balcony': None, 'pool': None, 'price_per_sqm': int(20_000_000_000 / 90),
            })
        df = _add_market_columns(pd.DataFrame(rows))
        scored = compute_expected_values(df, mode='sale')
        new_row = scored[scored['build_year'] >= 1400].iloc[0]
        old_row = scored[scored['build_year'] < 1395].iloc[0]
        self.assertGreater(new_row['expected_total'], old_row['expected_total'])
        self.assertGreater(new_row['build_year_adjustment'], old_row['build_year_adjustment'])

    def test_balcony_increases_expected_value(self):
        from workspace.services.valuation import compute_expected_values, _add_market_columns
        import pandas as pd

        base = {
            'price': 20_000_000_000, 'deposit': None, 'rent': None, 'area': 90,
            'rooms': '2', 'neighborhood': 'نواب', 'city': 'تهران',
            'business_type': 'شخصی', 'link': '', 'build_year': 1398,
            'floor': '3', 'elevator': True, 'parking': True, 'storage': True,
            'lobby': None, 'pool': None, 'roof_garden': None, 'jacuzzi': None, 'gym': None,
            'price_per_sqm': int(20_000_000_000 / 90),
        }
        rows = []
        for i, balcony in enumerate([True, True, True, False, False, False]):
            rows.append({
                **base, 'listing_id': i + 1, 'token': f'b{i}', 'title': f'آگهی {i}',
                'balcony': balcony,
            })
        df = _add_market_columns(pd.DataFrame(rows))
        scored = compute_expected_values(df, mode='sale')
        with_b = scored[scored['balcony'] == True].iloc[0]
        without_b = scored[scored['balcony'] == False].iloc[0]
        self.assertGreater(with_b['expected_total'], without_b['expected_total'])
        self.assertGreater(with_b['secondary_adjustment'], without_b['secondary_adjustment'])

    def test_pool_secondary_premium_at_same_price(self):
        from workspace.services.valuation import compute_expected_values, _add_market_columns
        import pandas as pd

        price = 20_000_000_000
        base = {
            'price': price, 'deposit': None, 'rent': None, 'area': 90,
            'rooms': '2', 'neighborhood': 'نواب', 'city': 'تهران',
            'business_type': 'شخصی', 'link': '', 'build_year': 1398,
            'floor': '3', 'elevator': True, 'parking': True, 'storage': True,
            'balcony': True, 'lobby': None, 'roof_garden': None, 'jacuzzi': None, 'gym': None,
            'price_per_sqm': int(price / 90),
        }
        rows = []
        for i, pool in enumerate([True, True, True, False, False, False]):
            rows.append({
                **base, 'listing_id': i + 1, 'token': f'p{i}', 'title': f'آگهی {i}',
                'pool': pool,
            })
        df = _add_market_columns(pd.DataFrame(rows))
        scored = compute_expected_values(df, mode='sale')
        with_pool = scored[scored['pool'] == True].iloc[0]
        no_pool = scored[scored['pool'] == False].iloc[0]
        self.assertLess(with_pool['value_score'], no_pool['value_score'])


class ListingAdvertiserSortTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='sortuser', password='pass', phone='09127777777')
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='sort-test',
            original_filename='t.xlsx',
            file_format='xlsx',
        )
        self.personal = Listing.objects.create(
            dataset=self.dataset,
            token='p1',
            title='شخصی اول',
            business_type='شخصی',
            price=100,
        )
        self.consultant = Listing.objects.create(
            dataset=self.dataset,
            token='c1',
            title='مشاور اول',
            business_type='مشاور',
            advertiser_signal='consultant',
            price=999_999,
        )
        self.genuine = Listing.objects.create(
            dataset=self.dataset,
            token='g1',
            title='مالک واقعی',
            business_type='شخصی',
            advertiser_signal='genuine_personal',
            price=50,
        )
        self.disguised = Listing.objects.create(
            dataset=self.dataset,
            token='d1',
            title='مشاور پنهان',
            business_type='شخصی',
            advertiser_signal='disguised_consultant',
            price=200,
        )

    def test_personal_listings_before_consultants(self):
        qs = sort_queryset(self.dataset.listings.all(), '-price', '-price')
        ordered = list(qs.values_list('token', flat=True))
        self.assertEqual(ordered[-1], 'c1')
        self.assertNotIn('c1', ordered[:-1])

    def test_business_type_desc_puts_consultants_first(self):
        qs = sort_queryset(self.dataset.listings.all(), '-business_type', '-price')
        ordered = list(qs.values_list('token', flat=True))
        self.assertEqual(ordered[0], 'c1')

    def test_business_type_asc_groups_by_display_category(self):
        qs = sort_queryset(self.dataset.listings.all(), 'business_type', '-price')
        ordered = list(qs.values_list('token', flat=True))
        self.assertEqual(ordered, ['g1', 'p1', 'd1', 'c1'])

    def test_business_type_desc_groups_by_display_category(self):
        qs = sort_queryset(self.dataset.listings.all(), '-business_type', '-price')
        ordered = list(qs.values_list('token', flat=True))
        self.assertEqual(ordered, ['c1', 'd1', 'p1', 'g1'])
