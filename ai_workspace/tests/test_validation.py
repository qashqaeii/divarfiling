"""تست اعتبارسنجی context قبل از LLM."""
from django.test import TestCase

from ai_workspace.constants import (
    FEATURE_CRM_MESSAGE,
    FEATURE_LISTING_SUMMARY,
    FEATURE_UPLOAD_BRIEF,
)
from ai_workspace.services.validation import prepare_context


class ValidationTests(TestCase):
    def test_listing_skip_without_price(self):
        result = prepare_context(FEATURE_LISTING_SUMMARY, {'title': 'آپارتمان'})
        self.assertTrue(result.skip_llm)
        self.assertEqual(result.reason, 'no_price')

    def test_listing_ok_with_price(self):
        result = prepare_context(
            FEATURE_LISTING_SUMMARY,
            {'title': 'آپارتمان', 'price_label': '۱۲ میلیارد'},
        )
        self.assertFalse(result.skip_llm)

    def test_listing_trims_long_description(self):
        long_desc = 'ا' * 4000
        result = prepare_context(
            FEATURE_LISTING_SUMMARY,
            {
                'title': 't',
                'price_label': 'p',
                'description_excerpt': long_desc,
            },
        )
        self.assertLessEqual(len(result.context['description_excerpt']), 3000)

    def test_upload_skip_empty(self):
        result = prepare_context(FEATURE_UPLOAD_BRIEF, {'total_files': 0, 'total_added': 0})
        self.assertTrue(result.skip_llm)
        self.assertEqual(result.reason, 'empty_upload')

    def test_crm_skip_no_name(self):
        result = prepare_context(FEATURE_CRM_MESSAGE, {'channel': 'واتساپ'})
        self.assertTrue(result.skip_llm)
        self.assertEqual(result.reason, 'no_customer_name')
