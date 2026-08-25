"""سرویس خلاصه هوشمند آگهی."""
from __future__ import annotations

from typing import Any, Dict

from workspace.models import Dataset, Listing
from workspace.services.analyzer import benchmark_listing, listings_to_dataframe

from ai_workspace.constants import FEATURE_LISTING_SUMMARY, resolve_model_label
from ai_workspace.context_builders import listing_context
from ai_workspace.services.gateway import GatewayResult, run


def generate_summary(user, dataset: Dataset, listing: Listing) -> GatewayResult:
    df = listings_to_dataframe(dataset.listings.all())
    benchmark = benchmark_listing(listing, df, dataset.transaction_type) if len(df) else {}
    context = listing_context.build(listing, dataset, benchmark)
    return run(
        FEATURE_LISTING_SUMMARY,
        user,
        context=context,
        entity_type='listing',
        entity_id=str(listing.id),
    )


def result_to_dict(result: GatewayResult) -> Dict[str, Any]:
    return {
        'ok': True,
        'feature': result.feature,
        'provider': result.provider,
        'model': result.model,
        'model_label': resolve_model_label(
            provider=result.provider,
            model=result.model,
            is_fallback=result.is_fallback,
        ),
        'is_fallback': result.is_fallback,
        'from_cache': result.from_cache,
        'status': result.status,
        'data': result.data,
        'latency_ms': result.latency_ms,
    }
