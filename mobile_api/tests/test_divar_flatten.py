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
        flat = flatten_divar_detail(detail, 'abc123')
        self.assertEqual(flat['deposit'], 500_000_000)
        self.assertEqual(flat['rent'], 15_000_000)
        self.assertEqual(flat['rent_convertibility'], 'قابل تبدیل')
