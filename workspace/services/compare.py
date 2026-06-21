"""مقایسه دو مجموعه‌داده."""
from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from workspace.services.analyzer import compute_statistics, listings_to_dataframe, neighborhood_stats


def compare_datasets(dataset_a, dataset_b) -> Dict[str, Any]:
    listings_a = list(dataset_a.listings.all())
    listings_b = list(dataset_b.listings.all())
    df_a = listings_to_dataframe(listings_a)
    df_b = listings_to_dataframe(listings_b)

    stats_a = compute_statistics(df_a, dataset_a.transaction_type)
    stats_b = compute_statistics(df_b, dataset_b.transaction_type)

    tokens_a = set(df_a['token'].tolist()) if 'token' in df_a.columns else set()
    tokens_b = set(df_b['token'].tolist()) if 'token' in df_b.columns else set()

    def delta(old, new):
        if not old:
            return None
        return round((new - old) / old * 100, 1)

    median_a = stats_a.get('price', {}).get('median', 0)
    median_b = stats_b.get('price', {}).get('median', 0)
    pps_a = stats_a.get('price_per_sqm', {}).get('median', 0)
    pps_b = stats_b.get('price_per_sqm', {}).get('median', 0)

    return {
        'dataset_a': {'name': dataset_a.name, 'count': len(listings_a), 'stats': stats_a},
        'dataset_b': {'name': dataset_b.name, 'count': len(listings_b), 'stats': stats_b},
        'delta': {
            'count_pct': delta(len(listings_a), len(listings_b)),
            'median_price_pct': delta(median_a, median_b),
            'median_pps_pct': delta(pps_a, pps_b),
        },
        'tokens': {
            'new': list(tokens_b - tokens_a)[:50],
            'removed': list(tokens_a - tokens_b)[:50],
            'common': len(tokens_a & tokens_b),
            'new_count': len(tokens_b - tokens_a),
            'removed_count': len(tokens_a - tokens_b),
        },
        'neighborhoods_a': neighborhood_stats(df_a, 5),
        'neighborhoods_b': neighborhood_stats(df_b, 5),
    }
