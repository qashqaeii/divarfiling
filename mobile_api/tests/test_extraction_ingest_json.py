"""تست سریال‌پذیری JSON در ingest استخراج موبایل."""
import json

import numpy as np
import pandas as pd
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from mobile_api.services.extraction_ingest import ingest_mobile_extraction
from workspace.services.columns import row_to_listing_fields

User = get_user_model()


class ExtractionIngestJsonTest(TestCase):
    def test_row_to_listing_fields_serializes_numpy_types(self):
        df = pd.DataFrame([{
            'شناسه': 'tok_numpy',
            'عنوان': 'آپارتمان تست',
            'ودیعه': np.int64(500_000_000),
            'اجاره ماهانه': np.int64(15_000_000),
            'متراژ': np.float64(65.5),
            'قیمت': np.int64(0),
        }])
        fields = row_to_listing_fields(df.iloc[0], df)
        payload = json.dumps(fields['data'], ensure_ascii=False)
        self.assertIn('ودیعه', payload)
        self.assertNotIn('int64', payload)

    def test_ingest_mobile_extraction_persists_listings(self):
        user = User.objects.create_user(username='09129998877', password='x')
        detail = {
            'seo': {'web_info': {'title': 'اجاره آپارتمان', 'city_persian': 'تهران'}},
            'share': {'web_url': 'https://divar.ir/v/ingest1'},
            'webengage': {'token': 'ingest1', 'business_type': 'personal'},
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
            'items': [{'token': 'ingest1', 'raw': detail}],
        })
        self.assertEqual(result.ingested_count, 1)
        self.assertEqual(result.created_count, 1)
        self.assertEqual(result.updated_count, 0)
        listing = result.dataset.listings.get()
        json.dumps(listing.data, ensure_ascii=False)

    def test_city_only_extraction_uses_city_name_not_dash_district(self):
        user = User.objects.create_user(username='09121112233', password='x')
        detail = {
            'seo': {'web_info': {'title': 'اجاره آپارتمان', 'city_persian': 'تهران'}},
            'share': {'web_url': 'https://divar.ir/v/ingest2'},
            'webengage': {'token': 'ingest2', 'business_type': 'personal'},
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
        result = ingest_mobile_extraction(user, {
            'filters': {
                'category': 'apartment-rent',
                'category_label': 'آپارتمان',
                'transaction_type_label': 'اجاره مسکونی',
                'city_name': 'کرج',
                'city_id': '2',
                'district_names': [],
                'max_items': 1,
                'output_name_hint': 'karaj',
            },
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'ingest2', 'raw': detail}],
        })
        self.assertEqual(result.dataset.city, 'کرج')
        self.assertEqual(result.dataset.district, '')
        self.assertIn('کرج', result.dataset.name)
        self.assertNotIn('—', result.dataset.name.split(' — ')[0])
        self.assertNotEqual(result.dataset.name.split(' — ')[0], '-')

    def test_ingest_uses_client_thumbnail_when_flatten_has_no_images(self):
        user = User.objects.create_user(username='09123334455', password='x')
        detail = {
            'seo': {'web_info': {'title': 'فروش آپارتمان', 'city_persian': 'تهران'}},
            'share': {'web_url': 'https://divar.ir/v/img1'},
            'webengage': {'token': 'img1', 'business_type': 'personal'},
            'sections': [],
        }
        thumb = 'https://s100.divarcdn.com/static/photo1.webp'
        result = ingest_mobile_extraction(user, {
            'filters': {
                'category': 'apartment-sell',
                'category_label': 'آپارتمان',
                'transaction_type_label': 'فروش مسکونی',
                'city_name': 'تهران',
                'max_items': 1,
            },
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{
                'token': 'img1',
                'raw': detail,
                'thumbnail_url': thumb,
                'image_urls': [thumb],
            }],
        })
        listing = result.dataset.listings.get()
        self.assertEqual(listing.images, [thumb])

    def test_ingest_extracts_images_from_raw_image_carousel(self):
        user = User.objects.create_user(username='09124445566', password='x')
        main_url = (
            'https://postimage01.divarcdn.com/static/photo/neda/webp_post/'
            'zXBkW8ICNLRYcdh_T4pifQ/becf62b6-1b74-4669-92cd-9577deb4b2e4.webp'
        )
        detail = {
            'seo': {'web_info': {'title': 'فروش آپارتمان', 'city_persian': 'تهران'}},
            'share': {'web_url': 'https://divar.ir/v/imgcarousel'},
            'webengage': {'token': 'imgcarousel', 'business_type': 'personal'},
            'sections': [
                {
                    'section_name': 'IMAGE',
                    'widgets': [
                        {
                            'widget_type': 'IMAGE_CAROUSEL',
                            'data': {
                                'items': [
                                    {
                                        'image_url': '',
                                        'image': {
                                            'url': main_url,
                                            'thumbnail_url': (
                                                'https://postimage01.divarcdn.com/static/photo/neda/'
                                                'webp_thumbnail/grv07UPd6lSlAD3kgTpp1Q/'
                                                'becf62b6-1b74-4669-92cd-9577deb4b2e4.webp'
                                            ),
                                        },
                                    },
                                ],
                            },
                        },
                    ],
                },
            ],
        }
        result = ingest_mobile_extraction(user, {
            'filters': {
                'category': 'apartment-sell',
                'category_label': 'آپارتمان',
                'transaction_type_label': 'فروش مسکونی',
                'city_name': 'تهران',
                'max_items': 1,
            },
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'imgcarousel', 'raw': detail}],
        })
        listing = result.dataset.listings.get()
        self.assertIn(main_url, listing.images)

    def test_ingest_maps_link_tasavir_column_to_listing_images(self):
        user = User.objects.create_user(username='09125556677', password='x')
        img_a = 'https://s100.divarcdn.com/static/a.webp'
        img_b = 'https://s100.divarcdn.com/static/b.webp'
        detail = {
            'seo': {'web_info': {'title': 'اجاره آپارتمان', 'city_persian': 'تهران'}},
            'share': {'web_url': 'https://divar.ir/v/linkcol'},
            'webengage': {'token': 'linkcol', 'business_type': 'personal'},
            'sections': [
                {
                    'section_name': 'IMAGE',
                    'widgets': [
                        {
                            'widget_type': 'IMAGE_CAROUSEL',
                            'data': {
                                'items': [
                                    {'image': {'url': img_a}},
                                    {'image': {'url': img_b}},
                                ],
                            },
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
            'items': [{'token': 'linkcol', 'raw': detail}],
        })
        listing = result.dataset.listings.get()
        self.assertEqual(len(listing.images), 2)
        self.assertIn(img_a, listing.images)
        self.assertIn(img_b, listing.images)

    def test_scheduled_ingest_skips_daily_limit_check(self):
        from unittest.mock import patch

        from mobile_api.models import MobileExtractionRun, MobileExtractionSchedule

        user = User.objects.create_user(username='09126667788', password='x')
        schedule = MobileExtractionSchedule.objects.create(
            user=user,
            title='زمان‌بندی تست',
            filters={'category': 'apartment-rent', 'max_items': 1, 'city_id': '1'},
            is_enabled=True,
            next_run_at=timezone.now(),
        )
        run = MobileExtractionRun.objects.create(
            user=user,
            schedule=schedule,
            status=MobileExtractionSchedule.RUN_STATUS_RUNNING,
        )
        detail = {
            'seo': {'web_info': {'title': 'اجاره آپارتمان', 'city_persian': 'تهران'}},
            'share': {'web_url': 'https://divar.ir/v/sched1'},
            'webengage': {'token': 'sched1', 'business_type': 'personal'},
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
        payload = {
            'run_id': run.pk,
            'filters': {
                'category': 'apartment-rent',
                'category_label': 'آپارتمان',
                'transaction_type_label': 'اجاره مسکونی',
                'city_name': 'تهران',
                'max_items': 1,
            },
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'sched1', 'raw': detail}],
        }
        with patch(
            'mobile_api.services.extraction_ingest.check_mobile_extraction_allowed',
            side_effect=ValueError('سقف استخراج روزانه تکمیل شده است.'),
        ):
            result = ingest_mobile_extraction(user, payload)
        self.assertEqual(result.ingested_count, 1)

    def test_manual_ingest_enforces_daily_limit_check(self):
        from unittest.mock import patch

        user = User.objects.create_user(username='09127778800', password='x')
        detail = {
            'seo': {'web_info': {'title': 'اجاره آپارتمان', 'city_persian': 'تهران'}},
            'share': {'web_url': 'https://divar.ir/v/manual1'},
            'webengage': {'token': 'manual1', 'business_type': 'personal'},
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
        payload = {
            'filters': {
                'category': 'apartment-rent',
                'category_label': 'آپارتمان',
                'transaction_type_label': 'اجاره مسکونی',
                'city_name': 'تهران',
                'max_items': 1,
            },
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'manual1', 'raw': detail}],
        }
        with patch(
            'mobile_api.services.extraction_ingest.check_mobile_extraction_allowed',
            side_effect=ValueError('سقف استخراج روزانه تکمیل شده است.'),
        ):
            with self.assertRaises(ValueError):
                ingest_mobile_extraction(user, payload)


def _personal_rent_detail(token: str) -> dict:
    return {
        'seo': {'web_info': {'title': 'اجاره آپارتمان', 'city_persian': 'تهران'}},
        'share': {'web_url': f'https://divar.ir/v/{token}'},
        'webengage': {'token': token, 'business_type': 'personal'},
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


def _personal_sell_detail(token: str) -> dict:
    return {
        'seo': {'web_info': {'title': 'فروش آپارتمان', 'city_persian': 'تهران'}},
        'share': {'web_url': f'https://divar.ir/v/{token}'},
        'webengage': {'token': token, 'business_type': 'personal', 'price': 8_000_000_000},
        'sections': [],
    }


class ExtractionIngestDatasetSplitTest(TestCase):
    def test_same_district_different_categories_create_separate_datasets(self):
        user = User.objects.create_user(username='09120001122', password='x')
        common_filters = {
            'city_name': 'تهران',
            'district_names': ['استاد معین'],
            'province_name': 'تهران',
            'output_name_hint': 'ostad-moein',
            'max_items': 1,
        }
        rent = ingest_mobile_extraction(user, {
            'filters': {
                **common_filters,
                'category': 'apartment-rent',
                'category_label': 'آپارتمان',
                'transaction_type_label': 'اجاره مسکونی',
            },
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'split-rent', 'raw': _personal_rent_detail('split-rent')}],
        })
        sell = ingest_mobile_extraction(user, {
            'filters': {
                **common_filters,
                'category': 'residential-sell',
                'category_label': 'آپارتمان',
                'transaction_type_label': 'فروش مسکونی',
            },
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'split-sell', 'raw': _personal_sell_detail('split-sell')}],
        })
        self.assertNotEqual(rent.dataset.pk, sell.dataset.pk)
        self.assertFalse(sell.dataset_merged)
        self.assertEqual(rent.dataset.transaction_type, 'اجاره مسکونی')
        self.assertEqual(sell.dataset.transaction_type, 'فروش مسکونی')
        self.assertEqual(rent.dataset.subcategory, 'آپارتمان')
        self.assertEqual(sell.dataset.subcategory, 'آپارتمان')
        self.assertIn('اجاره مسکونی', rent.dataset.name)
        self.assertIn('فروش مسکونی', sell.dataset.name)
        self.assertEqual(rent.dataset.listings.count(), 1)
        self.assertEqual(sell.dataset.listings.count(), 1)

    def test_same_category_same_district_merges(self):
        user = User.objects.create_user(username='09120003344', password='x')
        filters = {
            'category': 'apartment-rent',
            'category_label': 'آپارتمان',
            'transaction_type_label': 'اجاره مسکونی',
            'city_name': 'تهران',
            'district_names': ['استاد معین'],
            'output_name_hint': 'ostad-moein',
            'max_items': 1,
        }
        first = ingest_mobile_extraction(user, {
            'filters': filters,
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'merge-a', 'raw': _personal_rent_detail('merge-a')}],
        })
        second = ingest_mobile_extraction(user, {
            'filters': filters,
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'merge-b', 'raw': _personal_rent_detail('merge-b')}],
        })
        self.assertEqual(first.dataset.pk, second.dataset.pk)
        self.assertTrue(second.dataset_merged)
        self.assertEqual(second.dataset.listings.count(), 2)
