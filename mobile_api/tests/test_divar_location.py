"""تست استخراج موقعیت JSON خام دیوار — مسیر موبایل."""
import copy
import json

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from mobile_api.services.divar_flatten import items_to_export_records
from mobile_api.services.divar_location import (
    extract_post_location,
    location_tokens_agree,
)
from mobile_api.services.extraction_ingest import ingest_mobile_extraction
from workspace.models import Dataset, Listing

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


def _headline_sections(location_headline: str, advertising_title: str = '') -> list:
    widgets = []
    if advertising_title:
        widgets.append({
            'widget_type': 'LEGEND_TITLE_ROW',
            'data': {'title': advertising_title, 'subtitle': ''},
        })
    widgets.append({
        'widget_type': 'EXPANDABLE_SECTION',
        'data': {'title': location_headline, 'widget_list': []},
    })
    return [{'section_name': 'TITLE', 'widgets': widgets}]


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


def _sell_sections() -> list:
    return [
        {
            'section_name': 'LIST_DATA',
            'widgets': [
                {
                    'widget_type': 'UNEXPANDABLE_ROW',
                    'data': {'title': 'قیمت کل', 'value': '۱۰٬۰۰۰٬۰۰۰٬۰۰۰ تومان'},
                },
            ],
        },
    ]


def _build_real_sample(
    token: str,
    location_headline: str,
    city_persian: str,
    district_persian: str = '',
    *,
    advertising_title: str = '',
    description: str = '',
    description_street: str = '',
    office_address: str = '',
    listing_feature: dict | None = None,
    category: str = 'apartment-rent',
) -> dict:
    sections = _headline_sections(location_headline, advertising_title=advertising_title)
    if description:
        sections.append({
            'section_name': 'DESCRIPTION',
            'widgets': [
                {'widget_type': 'DESCRIPTION_ROW', 'data': {'text': description}},
            ],
        })
    if category == 'apartment-sell' or category == 'partnership':
        sections.extend(_sell_sections())
    else:
        sections.extend(_rent_sections())
    if listing_feature:
        sections.append({
            'section_name': 'LIST_DATA',
            'widgets': [
                {
                    'widget_type': 'UNEXPANDABLE_ROW',
                    'data': {
                        'title': listing_feature['title'],
                        'value': listing_feature['value'],
                    },
                },
            ],
        })
    detail = {
        'sections': sections,
        'seo': {'web_info': {'city_persian': city_persian, 'district_persian': district_persian}},
        'webengage': {'token': token, 'business_type': 'personal'},
        'share': {'web_url': f'https://divar.ir/v/{token}', 'title': advertising_title},
        'city': {'name': city_persian},
    }
    if description_street:
        detail['note_street_trap'] = description_street
    if office_address:
        detail['office_address_trap'] = office_address
    return detail


def _assert_location(
    testcase,
    loc: dict,
    *,
    city=None,
    district=None,
    neighborhood=None,
    street=None,
    raw=None,
):
    testcase.assertEqual(loc.get('city'), city)
    testcase.assertEqual(loc.get('district'), district)
    testcase.assertEqual(loc.get('neighborhood'), neighborhood)
    testcase.assertEqual(loc.get('street'), street)
    if raw is not None:
        testcase.assertEqual(loc.get('location_raw_title'), raw)


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

    def test_real_sample_1_chalus(self):
        loc = extract_post_location(_build_real_sample(
            'gaDbUBzO', '۲ هفته پیش در چالوس، خ دریای شرقی ۱', 'چالوس',
        ))
        _assert_location(
            self, loc,
            city='چالوس', district=None, neighborhood=None,
            street='خ دریای شرقی ۱',
            raw='۲ هفته پیش در چالوس، خ دریای شرقی ۱',
        )

    def test_real_sample_2_tehran(self):
        loc = extract_post_location(_build_real_sample(
            'gaXDhvQB', 'پریروز در تهران، مرزداران، خ میثاق دوم', 'تهران', 'مرزداران',
        ))
        _assert_location(
            self, loc,
            city='تهران', district='مرزداران', neighborhood=None,
            street='خ میثاق دوم',
        )

    def test_real_sample_3_rasht_janbazan(self):
        loc = extract_post_location(_build_real_sample(
            'gaG7HOde', '۲ هفته پیش در رشت، جانبازان، خ نهم', 'رشت', 'جانبازان',
            category='house-villa-rent',
        ))
        _assert_location(self, loc, city='رشت', district='جانبازان', street='خ نهم')

    def test_real_sample_4_rasht_jamaran_only_district(self):
        loc = extract_post_location(_build_real_sample(
            'gabPRSqX', 'دقایقی پیش در رشت، جماران', 'رشت', 'جماران',
        ))
        _assert_location(
            self, loc,
            city='رشت', district='جماران', neighborhood=None, street=None,
            raw='دقایقی پیش در رشت، جماران',
        )

    def test_real_sample_5_dezful_street_only_from_headline(self):
        loc = extract_post_location(_build_real_sample(
            'gaUToySG',
            '۴ روز پیش در دزفول، خ حافظ',
            'دزفول',
            advertising_title='واحد آپارتمان ۹۲ متری کلید اول خیابان حافظ جنوبی',
            description='خیابان حافظ جنوبی — آدرس دفتر: خیابان انقلاب',
            category='apartment-sell',
        ))
        _assert_location(self, loc, city='دزفول', district=None, street='خ حافظ')

    def test_real_sample_6_dezful_city_only(self):
        loc = extract_post_location(_build_real_sample(
            'gaY32hxb',
            'پریروز در دزفول',
            'دزفول',
            advertising_title='فروش آپارتمان سه خواب کلید اول کوی گلریز',
            category='apartment-sell',
        ))
        _assert_location(self, loc, city='دزفول', district=None, neighborhood=None, street=None)

    def test_real_sample_7_partnership_no_street_from_ads(self):
        loc = extract_post_location(_build_real_sample(
            'gaXzcZWA',
            'پریروز در دزفول',
            'دزفول',
            advertising_title='مشارکت خیابان نونچی ۱۳۵متری',
            description='املاک مطهری: خ شریعتی بین پیام‌آوران و ارسطو',
            listing_feature={'title': 'موقعیت ملک', 'value': 'بر خیابان فرعی'},
            category='partnership',
        ))
        _assert_location(self, loc, city='دزفول', district=None, neighborhood=None, street=None)

    def test_khavar_not_street(self):
        loc = extract_post_location(_detail_with_headline(
            'پریروز در تهران، خاوران',
            city_persian='تهران',
            district_persian='خاوران',
        ))
        self.assertIsNone(loc['street'])

    def test_khorramabad_not_street(self):
        loc = extract_post_location(_detail_with_headline(
            'پریروز در خرم‌آباد',
            city_persian='خرم‌آباد',
            district_persian='',
        ))
        self.assertIsNone(loc['street'])

    def test_dot_hafiz_is_street(self):
        loc = extract_post_location(_detail_with_headline(
            'پریروز در دزفول، خ. حافظ',
            city_persian='دزفول',
            district_persian='',
        ))
        self.assertEqual(loc['street'], 'خ. حافظ')

    def test_kooche_bahar_is_street(self):
        loc = extract_post_location(_detail_with_headline(
            'پریروز در تهران، کوچه بهار',
            city_persian='تهران',
            district_persian='',
        ))
        self.assertEqual(loc['street'], 'کوچه بهار')

    def test_near_metro_not_district(self):
        loc = extract_post_location(_detail_with_headline(
            'دیروز در تهران، نزدیک مترو',
            city_persian='تهران',
            district_persian='',
        ))
        self.assertIsNone(loc['district'])
        self.assertIsNone(loc['neighborhood'])

    def test_real_divar_ad_gorgan_asayesh_11(self):
        loc = extract_post_location(_detail_with_headline(
            '۱۴ ساعت پیش در گرگان، خ آسایش ۱۱',
            city_persian='گرگان',
            district_persian='',
        ))
        self.assertEqual(loc['city'], 'گرگان')
        self.assertEqual(loc['street'], 'خ آسایش ۱۱')
        self.assertIsNone(loc['neighborhood'])

    def test_real_divar_ad_gorgan_22_bahman(self):
        loc = extract_post_location(_detail_with_headline(
            'پریروز در گرگان، خ بیست و دو بهمن غربی',
            city_persian='گرگان',
            district_persian='',
        ))
        self.assertEqual(loc['street'], 'خ بیست و دو بهمن غربی')

    def test_real_divar_ad_tehran_afsariyeh(self):
        loc = extract_post_location(_detail_with_headline(
            'هفته پیش در تهران، افسریه جنوبی، خ عنابستانی',
            city_persian='تهران',
            district_persian='افسریه جنوبی',
        ))
        self.assertEqual(loc['district'], 'افسریه جنوبی')
        self.assertEqual(loc['street'], 'خ عنابستانی')
        self.assertIsNone(loc['neighborhood'])

    def test_real_divar_ad_tehran_ahangaran_farahani(self):
        loc = extract_post_location(_detail_with_headline(
            'دیروز در تهران، آهنگران (سراسیاب دولاب)، خ شهرابی فراهانی',
            city_persian='تهران',
            district_persian='',
        ))
        self.assertEqual(loc['city'], 'تهران')
        self.assertEqual(loc['neighborhood'], 'آهنگران (سراسیاب دولاب)')
        self.assertEqual(loc['street'], 'خ شهرابی فراهانی')

    def test_real_divar_ad_tehran_mahdi_salman(self):
        loc = extract_post_location(_detail_with_headline(
            '۱ ساعت پیش در تهران، المهدی، خ سلمان فارسی',
            city_persian='تهران',
            district_persian='المهدی',
        ))
        self.assertEqual(loc['district'], 'المهدی')
        self.assertEqual(loc['street'], 'خ سلمان فارسی')

    def test_gorgan_kooche_abbrev_niayesh(self):
        loc = extract_post_location(_detail_with_headline(
            '۲ هفته پیش در گرگان، ک نیایش چهارم',
            city_persian='گرگان',
            district_persian='',
        ))
        self.assertEqual(loc['street'], 'ک نیایش چهارم')

    def test_k_dot_kooche_abbrev(self):
        loc = extract_post_location(_detail_with_headline(
            'پریروز در رشت، ک. گلسار شمالی',
            city_persian='رشت',
            district_persian='',
        ))
        self.assertEqual(loc['street'], 'ک. گلسار شمالی')

    def test_kamarbandi_not_single_k_abbrev(self):
        loc = extract_post_location(_detail_with_headline(
            'دیروز در تهران، کمربندی شرقی',
            city_persian='تهران',
            district_persian='',
        ))
        self.assertIsNone(loc['neighborhood'])
        self.assertEqual(loc['street'], 'کمربندی شرقی')

    def test_kamarbandi_in_title_only_not_street(self):
        detail = _detail_with_headline(
            'پریروز در تهران، نزدیک مترو',
            city_persian='تهران',
            district_persian='',
        )
        detail['sections'][0]['widgets'][0]['data']['title'] = 'پریروز در تهران'
        widgets = detail['sections'][0]['widgets']
        widgets.insert(0, {
            'widget_type': 'LEGEND_TITLE_ROW',
            'data': {'title': 'آپارتمان کنار کمربندی شرقی', 'subtitle': ''},
        })
        loc = extract_post_location(detail)
        self.assertIsNone(loc['street'])

    def test_token_mismatch_skips_location_merge(self):
        self.assertFalse(location_tokens_agree('tokA', {'webengage': {'token': 'tokB'}}, 'tokA'))


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
        first = self._ingest(user, 'empty-old', _tehran_sample())
        listing = first.dataset.listings.get(token='empty-old')
        listing.neighborhood = ''
        listing.data = {}
        listing.save()

        self._ingest(user, 'empty-old', _tehran_sample())
        listing.refresh_from_db()
        self.assertEqual(listing.neighborhood, '')
        self.assertEqual(listing.data.get('مکان_خیابان'), 'خ میثاق دوم')
        self.assertNotIn('مکان_شهر', listing.data)

    def test_existing_listing_empty_street_backfilled_on_reingest(self):
        user = User.objects.create_user(username='09131000010', password='x')
        first = self._ingest(user, 'fill-st', SAMPLE_CHALUS)
        listing = first.dataset.listings.get(token='fill-st')
        listing.data = {'اجاره_ماهانه_عدد': 15_000_000}
        listing.save(update_fields=['data'])

        self._ingest(user, 'fill-st', SAMPLE_CHALUS)
        listing.refresh_from_db()
        self.assertEqual(listing.data.get('مکان_خیابان'), 'خ دریای شرقی ۱')
        self.assertEqual(listing.data.get('اجاره_ماهانه_عدد'), 15_000_000)

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

    def test_dataset_columns_unchanged_on_full_duplicate_reingest(self):
        user = User.objects.create_user(username='09131000007', password='x')
        first = self._ingest(user, 'col-dup', SAMPLE_CHALUS)
        ds = first.dataset
        cols_before = list(ds.columns or [])
        self._ingest(user, 'col-dup', SAMPLE_CHALUS)
        ds.refresh_from_db()
        self.assertEqual(list(ds.columns or []), cols_before)

    def test_mixed_reingest_new_gets_street_old_unchanged(self):
        user = User.objects.create_user(username='09131000009', password='x')
        shared_hint = 'loc-mixed-shared'
        raw_first = copy.deepcopy(SAMPLE_CHALUS)
        raw_first['webengage'] = {'token': 'old-mix', 'business_type': 'personal'}
        first = ingest_mobile_extraction(user, {
            'filters': {
                'category': 'apartment-rent',
                'category_label': 'آپارتمان',
                'transaction_type_label': 'اجاره مسکونی',
                'city_name': 'چالوس',
                'max_items': 1,
                'output_name_hint': shared_hint,
            },
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'old-mix', 'raw': raw_first}],
        })
        listing = first.dataset.listings.get(token='old-mix')
        listing.neighborhood = 'قدیم'
        listing.data = {'مکان_خیابان': 'خ قدیم'}
        listing.save()
        detail_new = _build_real_sample(
            'new-mix', 'پریروز در چالوس، خ جدید', 'چالوس', '',
        )
        raw_old = copy.deepcopy(SAMPLE_CHALUS)
        raw_old['webengage'] = {'token': 'old-mix', 'business_type': 'personal'}
        common_filters = {
            'category': 'apartment-rent',
            'category_label': 'آپارتمان',
            'transaction_type_label': 'اجاره مسکونی',
            'city_name': 'چالوس',
            'max_items': 2,
            'output_name_hint': shared_hint,
        }
        result = ingest_mobile_extraction(user, {
            'filters': common_filters,
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [
                {'token': 'old-mix', 'raw': raw_old},
                {'token': 'new-mix', 'raw': detail_new},
            ],
        })
        self.assertEqual(str(result.dataset.pk), str(first.dataset.pk))
        self.assertEqual(result.created_count, 1)
        listing.refresh_from_db()
        self.assertEqual(listing.data.get('مکان_خیابان'), 'خ قدیم')
        new_listing = result.dataset.listings.get(token='new-mix')
        self.assertEqual(new_listing.data.get('مکان_خیابان'), 'خ جدید')
