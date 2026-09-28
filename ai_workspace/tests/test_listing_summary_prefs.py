"""تست لحن و سبک خلاصه هوشمند."""
from django.test import TestCase

from ai_workspace.constants import (
    DEFAULT_LISTING_SUMMARY_STYLE,
    DEFAULT_LISTING_SUMMARY_TONE,
    normalize_listing_summary_style,
    normalize_listing_summary_tone,
)
from ai_workspace.services.listing_summary_prefs import (
    apply_listing_summary_preferences,
    parse_listing_summary_preferences,
)


class ListingSummaryPrefsTests(TestCase):
    def test_normalize_defaults(self):
        self.assertEqual(normalize_listing_summary_tone(None), DEFAULT_LISTING_SUMMARY_TONE)
        self.assertEqual(normalize_listing_summary_style('invalid'), DEFAULT_LISTING_SUMMARY_STYLE)

    def test_parse_body(self):
        tone, style = parse_listing_summary_preferences({'tone': 'رسمی', 'style': 'واتساپ'})
        self.assertEqual(tone, 'رسمی')
        self.assertEqual(style, 'واتساپ')

    def test_apply_enriches_context(self):
        ctx = apply_listing_summary_preferences(
            {'title': 'ملک', 'content_version': 'crm-1'},
            tone='کوتاه',
            style='تحلیلی',
        )
        self.assertEqual(ctx['tone'], 'کوتاه')
        self.assertEqual(ctx['style'], 'تحلیلی')
        self.assertIn('tone_guide', ctx)
        self.assertIn('style_guide', ctx)
        self.assertIn('t=کوتاه', ctx['content_version'])
