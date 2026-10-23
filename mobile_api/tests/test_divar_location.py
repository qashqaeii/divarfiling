"""تست استخراج موقعیت JSON خام دیوار — مسیر موبایل."""
import copy
import json

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from mobile_api.services.divar_flatten import items_to_export_records
from mobile_api.services.divar_location import extract_post_location
from mobile_api.services.extraction_ingest import ingest_mobile_extraction
from workspace.models import Listing

User = get_user_model()

SAMPLE_CHALUS = {
    'sections': [
        {
            'section_name': 'TITLE',
            'widgets': [
                {
                    'widget_type': 'LEGEND_TITLE_ROW',
                    'data': {'title': 'واحد آپارتمان 130متر', 'subtitle': ''},
                },
                {
                    'widget_type': 'EXPANDABLE_SECTION',
                    'data': {
                        'title': '۲ هفته پیش در چالوس، خ دریای شرقی ۱',
                        'widget_list': [
                            {
                                'widget_type': 'DESCRIPTION_ROW',
                                'data': {'text': 'انتشار آگهی: ۱۳ مهر ۱۴۰۵'},
                            },
                        ],
                    },
                },
            ],
        },
    ],
    'seo': {'web_info': {'city_persian': 'چالوس', 'district_persian': ''}},
    'webengage': {'token': 'gaDbUBzO', 'city': 'chalus', 'district': ''},
    'city': {'name': 'چالوس'},
    'share': {'web_url': 'https://divar.ir/v/gaDbUBzO'},
}

def _tehran_sample():
    return copy.deepcopy({
    'sections': [
        {
            'section_name': 'TITLE',
            'widgets': [
                {
                    'widget_type': 'LEGEND_TITLE_ROW',
                    'data': {'title': '۶۰ متر یکخواب', 'subtitle': ''},
                },
                {
                    'widget_type': 'EXPANDABLE_SECTION',
                    'data': {
                        'title': 'پریروز در تهران، مرزداران، خ میثاق دوم',
                        'widget_list': [],
                    },
                },
            ],
        },
    ],
    'seo': {'web_info': {'city_persian': 'تهران', 'district_persian': 'مرزداران'}},
    'webengage': {'token': 'gaXDhvQB', 'city': 'tehran', 'district': 'marzdaran'},
    'city': {'name': 'تهران'},
    'share': {'web_url': 'https://divar.ir/v/gaXDhvQB'},
    })




def _rent_sections() -> list:
    return [
        {
            'section_name': 'LIST_DATA',
            'widgets': [
                {
                    'widget_type': 'RENT_SLIDER',
                    'data': {
                        'credit': {'value': '۵۰۰٬۰۰۰٬۰۰۰ تومان'},
                        'rent': {'value': '۱۵٬۰۰۰٬۰۰۰ تومان'},
                    },
                },
            ],
        },
    ]


def _detail_with_headline(title_line: str, **seo_web) -> dict:
    base = {
        'sections': [
            {
                'section_name': 'TITLE',
                'widgets': [
                    {
                        'widget_type': 'EXPANDABLE_SECTION',
                        'data': {'title': title_line, 'widget_list': []},
                    },
                ],
            },
            *_rent_sections(),
        ],
        'share': {'web_url': 'https://divar.ir/v/tok1'},
        'webengage': {'token': 'tok1', 'business_type': 'personal'},
    }
    if seo_web is not None:
        base['seo'] = {'web_info': seo_web}
    return base


class DivarLocationExtractTest(SimpleTestCase):
    def test_sample_chalus(self):
        loc = extract_post_location(SAMPLE_CHALUS)
        self.assertIsNone(loc['province'])
        self.assertEqual(loc['city'], 'چالوس')
        self.assertIsNone(loc['district'])
        self.assertIsNone(loc['neighborhood'])
        self.assertEqual(loc['street'], 'خ دریای شرقی ۱')
        self.assertEqual(loc['location_raw_title'], '۲ هفته پیش در چالوس، خ دریای شرقی ۱')

    def test_sample_tehran(self):
        loc = extract_post_location(_tehran_sample())
        self.assertIsNone(loc['province'])
        self.assertEqual(loc['city'], 'تهران')
        self.assertEqual(loc['district'], 'مرزداران')
        self.assertIsNone(loc['neighborhood'])
        self.assertEqual(loc['street'], 'خ میثاق دوم')

    def test_province_from_filter_only(self):
        loc = extract_post_location(_tehran_sample(), filters={'province_name': 'تهران'})
        self.assertEqual(loc['province'], 'تهران')

    def test_no_province_guess_from_city(self):
        loc = extract_post_location(SAMPLE_CHALUS)
        self.assertIsNone(loc['province'])

    def test_city_district_street_no_district(self):
        loc = extract_post_location(_detail_with_headline(
            'دیروز در اصفهان, خیابان آمادگاه',
            city_persian='اصفهان',
            district_persian='',
        ))
        self.assertEqual(loc['city'], 'اصفهان')
        self.assertIsNone(loc['district'])
        self.assertEqual(loc['street'], 'خیابان آمادگاه')

    def test_city_neighborhood_no_street(self):
        loc = extract_post_location(_detail_with_headline(
            'امروز در شیراز، محله معالی‌آباد',
            city_persian='شیراز',
            district_persian='',
        ))
        self.assertEqual(loc['neighborhood'], 'معالی‌آباد')
        self.assertIsNone(loc['street'])

    def test_city_only(self):
        loc = extract_post_location(_detail_with_headline(
            'پریروز در کرمان',
            city_persian='کرمان',
            district_persian='',
        ))
        self.assertEqual(loc['city'], 'کرمان')
        self.assertIsNone(loc['street'])

    def test_district_without_neighborhood(self):
        loc = extract_post_location(_detail_with_headline(
            '۱ روز پیش در تهران، سعادت‌آباد',
            city_persian='تهران',
            district_persian='سعادت‌آباد',
        ))
        self.assertEqual(loc['district'], 'سعادت‌آباد')
        self.assertIsNone(loc['neighborhood'])

    def test_district_neighborhood_street(self):
        loc = extract_post_location(_detail_with_headline(
            'پریروز در تهران، یوسف‌آباد، محله جهان‌آرا، خ فتحی شقاقی',
            city_persian='تهران',
            district_persian='یوسف‌آباد',
        ))
        self.assertEqual(loc['district'], 'یوسف‌آباد')
        self.assertEqual(loc['neighborhood'], 'جهان‌آرا')
        self.assertEqual(loc['street'], 'خ فتحی شقاقی')

    def test_missing_seo_web_info(self):
        detail = dict(SAMPLE_CHALUS)
        detail.pop('seo', None)
        loc = extract_post_location(detail)
        self.assertEqual(loc['city'], 'چالوس')

    def test_missing_title_section(self):
        detail = dict(SAMPLE_CHALUS)
        detail['sections'] = []
        loc = extract_post_location(detail)
        self.assertEqual(loc['city'], 'چالوس')
        self.assertIsNone(loc['street'])

    def test_missing_expandable_section(self):
        detail = {
            'seo': {'web_info': {'city_persian': 'تبریز', 'district_persian': ''}},
            'sections': [{'section_name': 'TITLE', 'widgets': []}, *_rent_sections()],
            'share': {'web_url': 'https://divar.ir/v/x'},
            'webengage': {'token': 'x', 'business_type': 'personal'},
        }
        loc = extract_post_location(detail)
        self.assertEqual(loc['city'], 'تبریز')

    def test_widget_order_independent(self):
        detail = {
            'sections': [
                {
                    'section_name': 'TITLE',
                    'widgets': [
                        {
                            'widget_type': 'LEGEND_TITLE_ROW',
                            'data': {'title': 'عنوان آگهی', 'subtitle': ''},
                        },
                        {
                            'widget_type': 'EXPANDABLE_SECTION',
                            'data': {
                                'title': 'پریروز در تهران، ونک، خ ملاصدرا',
                                'widget_list': [],
                            },
                        },
                    ],
                },
                *_rent_sections(),
            ],
            'seo': {'web_info': {'city_persian': 'تهران', 'district_persian': 'ونک'}},
            'share': {'web_url': 'https://divar.ir/v/ord'},
            'webengage': {'token': 'ord', 'business_type': 'personal'},
        }
        loc = extract_post_location(detail)
        self.assertEqual(loc['street'], 'خ ملاصدرا')

    def test_english_comma(self):
        loc = extract_post_location(_detail_with_headline(
            '2 weeks ago در رشت, خ گلسار',
            city_persian='رشت',
            district_persian='',
        ))
        self.assertEqual(loc['street'], 'خ گلسار')

    def test_invalid_headline_keeps_raw_only(self):
        loc = extract_post_location(_detail_with_headline(
            'متن نامعتبر بدون الگوی در',
            city_persian='قم',
            district_persian='',
        ))
        self.assertEqual(loc['city'], 'قم')
        self.assertIsNone(loc['street'])

    def test_street_not_assigned_to_district(self):
        loc = extract_post_location(_tehran_sample())
        self.assertEqual(loc['district'], 'مرزداران')
        self.assertNotEqual(loc['district'], loc['street'])


class DivarLocationFlattenIngestTest(TestCase):
    def _ingest(self, user, token: str, detail: dict):
        detail = dict(detail)
        detail['sections'] = [*detail.get('sections', []), *_rent_sections()]
        detail['webengage'] = {
            **(detail.get('webengage') or {}),
            'token': token,
            'business_type': (detail.get('webengage') or {}).get('business_type') or 'personal',
        }
        detail['share'] = {'web_url': f'https://divar.ir/v/{token}'}
        return ingest_mobile_extraction(user, {
            'filters': {
                'category': 'apartment-rent',
                'category_label': 'آپارتمان',
                'transaction_type_label': 'اجاره مسکونی',
                'city_name': detail.get('seo', {}).get('web_info', {}).get('city_persian', 'تهران'),
                'max_items': 1,
            },
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': token, 'raw': detail}],
        })

    def test_tehran_end_to_end_new_listing(self):
        user = User.objects.create_user(username='09131000001', password='x')
        result = self._ingest(user, 'gaXDhvQB', _tehran_sample())
        listing = result.dataset.listings.get(token='gaXDhvQB')
        self.assertEqual(listing.city, 'تهران')
        self.assertEqual(listing.neighborhood, 'مرزداران')
        self.assertEqual(listing.data.get('مکان_خیابان'), 'خ میثاق دوم')

    def test_chalus_end_to_end_new_listing(self):
        user = User.objects.create_user(username='09131000002', password='x')
        result = self._ingest(user, 'gaDbUBzO', SAMPLE_CHALUS)
        listing = result.dataset.listings.get(token='gaDbUBzO')
        self.assertEqual(listing.city, 'چالوس')
        self.assertEqual(listing.neighborhood, '')
        self.assertEqual(listing.data.get('مکان_خیابان'), 'خ دریای شرقی ۱')

    def test_existing_listing_location_not_overwritten(self):
        user = User.objects.create_user(username='09131000003', password='x')
        first = self._ingest(user, 'dup-loc', _tehran_sample())
        listing = first.dataset.listings.get(token='dup-loc')
        listing.neighborhood = 'محله_قدیمی'
        listing.city = 'شهر_قدیمی'
        listing.data = {
            'مکان_خیابان': 'خ قدیم',
            'نقشه_نوع': 'FUZZY',
            'نقشه_شعاع_محدوده_متر': 400,
            'اجاره_ماهانه_عدد': 15_000_000,
        }
        listing.deposit = 500_000_000
        listing.rent = 15_000_000
        listing.save()

        changed = copy.deepcopy(_tehran_sample())
        changed['sections'][0]['widgets'][1]['data']['title'] = (
            'پریروز در تهران، نیاوران، خ جدید'
        )
        changed['seo'] = {'web_info': {'city_persian': 'تهران', 'district_persian': 'نیاوران'}}
        self._ingest(user, 'dup-loc', changed)
        listing.refresh_from_db()
        self.assertEqual(listing.neighborhood, 'محله_قدیمی')
        self.assertEqual(listing.city, 'شهر_قدیمی')
        self.assertEqual(listing.data.get('مکان_خیابان'), 'خ قدیم')
        self.assertEqual(listing.data.get('نقشه_نوع'), 'FUZZY')
        self.assertEqual(listing.data.get('نقشه_شعاع_محدوده_متر'), 400)

    def test_empty_neighborhood_old_listing_unchanged(self):
        user = User.objects.create_user(username='09131000004', password='x')
        first = self._ingest(user, 'empty-old', SAMPLE_CHALUS)
        listing = first.dataset.listings.get(token='empty-old')
        listing.neighborhood = ''
        listing.data = {}
        listing.save()

        self._ingest(user, 'empty-old', _tehran_sample())
        listing.refresh_from_db()
        self.assertEqual(listing.neighborhood, '')
        self.assertEqual(listing.data, {})

    def test_token_matching_not_index(self):
        user = User.objects.create_user(username='09131000005', password='x')
        items = [
            {'token': 'tokB', 'raw': {**SAMPLE_CHALUS, 'webengage': {'token': 'tokB', 'business_type': 'personal'}}},
            {'token': 'tokA', 'raw': {**_tehran_sample(), 'webengage': {'token': 'tokA', 'business_type': 'personal'}}},
        ]
        records, _ = items_to_export_records(items, 'apartment-rent', max_items=10)
        by_id = {r.get('شناسه'): r for r in records}
        self.assertEqual(by_id['tokA'].get('مکان_خیابان'), 'خ میثاق دوم')
        self.assertEqual(by_id['tokB'].get('مکان_خیابان'), 'خ دریای شرقی ۱')

    def test_price_preserved_on_reingest(self):
        user = User.objects.create_user(username='09131000006', password='x')
        self._ingest(user, 'price-keep', _tehran_sample())
        listing = Listing.objects.get(token='price-keep')
        old_deposit = listing.deposit
        old_rent = listing.rent
        self._ingest(user, 'price-keep', _tehran_sample())
        listing.refresh_from_db()
        self.assertEqual(listing.deposit, old_deposit)
        self.assertEqual(listing.rent, old_rent)

    def test_location_fields_in_export_record(self):
        detail = dict(_tehran_sample())
        detail['sections'] = list(detail['sections']) + _rent_sections()
        records, _ = items_to_export_records(
            [{'token': 'gaXDhvQB', 'raw': detail}],
            'apartment-rent',
            max_items=1,
        )
        self.assertEqual(records[0].get('مکان_خیابان'), 'خ میثاق دوم')

    def test_no_sensitive_data_in_location_sources(self):
        loc = extract_post_location(_tehran_sample())
        blob = json.dumps(loc, ensure_ascii=False)
        self.assertNotIn('phone', blob.lower())
        self.assertNotIn('09', blob)
