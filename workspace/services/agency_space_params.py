"""پارامترهای لیست فضای آژانس — parse امن از query string."""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import date, datetime
from typing import Any, Dict, Optional
from urllib.parse import urlencode

SPACE_TABS = frozenset({
    'overview', 'all', 'properties', 'contacts', 'crm', 'saved_by_me',
    'published_by_me',
})
SPACE_TAB_ALIASES = {
    'mine': 'published_by_me',
    'all': 'overview',
    'saved_by_me': 'crm',
}

SPACE_SCOPES = frozenset({'all', 'published_by_me', 'copied_by_me'})
CRM_COPY_CHOICES = frozenset({'copied', 'not_copied'})
CONTACT_SHARE_FILTER_CHOICES = frozenset({'summary', 'full'})

ORDERING_CHOICES = frozenset({
    'newest', 'oldest', 'price_asc', 'price_desc', 'area_asc', 'area_desc',
    'budget_asc', 'budget_desc', 'most_copied',
})

PUBLICATION_STATUS_CHOICES = frozenset({'active', 'archived', 'all'})

DEFAULT_PAGE_SIZE = 24


@dataclass
class SpaceListFilters:
    tab: str = 'overview'
    scope: str = 'all'
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
    rooms: str = ''
    published_after: Optional[date] = None
    published_before: Optional[date] = None
    customer_type: str = ''
    region: str = ''
    min_budget: Optional[int] = None
    max_budget: Optional[int] = None
    contact_share_level: str = ''
    crm_copy: str = ''
    publication_status: str = 'active'

    def normalized_tab(self) -> str:
        t = SPACE_TAB_ALIASES.get(self.tab, self.tab)
        if t not in SPACE_TABS:
            return 'overview'
        if t == 'published_by_me':
            return 'properties'
        return t

    def normalized_scope(self) -> str:
        s = (self.scope or 'all').strip()
        if s == 'published_by_me' or self.tab == 'published_by_me':
            return 'published_by_me'
        return s if s in SPACE_SCOPES else 'all'

    def is_overview(self) -> bool:
        return self.normalized_tab() == 'overview'

    def as_query_dict(self, *, exclude: frozenset[str] = frozenset()) -> Dict[str, str]:
        out: Dict[str, str] = {}
        tab_out = self.normalized_tab()
        mapping = {
            'tab': tab_out if tab_out != 'overview' else '',
            'scope': self.normalized_scope() if self.normalized_scope() != 'all' else '',
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
            'rooms': self.rooms,
            'published_after': self.published_after.isoformat() if self.published_after else '',
            'published_before': self.published_before.isoformat() if self.published_before else '',
            'customer_type': self.customer_type,
            'region': self.region,
            'min_budget': str(self.min_budget) if self.min_budget is not None else '',
            'max_budget': str(self.max_budget) if self.max_budget is not None else '',
            'contact_share_level': self.contact_share_level,
            'crm_copy': self.crm_copy,
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

    def without_params(self, *params: str) -> str:
        return self.query_string(exclude=frozenset(params))

    def published_after_jalali(self) -> str:
        return _format_filter_date_jalali(self.published_after)

    def published_before_jalali(self) -> str:
        return _format_filter_date_jalali(self.published_before)


def _format_filter_date_jalali(value: Optional[date]) -> str:
    if not value:
        return ''
    from workspace.services.jalali_input import format_jalali_date, to_persian_digits
    return to_persian_digits(format_jalali_date(value))


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
        pass
    from workspace.services.jalali_input import parse_jalali_date_string
    return parse_jalali_date_string(raw)


def parse_space_list_filters(get_params: Any) -> SpaceListFilters:
    tab = (get_params.get('tab') or 'overview').strip()
    tab = SPACE_TAB_ALIASES.get(tab, tab)
    if tab not in SPACE_TABS:
        tab = 'overview'

    scope = (get_params.get('scope') or '').strip()
    if tab == 'published_by_me':
        tab = 'properties'
        scope = 'published_by_me'
    elif scope not in SPACE_SCOPES:
        scope = 'all'

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

    crm_copy = (get_params.get('crm_copy') or '').strip()
    if crm_copy not in CRM_COPY_CHOICES:
        crm_copy = ''

    contact_share = (get_params.get('contact_share_level') or '').strip()
    if contact_share not in CONTACT_SHARE_FILTER_CHOICES:
        contact_share = ''

    return SpaceListFilters(
        tab=tab,
        scope=scope,
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
        rooms=(get_params.get('rooms') or '').strip(),
        published_after=_date_param(get_params.get('published_after', '')),
        published_before=_date_param(get_params.get('published_before', '')),
        customer_type=(get_params.get('customer_type') or '').strip(),
        region=(get_params.get('region') or '').strip(),
        min_budget=_int_param(get_params.get('min_budget', '')),
        max_budget=_int_param(get_params.get('max_budget', '')),
        contact_share_level=contact_share,
        crm_copy=crm_copy,
        publication_status=pub_status,
    )


def filters_to_legacy_kwargs(filters: SpaceListFilters) -> Dict[str, Any]:
    """سازگاری با get_space_items_qs(**kwargs)."""
    tab = filters.normalized_tab()
    legacy_tab = ''
    if tab in ('properties', 'contacts'):
        legacy_tab = tab
    elif tab in ('crm', 'saved_by_me'):
        legacy_tab = 'saved_by_me'
    return {
        'tab': legacy_tab,
        'scope': filters.normalized_scope(),
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
        'rooms': filters.rooms,
        'published_after': filters.published_after,
        'published_before': filters.published_before,
        'customer_type': filters.customer_type,
        'region': filters.region,
        'min_budget': filters.min_budget,
        'max_budget': filters.max_budget,
        'contact_share_level': filters.contact_share_level,
        'crm_copy': filters.crm_copy,
        'publication_status': filters.publication_status,
    }


def build_space_filter_chips(filters: SpaceListFilters) -> list:
    """Chipهای فیلتر فعال برای UI — بدون منطق permission."""

    def _chip(param: str, label: str) -> dict:
        return {'label': label, 'clear_query': filters.without_params(param)}

    def _range_chip(*params: str, label: str) -> dict:
        return {'label': label, 'clear_query': filters.without_params(*params)}

    chips = []
    if filters.q:
        chips.append(_chip('q', f'جستجو: {filters.q[:40]}'))
    if filters.deal_mode:
        chips.append(_chip('deal_mode', filters.deal_mode))
    if filters.property_type:
        chips.append(_chip('property_type', filters.property_type))
    if filters.city:
        chips.append(_chip('city', f'شهر: {filters.city}'))
    if filters.district:
        chips.append(_chip('district', f'منطقه: {filters.district}'))
    if filters.min_price is not None or filters.max_price is not None:
        lo = filters.min_price or '…'
        hi = filters.max_price or '…'
        chips.append(_range_chip('min_price', 'max_price', label=f'قیمت {lo}–{hi}'))
    if filters.min_area is not None or filters.max_area is not None:
        lo = filters.min_area or '…'
        hi = filters.max_area or '…'
        chips.append(_range_chip('min_area', 'max_area', label=f'متراژ {lo}–{hi}'))
    if filters.rooms:
        chips.append(_chip('rooms', f'{filters.rooms} خواب'))
    if filters.customer_type:
        chips.append(_chip('customer_type', filters.customer_type))
    if filters.region:
        chips.append(_chip('region', f'محدوده: {filters.region}'))
    if filters.min_budget is not None or filters.max_budget is not None:
        lo = filters.min_budget or '…'
        hi = filters.max_budget or '…'
        chips.append(_range_chip('min_budget', 'max_budget', label=f'بودجه {lo}–{hi}'))
    if filters.visibility:
        lbl = 'عمومی آژانس' if filters.visibility == 'agency_public' else 'اعضای منتخب'
        chips.append(_chip('visibility', lbl))
    if filters.contact_share_level:
        lbl = 'اطلاعات کامل' if filters.contact_share_level == 'full' else 'خلاصه'
        chips.append(_chip('contact_share_level', lbl))
    if filters.crm_copy == 'copied':
        chips.append(_chip('crm_copy', 'در CRM من'))
    elif filters.crm_copy == 'not_copied':
        chips.append(_chip('crm_copy', 'کپی نشده'))
    if filters.publisher_id:
        chips.append(_chip('publisher', f'ناشر #{filters.publisher_id}'))
    if filters.published_after is not None or filters.published_before is not None:
        lo = filters.published_after_jalali() or '…'
        hi = filters.published_before_jalali() or '…'
        chips.append(_range_chip('published_after', 'published_before', label=f'تاریخ {lo} – {hi}'))
    return chips
