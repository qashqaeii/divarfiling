"""Context Builder — آگهی دیوار."""
from __future__ import annotations

from typing import Any, Dict

from workspace.services.advertiser_signal import listing_advertiser_display
from workspace.services.formatting import format_area, format_toman
from workspace.services.features import extract_listing_features
from workspace.services.display import transaction_profile

from ai_workspace.context_builders.base import truncate


def build(listing, dataset, benchmark: Dict[str, Any] | None = None) -> Dict[str, Any]:
    benchmark = benchmark or {}
    feat = extract_listing_features(listing)
    tx = transaction_profile(dataset.transaction_type)
    adv = listing_advertiser_display(listing)

    desc = (getattr(listing, 'description', '') or '').strip()
    if not desc and getattr(listing, 'data', None):
        desc = str((listing.data or {}).get('توضیحات') or (listing.data or {}).get('description') or '')

    price_label = ''
    if tx.get('show_price') and listing.price:
        price_label = format_toman(listing.price)
    elif listing.deposit or listing.rent:
        parts = []
        if listing.deposit:
            parts.append(f'رهن {format_toman(listing.deposit)}')
        if listing.rent:
            parts.append(f'اجاره {format_toman(listing.rent)}')
        price_label = ' · '.join(parts)

    return {
        'title': listing.title or '',
        'token': listing.token or '',
        'deal_mode': tx.get('badge') or dataset.transaction_type or '',
        'price_label': price_label,
        'price_per_sqm_label': format_toman(listing.price_per_sqm, per_sqm=True) if listing.price_per_sqm else '',
        'area_label': format_area(listing.area) if listing.area else '',
        'rooms': feat.get('rooms') or listing.rooms or '',
        'neighborhood': listing.neighborhood or '',
        'city': listing.city or dataset.city or '',
        'benchmark_verdict': benchmark.get('verdict') or '',
        'benchmark_note': benchmark.get('note') or '',
        'benchmark_diff': benchmark.get('diff_pct_fmt') or '',
        'market_median': benchmark.get('market_median_fmt') or '',
        'advertiser_label': adv.get('label') or '',
        'advertiser_title': adv.get('title') or '',
        'description_excerpt': truncate(desc, 300),
        'content_version': f'{listing.id}:{listing.created_at.isoformat() if listing.created_at else ""}',
        '_listing': listing,
        '_dataset': dataset,
    }
