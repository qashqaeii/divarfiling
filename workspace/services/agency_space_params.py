"""پارامترهای لیست فضای آژانس — parse امن از query string."""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime
from typing import Any, Dict, Optional
from urllib.parse import urlencode

SPACE_TABS = frozenset({
    'all', 'properties', 'contacts', 'published_by_me', 'saved_by_me',
})
SPACE_TAB_ALIASES = {'mine': 'published_by_me'}

ORDERING_CHOICES = frozenset({
    'newest', 'oldest', 'price_asc', 'price_desc', 'area_asc', 'area_desc',
})

PUBLICATION_STATUS_CHOICES = frozenset({'active', 'archived', 'all'})

DEFAULT_PAGE_SIZE = 24


@dataclass
class SpaceListFilters:
    tab: str = 'all'
    kind: str = ''
    q: str = ''
    publisher_id: Optional[int] = None
    visibility: str = ''
    ordering: str = 'newest'
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    deal_mode: str = ''
    property_type: str = ''
    city: str = ''
    district: str = ''
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    published_after: Optional[date] = None
    published_before: Optional[date] = None
    customer_type: str = ''
    region: str = ''
    min_budget: Optional[int] = None
    max_budget: Optional[int] = None
    publication_status: str = 'active'

    def normalized_tab(self) -> str:
        t = SPACE_TAB_ALIASES.get(self.tab, self.tab)
        return t if t in SPACE_TABS else 'all'

    def as_query_dict(self, *, exclude: frozenset[str] = frozenset()) -> Dict[str, str]:
        out: Dict[str, str] = {}
        mapping = {
            'tab': self.tab if self.tab != 'all' else '',
            'kind': self.kind,
            'q': self.q,
            'publisher': str(self.publisher_id) if self.publisher_id else '',
            'visibility': self.visibility,
            'ordering': self.ordering if self.ordering != 'newest' else '',
            'deal_mode': self.deal_mode,
            'property_type': self.property_type,
            'city': self.city,
            'district': self.district,
            'min_price': str(self.min_price) if self.min_price is not None else '',
            'max_price': str(self.max_price) if self.max_price is not None else '',
            'min_area': str(self.min_area) if self.min_area is not None else '',
            'max_area': str(self.max_area) if self.max_area is not None else '',
            'published_after': self.published_after.isoformat() if self.published_after else '',
            'published_before': self.published_before.isoformat() if self.published_before else '',
            'customer_type': self.customer_type,
            'region': self.region,
            'min_budget': str(self.min_budget) if self.min_budget is not None else '',
            'max_budget': str(self.max_budget) if self.max_budget is not None else '',
            'publication_status': (
                self.publication_status if self.publication_status != 'active' else ''
            ),
        }
        for key, val in mapping.items():
            if key in exclude or not val:
                continue
            out[key] = val
        return out

    def query_string(self, *, page: Optional[int] = None, exclude: frozenset[str] = frozenset()) -> str:
        data = self.as_query_dict(exclude=exclude)
        if page is not None and page > 1:
            data['page'] = str(page)
        return urlencode(data)


def _int_param(raw: str) -> Optional[int]:
    raw = (raw or '').strip()
    if not raw or not raw.isdigit():
        return None
    return int(raw)


def _float_param(raw: str) -> Optional[float]:
    raw = (raw or '').strip().replace(',', '')
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _date_param(raw: str) -> Optional[date]:
    raw = (raw or '').strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def parse_space_list_filters(get_params: Any) -> SpaceListFilters:
    tab = (get_params.get('tab') or 'all').strip()
    tab = SPACE_TAB_ALIASES.get(tab, tab)
    if tab not in SPACE_TABS:
        tab = 'all'

    ordering = (get_params.get('ordering') or 'newest').strip()
    if ordering not in ORDERING_CHOICES:
        ordering = 'newest'

    visibility = (get_params.get('visibility') or '').strip()
    if visibility not in ('agency_public', 'selected_members'):
        visibility = ''

    pub_status = (get_params.get('publication_status') or 'active').strip()
    if pub_status not in PUBLICATION_STATUS_CHOICES:
        pub_status = 'active'

    publisher_raw = (get_params.get('publisher') or '').strip()
    publisher_id = int(publisher_raw) if publisher_raw.isdigit() else None

    page = _int_param(get_params.get('page', '1') or '1') or 1
    if page < 1:
        page = 1

    return SpaceListFilters(
        tab=tab,
        kind=(get_params.get('kind') or '').strip(),
        q=(get_params.get('q') or '').strip(),
        publisher_id=publisher_id,
        visibility=visibility,
        ordering=ordering,
        page=page,
        page_size=DEFAULT_PAGE_SIZE,
        deal_mode=(get_params.get('deal_mode') or '').strip(),
        property_type=(get_params.get('property_type') or '').strip(),
        city=(get_params.get('city') or '').strip(),
        district=(get_params.get('district') or '').strip(),
        min_price=_int_param(get_params.get('min_price', '')),
        max_price=_int_param(get_params.get('max_price', '')),
        min_area=_float_param(get_params.get('min_area', '')),
        max_area=_float_param(get_params.get('max_area', '')),
        published_after=_date_param(get_params.get('published_after', '')),
        published_before=_date_param(get_params.get('published_before', '')),
        customer_type=(get_params.get('customer_type') or '').strip(),
        region=(get_params.get('region') or '').strip(),
        min_budget=_int_param(get_params.get('min_budget', '')),
        max_budget=_int_param(get_params.get('max_budget', '')),
        publication_status=pub_status,
    )


def filters_to_legacy_kwargs(filters: SpaceListFilters) -> Dict[str, Any]:
    """سازگاری با get_space_items_qs(**kwargs)."""
    tab = filters.normalized_tab()
    legacy_tab = ''
    if tab == 'published_by_me':
        legacy_tab = 'published_by_me'
    elif tab in ('properties', 'contacts'):
        legacy_tab = tab
    elif tab == 'saved_by_me':
        legacy_tab = 'saved_by_me'
    return {
        'tab': legacy_tab,
        'kind': filters.kind,
        'q': filters.q,
        'publisher_id': filters.publisher_id,
        'visibility': filters.visibility,
        'ordering': filters.ordering,
        'deal_mode': filters.deal_mode,
        'property_type': filters.property_type,
        'city': filters.city,
        'district': filters.district,
        'min_price': filters.min_price,
        'max_price': filters.max_price,
        'min_area': filters.min_area,
        'max_area': filters.max_area,
        'published_after': filters.published_after,
        'published_before': filters.published_before,
        'customer_type': filters.customer_type,
        'region': filters.region,
        'min_budget': filters.min_budget,
        'max_budget': filters.max_budget,
        'publication_status': filters.publication_status,
    }
