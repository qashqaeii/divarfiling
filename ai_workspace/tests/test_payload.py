"""تست نرمال‌سازی payload."""
from django.test import TestCase

from ai_workspace.services.payload import (
    is_valid_listing_payload,
    normalize_listing_payload,
)


class PayloadNormalizeTests(TestCase):
    def test_nested_json_in_summary_field(self):
        raw = (
            '{\n  "summary": "واحد قدرالسهم ۱۵۰ متری در ولنجک با قیمت ۹۷ میلیارد.",\n'
            '  "highlights": ["قیمت: ۹۷ میلیارد", "دو پارکینگ"]\n'
        )
        data = normalize_listing_payload({'summary': raw, 'raw': raw}, raw)
        self.assertTrue(is_valid_listing_payload(data))
        self.assertIn('ولنجک', data['summary'])
        self.assertEqual(len(data['highlights']), 2)
        self.assertNotIn('raw', data)

    def test_invalid_nested_blob_stays_invalid(self):
        data = normalize_listing_payload({'summary': '{broken', 'raw': '{broken'})
        self.assertFalse(is_valid_listing_payload(data))

    def test_strips_advertiser_note(self):
        data = normalize_listing_payload({
            'summary': 'آپارتمان ۶۵ متری در جیحون با قیمت بالاتر از میانگین بازار.',
            'highlights': ['دو خواب', 'پارکینگ'],
            'negotiation_tip': 'مذاکره برای تخفیف منطقی توصیه می‌شود.',
            'advertiser_note': 'برچسب شخصی دارد اما نشانه‌های مشاور در متن وجود دارد.',
        })
        self.assertNotIn('advertiser_note', data)
        self.assertIn('جیحون', data['summary'])
