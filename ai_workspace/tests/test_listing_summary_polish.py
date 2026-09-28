"""تست پولیش خروجی خلاصه هوشمند."""
from django.test import TestCase

from ai_workspace.services.listing_summary_polish import polish_listing_payload


class ListingSummaryPolishTests(TestCase):
    def test_summary_merges_newlines(self):
        data = polish_listing_payload({
            'summary': 'آپارتمان ۸۵ متری.\n\nدر سعادت‌آباد.',
            'highlights': ['مالی — قیمت ۱۲ میلیارد'],
            'negotiation_tip': 'با مالک برای بازدید هماهنگ کنید',
        })
        self.assertNotIn('\n', data['summary'])
        self.assertIn('سعادت', data['summary'])
        self.assertTrue(data['highlights'][0].startswith('قیمت'))
        self.assertTrue(data['negotiation_tip'].endswith('۔'))

    def test_dedupes_highlights(self):
        data = polish_listing_payload({
            'summary': 'ملک مناسب برای خانواده در محله آرام شهر.',
            'highlights': ['دو خواب', 'دو خواب', 'پارکینگ دارد'],
            'negotiation_tip': 'تاکید روی پارکینگ در معرفی اولیه به مشتری',
        })
        self.assertEqual(len(data['highlights']), 2)
