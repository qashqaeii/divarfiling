"""تست fallback خلاصه آگهی."""
from django.test import TestCase

from ai_workspace.fallbacks.listing_summary import build


class ListingFallbackTests(TestCase):
    def test_build_json_structure(self):
        result = build({
            'title': 'آپارتمان ۸۵ متری',
            'neighborhood': 'سعادت‌آباد',
            'city': 'تهران',
            'price_label': '۱۲.۵ میلیارد تومان',
            'tab_financial': 'قیمت: ۱۲.۵ میلیارد تومان',
            'tab_property': 'متراژ: ۸۵ متر\nاتاق: ۲',
            'benchmark_verdict': 'زیر میانه بازار',
            'benchmark': {
                'market_median': '۱۳ میلیارد تومان',
                'diff_pct': '-8٪',
            },
        })
        data = result['data']
        self.assertIn('summary', data)
        self.assertIn('highlights', data)
        self.assertNotIn('advertiser_note', data)
        self.assertIn('زیر', data['summary'])
