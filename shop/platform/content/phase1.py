"""محتوای صفحات پلتفرم — فاز ۱ + فاز ۲."""
from __future__ import annotations

from typing import Any

from shop.platform.content.agency_hub import agency_product_line_content
from shop.platform.content.agency_management import agency_management_content
from shop.platform.content.build_property_database import build_property_database_content
from shop.platform.content.crm_hub import crm_product_line_content
from shop.platform.content.customer_follow_up import customer_follow_up_content
from shop.platform.content.extraction_hub import extraction_product_line_content
from shop.platform.content.fast_property_search import fast_property_search_content
from shop.platform.content.features_hub import features_hub_content
from shop.platform.content.filing_hub import filing_product_line_content
from shop.platform.content.market_intelligence_hub import (
    market_intelligence_product_line_content,
)
from shop.platform.content.property_pricing import property_pricing_content
from shop.platform.content.reminders_feature import crm_reminders_content
from shop.platform.content.solutions_hub import solutions_hub_content


def build_page_content(content_key: str) -> dict[str, Any]:
    builders = {
        'features_hub': features_hub_content,
        'crm_product_line': crm_product_line_content,
        'crm_reminders': crm_reminders_content,
        'solutions_hub': solutions_hub_content,
        'customer_follow_up': customer_follow_up_content,
        'filing_product_line': filing_product_line_content,
        'fast_property_search': fast_property_search_content,
        'build_property_database': build_property_database_content,
        'market_intelligence_product_line': market_intelligence_product_line_content,
        'property_pricing': property_pricing_content,
        'agency_product_line': agency_product_line_content,
        'agency_management': agency_management_content,
        'extraction_product_line': extraction_product_line_content,
    }
    builder = builders.get(content_key)
    if not builder:
        raise KeyError(f'unknown content_key: {content_key}')
    return builder()
