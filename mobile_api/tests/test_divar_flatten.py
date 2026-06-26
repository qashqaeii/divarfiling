"""تست flatten دیوار."""
from django.test import SimpleTestCase

from mobile_api.services.divar_flatten import (
    flatten_divar_detail,
    is_consultant_ad,
    is_roommate_ad,
    items_to_export_records,
)


class DivarFlattenTest(SimpleTestCase):
    def test_roommate_regex(self):
        flat = {'title': 'همخانه در تهران', 'description': ''}
        self.assertTrue(is_roommate_ad(flat, 'apartment-rent'))
        self.assertFalse(is_roommate_ad(flat, 'residential-sell'))

    def test_consultant_detection(self):
        self.assertTrue(is_consultant_ad({'business_type': 'premium-panel', 'consultant_name': ''}))
        self.assertTrue(is_consultant_ad({'business_type': '', 'consultant_name': 'آژانس نمونه'}))
        self.assertFalse(is_consultant_ad({'business_type': 'personal', 'consultant_name': ''}))

    def test_rent_slider_fallback(self):
        detail = {
            'seo': {'web_info': {'title': 'اجاره آپارتمان', 'city_persian': 'تهران'}},
            'share': {'web_url': 'https://divar.ir/v/abc123'},
            'webengage': {'token': 'abc123', 'business_type': 'personal'},
            'sections': [
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
            ],
        }
        records, _skipped = items_to_export_records(
            [{'token': 'abc123', 'raw': detail}],
            'apartment-rent',
        )
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertIn('ودیعه', rec)
        self.assertIn('اجاره ماهانه', rec)
        self.assertNotIn('description', rec)
        self.assertNotIn('latitude', rec)

    def test_listing_data_has_persian_advertiser_type(self):
        detail = {
            'seo': {'web_info': {'title': 'فروش آپارتمان', 'city_persian': 'تهران'}},
            'share': {'web_url': 'https://divar.ir/v/xyz789'},
            'webengage': {'token': 'xyz789', 'business_type': 'personal'},
            'sections': [],
        }
        records, _ = items_to_export_records(
            [{'token': 'xyz789', 'raw': detail}],
            'apartment-sell',
        )
        self.assertEqual(records[0].get('نوع آگهی دهنده'), 'شخصی')

    def test_sell_export_has_excel_columns(self):
        detail = {
            'seo': {
                'web_info': {
                    'title': 'آپارتمان ۶۵ متری',
                    'city_persian': 'تهران',
                    'district_persian': 'تجریش',
                },
            },
            'share': {'web_url': 'https://divar.ir/v/sell65'},
            'webengage': {
                'token': 'sell65',
                'business_type': 'premium-panel',
                'price': 26_000_000_000,
            },
            'sections': [
                {
                    'section_name': 'LIST_DATA',
                    'widgets': [
                        {
                            'widget_type': 'UNEXPANDABLE_ROW',
                            'data': {'title': 'متراژ', 'value': '۶۵ متر'},
                        },
                        {
                            'widget_type': 'UNEXPANDABLE_ROW',
                            'data': {'title': 'قیمت کل', 'value': '۲۶٬۰۰۰٬۰۰۰٬۰۰۰ تومان'},
                        },
                        {
                            'widget_type': 'GROUP_FEATURE_ROW',
                            'data': {
                                'items': [
                                    {'title': 'آسانسور', 'available': True},
                                    {'title': 'پارکینگ', 'available': True},
                                ],
                            },
                        },
                    ],
                },
            ],
            'business_lazy_widget_list': [
                {
                    'widget_type': 'EVENT_ROW',
                    'data': {
                        'title': 'املاک ارم شمرون',
                        'action': {'type': 'PREMIUM_PANEL_BRAND_LANDING'},
                    },
                },
            ],
        }
        records, _ = items_to_export_records(
            [{'token': 'sell65', 'raw': detail}],
            'apartment-sell',
        )
        rec = records[0]
        expected_keys = {
            'شناسه', 'عنوان', 'لینک', 'شهر', 'محله', 'متراژ', 'قیمت',
            'آسانسور', 'پارکینگ', 'نوع آگهی دهنده', 'نام مشاور / آژانس',
            'ویژگی‌ها و امکانات', 'توضیحات',
        }
        for key in expected_keys:
            self.assertIn(key, rec, msg=f'missing column {key}')
        self.assertEqual(rec.get('آسانسور'), 'دارد')
        self.assertEqual(rec.get('نوع آگهی دهنده'), 'مشاور')

    def test_flatten_divar_detail_compat(self):
        detail = {
            'seo': {'web_info': {'title': 'اجاره آپارتمان', 'city_persian': 'تهران'}},
            'share': {'web_url': 'https://divar.ir/v/abc123'},
            'webengage': {'token': 'abc123', 'business_type': 'personal'},
            'sections': [
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
            ],
        }
        flat = flatten_divar_detail(detail, 'abc123', 'apartment-rent')
        self.assertIn('ودیعه', flat.get('data', {}))
