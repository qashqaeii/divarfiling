"""Regression tests for compute_statistics edge cases."""
import pandas as pd
from django.test import SimpleTestCase

from workspace.services.analyzer import compute_statistics


class ComputeStatisticsTests(SimpleTestCase):
    def test_empty_dataframe(self):
        stats = compute_statistics(pd.DataFrame(), transaction_type='فروش')
        self.assertEqual(stats['row_count'], 0)
        self.assertNotIn('price', stats)

    def test_single_price_record(self):
        df = pd.DataFrame({'price': [1_000_000_000], 'area': [80]})
        stats = compute_statistics(df, transaction_type='فروش')
        self.assertNotIn('price', stats)

    def test_all_null_prices(self):
        df = pd.DataFrame({'price': [None, None], 'area': [80, 90]})
        stats = compute_statistics(df, transaction_type='فروش')
        self.assertNotIn('price', stats)

    def test_two_prices_produce_mean(self):
        df = pd.DataFrame({'price': [1_000_000_000, 2_000_000_000], 'area': [80, 90]})
        stats = compute_statistics(df, transaction_type='فروش')
        self.assertIn('price', stats)
        self.assertEqual(stats['price']['mean'], 1_500_000_000)
        self.assertIsNotNone(stats['price']['median'])

    def test_invalid_transaction_type_does_not_crash(self):
        df = pd.DataFrame({'price': [1_000_000_000, 2_000_000_000]})
        stats = compute_statistics(df, transaction_type='نامشخص')
        self.assertIsInstance(stats, dict)
