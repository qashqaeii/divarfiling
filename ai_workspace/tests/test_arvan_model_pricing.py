from decimal import Decimal

from django.test import SimpleTestCase

from ai_workspace.arvan_model_pricing import (
    aggregate_cost_from_model_rows,
    estimate_token_cost_toman,
    normalize_model_key,
)


class ArvanModelPricingTests(SimpleTestCase):
    def test_normalize_gemini(self):
        self.assertEqual(normalize_model_key('Gemini-2.5-Flash-lite'), 'gemini-2.5-flash-lite')

    def test_gemini_cost_one_m_input(self):
        cost, priced = estimate_token_cost_toman(
            model='Gemini-2.5-Flash-lite',
            input_tokens=1_000_000,
            output_tokens=0,
        )
        self.assertTrue(priced)
        self.assertEqual(cost, Decimal('21000'))

    def test_gemini_mixed_tokens(self):
        cost, _ = estimate_token_cost_toman(
            model='Gemini-2.5-Flash-lite',
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        self.assertEqual(cost, Decimal('21000') + Decimal('84000'))

    def test_deepseek_rates(self):
        cost, priced = estimate_token_cost_toman(
            model='DeepSeek-V4-Flash',
            input_tokens=2_000_000,
            output_tokens=1_000_000,
        )
        self.assertTrue(priced)
        self.assertEqual(cost, Decimal('58800') + Decimal('58800'))

    def test_unknown_model_unpriced(self):
        cost, priced = estimate_token_cost_toman(
            model='some-free-model',
            input_tokens=1000,
            output_tokens=1000,
        )
        self.assertFalse(priced)
        self.assertEqual(cost, Decimal('0'))

    def test_aggregate_coverage(self):
        summary = aggregate_cost_from_model_rows([
            {'model': 'Gemini-2.5-Flash-lite', 'sum_input': 1000, 'sum_output': 0},
            {'model': 'unknown', 'sum_input': 1000, 'sum_output': 0},
        ])
        self.assertGreater(summary['total_toman'], 0)
        self.assertEqual(summary['coverage_pct'], 50.0)
