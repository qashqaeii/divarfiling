"""Listing benchmark payload for Mobile API."""
from __future__ import annotations

from typing import Any, Dict, Optional

from workspace.models import Listing

from mobile_api.serializers import _listing_market_to_dict
from workspace.services.access import has_active_bot_license
from workspace.services.analyzer import benchmark_listing, listings_to_dataframe


def listing_benchmark_payload(user, token: str) -> Optional[Dict[str, Any]]:
    if not has_active_bot_license(user):
        return None
    lst = (
        Listing.objects.filter(
            dataset__user=user,
            dataset__is_active=True,
            token=token,
        )
        .select_related('dataset')
        .first()
    )
    if not lst:
        return None

    dataset = lst.dataset
    if dataset is None:
        return {
            'status': 'insufficient_data',
            'message': 'داده کافی برای مقایسه دقیق وجود ندارد',
            'listing_token': token,
        }

    listings_qs = dataset.listings.all()
    if listings_qs.count() < 2:
        return {
            'status': 'insufficient_data',
            'message': 'داده کافی برای مقایسه دقیق وجود ندارد',
            'sample_count': listings_qs.count(),
            'listing_token': token,
        }

    df = listings_to_dataframe(listings_qs)
    if df is None or len(df) < 2:
        return {
            'status': 'insufficient_data',
            'message': 'داده کافی برای مقایسه دقیق وجود ندارد',
            'listing_token': token,
        }

    bench = benchmark_listing(lst, df, dataset.transaction_type or '')
    summary = _listing_market_to_dict(lst)
    if not summary:
        return {
            'status': 'insufficient_data',
            'message': 'داده کافی برای مقایسه دقیق وجود ندارد',
            'sample_count': int(bench.get('sample_count') or len(df)),
            'listing_token': token,
        }

    return {
        'status': 'ok',
        'listing_token': token,
        'summary': summary,
        'benchmark': {
            'metric': bench.get('metric') or '',
            'label': bench.get('label') or '',
            'listing_metric': bench.get('listing_metric'),
            'listing_metric_fmt': bench.get('price_per_sqm_fmt') or bench.get('listing_metric_fmt') or '',
            'market_median': bench.get('market_median'),
            'market_median_fmt': bench.get('market_median_fmt') or '',
            'diff_amount': bench.get('diff_amount'),
            'diff_amount_fmt': bench.get('diff_amount_fmt') or '',
            'value_score': bench.get('value_score'),
            'market_tier': bench.get('market_tier') or '',
            'verdict': bench.get('verdict') or '',
            'note': bench.get('note') or '',
            'sample_count': int(bench.get('sample_count') or len(df)),
        },
    }
