"""تست تشخیص سیگنال آگهی‌دهنده — مالک واقعی در برابر مشاور پنهان."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from mobile_api.services.extraction_ingest import ingest_mobile_extraction
from workspace.services.advertiser_signal import (
    ADVERTISER_SIGNAL_DISGUISED,
    ADVERTISER_SIGNAL_GENUINE_PERSONAL,
    detect_advertiser_signal,
    has_disguised_consultant_markers,
    normalize_ad_text,
)

User = get_user_model()


class AdvertiserSignalDetectionTest(TestCase):
    def test_normalize_persian_variants(self):
        self.assertEqual(normalize_ad_text('مشاور شما'), normalize_ad_text('مشاور شما'))

    def test_genuine_personal_without_markers(self):
        signal = detect_advertiser_signal(
            title='اجاره آپارتمان ۶۵ متری',
            description='واحد تمیز و نوساز. بدون واسطه.',
            business_type='personal',
        )
        self.assertEqual(signal, ADVERTISER_SIGNAL_GENUINE_PERSONAL)

    def test_disguised_consultant_with_phrase_in_description(self):
        signal = detect_advertiser_signal(
            title='اجاره آپارتمان',
            description='لطفاً همکارهای عزیز تماس نگیرید. فقط مستاجر.',
            business_type='personal',
        )
        self.assertEqual(signal, ADVERTISER_SIGNAL_DISGUISED)

    def test_disguised_consultant_with_title_marker(self):
        self.assertTrue(has_disguised_consultant_markers(
            title='فایل شخصی — مشاور شما',
            description='',
        ))

    def test_official_consultant_skips_personal_detection(self):
        signal = detect_advertiser_signal(
            title='اجاره آپارتمان',
            description='لطفاً همکارهای عزیز تماس نگیرید',
            business_type='premium-panel',
        )
        self.assertEqual(signal, 'consultant')

    def test_ingest_sets_genuine_personal_signal(self):
        user = User.objects.create_user(username='09128889900', password='x')
        detail = {
            'seo': {'web_info': {'title': 'اجاره آپارتمان ۸۰ متری', 'city_persian': 'تهران'}},
            'share': {'web_url': 'https://divar.ir/v/genuine1'},
            'webengage': {'token': 'genuine1', 'business_type': 'personal'},
            'sections': [
                {
                    'section_name': 'DESCRIPTION',
                    'widgets': [
                        {
                            'widget_type': 'DESCRIPTION',
                            'data': {'text': 'واحد نوساز، بدون واسطه. تماس مستقیم با مالک.'},
                        },
                    ],
                },
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
        result = ingest_mobile_extraction(user, {
            'filters': {
                'category': 'apartment-rent',
                'category_label': 'آپارتمان',
                'transaction_type_label': 'اجاره مسکونی',
                'city_name': 'تهران',
                'max_items': 1,
            },
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'genuine1', 'raw': detail}],
        })
        listing = result.dataset.listings.get()
        self.assertEqual(listing.advertiser_signal, ADVERTISER_SIGNAL_GENUINE_PERSONAL)
        self.assertEqual(result.genuine_personal_count, 1)
        self.assertEqual(result.disguised_consultant_count, 0)

    def test_ingest_sets_disguised_signal(self):
        user = User.objects.create_user(username='09129990011', password='x')
        detail = {
            'seo': {
                'web_info': {
                    'title': 'اجاره آپارتمان — مشاور شما در منطقه',
                    'city_persian': 'تهران',
                },
            },
            'share': {'web_url': 'https://divar.ir/v/disguised1'},
            'webengage': {'token': 'disguised1', 'business_type': 'personal'},
            'sections': [
                {
                    'section_name': 'DESCRIPTION',
                    'widgets': [
                        {
                            'widget_type': 'DESCRIPTION',
                            'data': {'text': 'مشاور شما در منطقه — همکاران تماس نگیرید.'},
                        },
                    ],
                },
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
        result = ingest_mobile_extraction(user, {
            'filters': {
                'category': 'apartment-rent',
                'category_label': 'آپارتمان',
                'transaction_type_label': 'اجاره مسکونی',
                'city_name': 'تهران',
                'max_items': 1,
            },
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'disguised1', 'raw': detail}],
        })
        listing = result.dataset.listings.get()
        self.assertEqual(listing.advertiser_signal, ADVERTISER_SIGNAL_DISGUISED)
        self.assertEqual(result.genuine_personal_count, 0)
        self.assertEqual(result.disguised_consultant_count, 1)
