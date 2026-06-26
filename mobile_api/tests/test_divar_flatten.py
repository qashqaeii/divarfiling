"""تست flatten دیوار."""
from django.test import SimpleTestCase

from mobile_api.services.divar_flatten import flatten_divar_detail, is_consultant_ad, is_roommate_ad


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
        flat = flatten_divar_detail(detail, 'abc123', 'apartment-rent')
        self.assertEqual(flat['deposit'], 500_000_000)
        self.assertEqual(flat['rent'], 15_000_000)
        self.assertIn('ودیعه', flat.get('data', {}))
        self.assertNotIn('description', flat.get('data', {}))
        self.assertNotIn('raw', flat.get('data', {}))

    def test_listing_data_has_persian_advertiser_type(self):
        detail = {
            'seo': {'web_info': {'title': 'فروش آپارتمان', 'city_persian': 'تهران'}},
            'share': {'web_url': 'https://divar.ir/v/xyz789'},
            'webengage': {'token': 'xyz789', 'business_type': 'personal'},
            'sections': [],
        }
        flat = flatten_divar_detail(detail, 'xyz789', 'apartment-rent')
        self.assertEqual(flat['data'].get('نوع آگهی دهنده'), 'شخصی')

    def test_rent_fields_and_amenities_like_windows_export(self):
        detail = {
            'seo': {
                'web_info': {
                    'title': 'آپارتمان ۱۲۵ متری',
                    'city_persian': 'تهران',
                    'district_persian': 'باغ فیض',
                },
            },
            'share': {'web_url': 'https://divar.ir/v/rent125'},
            'webengage': {
                'token': 'rent125',
                'business_type': 'personal',
                'credit': 1_000_000_000,
                'rent': 40_000_000,
            },
            'sections': [
                {
                    'section_name': 'LIST_DATA',
                    'widgets': [
                        {
                            'widget_type': 'UNEXPANDABLE_ROW',
                            'data': {'title': 'متراژ', 'value': '۱۲۵ متر'},
                        },
                        {
                            'widget_type': 'UNEXPANDABLE_ROW',
                            'data': {'title': 'ودیعه', 'value': '۱ میلیارد تومان'},
                        },
                        {
                            'widget_type': 'UNEXPANDABLE_ROW',
                            'data': {'title': 'اجاره ماهانه', 'value': '۴۰ میلیون تومان'},
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
        }
        flat = flatten_divar_detail(detail, 'rent125', 'apartment-rent')
        self.assertEqual(flat['deposit'], 1_000_000_000)
        self.assertEqual(flat['rent'], 40_000_000)
        self.assertEqual(flat['area'], 125.0)
        data = flat['data']
        self.assertIn('ودیعه', data)
        self.assertIn('اجاره ماهانه', data)
        self.assertIn('متراژ', data)
        self.assertEqual(data.get('آسانسور'), 'دارد')
        self.assertNotIn('description', data)
        self.assertNotIn('latitude', data)
