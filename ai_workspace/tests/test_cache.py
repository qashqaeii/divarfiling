"""تست کش AI — get/store با کلید یکسان."""
from django.test import TestCase

from ai_workspace.services import cache as ai_cache


class CacheTests(TestCase):
    def test_store_then_get_hit(self):
        ai_cache.store(
            'listing_summary',
            '42',
            'v1',
            'abc123hash',
            text='{"summary":"cached"}',
            data={'summary': 'cached'},
        )
        hit = ai_cache.get('listing_summary', '42', 'v1', 'abc123hash')
        self.assertIsNotNone(hit)
        self.assertEqual(hit['data']['summary'], 'cached')

    def test_different_prompt_hash_misses(self):
        ai_cache.store(
            'listing_summary',
            '42',
            'v1',
            'hash_a',
            text='{"summary":"a"}',
            data={'summary': 'a'},
        )
        self.assertIsNone(ai_cache.get('listing_summary', '42', 'v1', 'hash_b'))
