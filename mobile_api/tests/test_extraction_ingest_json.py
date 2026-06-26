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
        listing = result.dataset.listings.get()
        json.dumps(listing.data, ensure_ascii=False)
