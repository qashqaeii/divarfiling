"""تست resolve_model_label."""
from django.test import SimpleTestCase

from ai_workspace.constants import INTERNAL_MODEL_LABEL, resolve_model_label


class ResolveModelLabelTests(SimpleTestCase):
    def test_fallback_source(self):
        self.assertEqual(
            resolve_model_label(source='fallback'),
            INTERNAL_MODEL_LABEL,
        )

    def test_rule_based_provider(self):
        self.assertEqual(
            resolve_model_label(provider='rule_based'),
            INTERNAL_MODEL_LABEL,
        )

    def test_ai_model_name(self):
        self.assertEqual(
            resolve_model_label(provider='gemini', model='gemini-2.0-flash'),
            'gemini-2.0-flash',
        )

    def test_arvan_provider(self):
        self.assertEqual(
            resolve_model_label(provider='arvan', model='Gemini-2.5-Flash-lite'),
            'Gemini-2.5-Flash-lite',
        )
