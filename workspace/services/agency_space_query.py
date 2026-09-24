"""Query layer Agency Space — list/detail، فیلتر، جستجو، مرتب‌سازی."""

from __future__ import annotations



from datetime import date, datetime, time

from typing import Any, Dict, List, Optional, Tuple



from django.core.paginator import Paginator

from django.db.models import (

    Case,

    Count,

    Exists,

    F,

    IntegerField,

    OuterRef,

    Q,

    QuerySet,

    Subquery,

    Prefetch,

    When,

)

from django.utils import timezone



from workspace.models import AgencySpaceCopy, AgencySpaceItem, CRMAgency, CRMAgencyMember

from workspace.services.agency_space_access import (

    can_access_agency_space,

    can_moderate_agency_space,

    can_view_space_item,

    get_user_space_agency,

)

from workspace.services.agency_space_params import DEFAULT_PAGE_SIZE, SpaceListFilters

from workspace.services.crm_scope import get_membership





def _visible_discovery_status_q() -> Q:

    return Q(status=AgencySpaceItem.STATUS_ACTIVE)





def annotate_space_list_for_user(qs: QuerySet, user) -> QuerySet:

    """already_copied، copy_count — بدون N+1 در لیست."""

    my_copy = AgencySpaceCopy.objects.filter(

        item_id=OuterRef('pk'),

        copied_by_id=user.id,

    )

    my_live_copy = my_copy.filter(

        Q(copied_property_id__isnull=False) | Q(copied_customer_id__isnull=False),

    )

    return qs.annotate(

        space_copy_count=Count('space_copies', distinct=True),

        viewer_has_space_copy=Exists(my_copy),

        viewer_has_live_copy=Exists(my_live_copy),

        viewer_copy_property_id=Subquery(my_copy.values('copied_property_id')[:1]),

        viewer_copy_customer_id=Subquery(my_copy.values('copied_customer_id')[:1]),

        viewer_copy_created_at=Subquery(my_copy.values('created_at')[:1]),

    )





def _visibility_q_for_user(user) -> Q:

    membership = get_membership(user)

    if not membership:

        return Q(pk__in=[])

    audience_item_ids = AgencySpaceItem.objects.filter(

        agency_id=membership.agency_id,

        visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,

        audience_members__member_id=membership.pk,

    ).values_list('pk', flat=True)

    return (

        Q(visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)

        | Q(publisher_id=user.id)

        | Q(pk__in=audience_item_ids)

    )





def _apply_search(qs: QuerySet, query: str) -> QuerySet:

    if not query:

        return qs

    return qs.filter(

        Q(property__title__icontains=query)

        | Q(property__city__icontains=query)

        | Q(property__district__icontains=query)

        | Q(property__neighborhood__icontains=query)

        | Q(property__address__icontains=query)

        | Q(property__property_type__icontains=query)

        | Q(property__deal_mode__icontains=query)

        | Q(customer__name__icontains=query)

        | Q(customer__company_name__icontains=query)

        | Q(customer__notes__icontains=query)

        | Q(customer__areas__icontains=query)

        | Q(customer__customer_type__icontains=query)

        | Q(customer__city__icontains=query)

        | Q(customer__district__icontains=query)

        | Q(note__icontains=query)

    )





def _apply_property_filters(qs: QuerySet, **kwargs) -> QuerySet:

    deal_mode = kwargs.get('deal_mode') or ''

    property_type = kwargs.get('property_type') or ''

    city = kwargs.get('city') or ''

    district = kwargs.get('district') or ''

    min_price = kwargs.get('min_price')

    max_price = kwargs.get('max_price')

    min_area = kwargs.get('min_area')

    max_area = kwargs.get('max_area')

    published_after = kwargs.get('published_after')

    published_before = kwargs.get('published_before')



    if deal_mode:

        qs = qs.filter(property__deal_mode=deal_mode)

    if property_type:

        qs = qs.filter(property__property_type=property_type)

    if city:

        qs = qs.filter(property__city__icontains=city)

    if district:

        qs = qs.filter(

            Q(property__district__icontains=district)

            | Q(property__neighborhood__icontains=district),

        )

    if min_price is not None:

        qs = qs.filter(

            Q(property__sale_price__gte=min_price)

            | Q(property__monthly_rent__gte=min_price),

        )

    if max_price is not None:

        qs = qs.filter(

            Q(property__sale_price__lte=max_price)

            | Q(property__monthly_rent__lte=max_price),

        )

    if min_area is not None:

        qs = qs.filter(property__area__gte=min_area)

    if max_area is not None:

        qs = qs.filter(property__area__lte=max_area)

    if published_after:

        qs = qs.filter(published_at__gte=_date_start(published_after))

    if published_before:

        qs = qs.filter(published_at__lte=_date_end(published_before))

    return qs





def _apply_customer_filters(qs: QuerySet, **kwargs) -> QuerySet:

    customer_type = kwargs.get('customer_type') or ''

    region = kwargs.get('region') or ''

    min_budget = kwargs.get('min_budget')

    max_budget = kwargs.get('max_budget')

    published_after = kwargs.get('published_after')

    published_before = kwargs.get('published_before')



    if customer_type:

        qs = qs.filter(customer__customer_type=customer_type)

    if region:

        qs = qs.filter(

            Q(customer__areas__icontains=region)

            | Q(customer__city__icontains=region)

            | Q(customer__district__icontains=region),

        )

    if min_budget is not None:

        qs = qs.filter(

            Q(customer__budget_max__gte=min_budget)

            | Q(customer__budget_min__gte=min_budget),

        )

    if max_budget is not None:

        qs = qs.filter(

            Q(customer__budget_min__lte=max_budget)

            | Q(customer__budget_max__lte=max_budget),

        )

    if published_after:

        qs = qs.filter(published_at__gte=_date_start(published_after))

    if published_before:

        qs = qs.filter(published_at__lte=_date_end(published_before))

    return qs





def _date_start(d: date) -> datetime:

    tz = timezone.get_current_timezone()

    return timezone.make_aware(datetime.combine(d, time.min), tz)





def _date_end(d: date) -> datetime:

    tz = timezone.get_current_timezone()

    return timezone.make_aware(datetime.combine(d, time.max), tz)





def _apply_common_filters(qs: QuerySet, user, **kwargs) -> QuerySet:

    publisher_id = kwargs.get('publisher_id')

    visibility = kwargs.get('visibility') or ''

    q = (kwargs.get('q') or '').strip()



    if publisher_id:

        qs = qs.filter(publisher_id=publisher_id)

    if visibility in (

        AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,

        AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,

    ):

        qs = qs.filter(visibility=visibility)

    qs = _apply_search(qs, q)

    return qs





def _apply_ordering(qs: QuerySet, ordering: str) -> QuerySet:

    if ordering == 'oldest':

        return qs.order_by('published_at')

    if ordering == 'price_asc':

        return qs.annotate(

            _sort_price=Case(

                When(property__sale_price__isnull=False, then=F('property__sale_price')),

                default=F('property__monthly_rent'),

                output_field=IntegerField(),

            ),

        ).order_by(F('_sort_price').asc(nulls_last=True))

    if ordering == 'price_desc':

        return qs.annotate(

            _sort_price=Case(

                When(property__sale_price__isnull=False, then=F('property__sale_price')),

                default=F('property__monthly_rent'),

                output_field=IntegerField(),

            ),

        ).order_by(F('_sort_price').desc(nulls_last=True))

    if ordering == 'area_asc':

        return qs.order_by(F('property__area').asc(nulls_last=True))

    if ordering == 'area_desc':

        return qs.order_by(F('property__area').desc(nulls_last=True))

    return qs.order_by('-published_at')





def _base_agency_qs(user, agency: CRMAgency) -> QuerySet:

    pub_membership = Prefetch(

        'publisher__crm_agency_memberships',

        queryset=CRMAgencyMember.objects.filter(agency=agency, is_active=True),

        to_attr='_space_pub_membership',

    )

    return (

        AgencySpaceItem.objects.filter(agency=agency)

        .select_related('publisher', 'property', 'customer')

        .prefetch_related('audience_members', pub_membership)

    )





def _saved_by_me_qs(user, agency: CRMAgency) -> QuerySet:

    live_item_ids = AgencySpaceCopy.objects.filter(

        copied_by=user,

        item__agency=agency,

    ).filter(

        Q(copied_property_id__isnull=False) | Q(copied_customer_id__isnull=False),

    ).values_list('item_id', flat=True)

    return _base_agency_qs(user, agency).filter(pk__in=live_item_ids)





def _published_by_me_qs(user, agency: CRMAgency, publication_status: str) -> QuerySet:

    qs = _base_agency_qs(user, agency).filter(publisher_id=user.id)

    if publication_status == 'active':

        qs = qs.filter(

            status__in=(

                AgencySpaceItem.STATUS_ACTIVE,

                AgencySpaceItem.STATUS_MODERATION_HIDDEN,

            ),

        )

    elif publication_status == 'archived':

        qs = qs.filter(status=AgencySpaceItem.STATUS_ARCHIVED)

    else:

        qs = qs.exclude(status=AgencySpaceItem.STATUS_ARCHIVED)

    return qs





def get_space_items_qs(

    user,

    *,

    agency: Optional[CRMAgency] = None,

    kind: str = '',

    tab: str = '',

    q: str = '',

    publisher_id: Optional[int] = None,

    visibility: str = '',

    ordering: str = 'newest',

    deal_mode: str = '',

    property_type: str = '',

    city: str = '',

    district: str = '',

    min_price: Optional[int] = None,

    max_price: Optional[int] = None,

    min_area: Optional[float] = None,

    max_area: Optional[float] = None,

    published_after: Optional[date] = None,

    published_before: Optional[date] = None,

    customer_type: str = '',

    region: str = '',

    min_budget: Optional[int] = None,

    max_budget: Optional[int] = None,

    publication_status: str = 'active',

) -> QuerySet:

    if tab == 'mine':
        tab = 'published_by_me'

    agency = agency or get_user_space_agency(user)

    if not agency or not can_access_agency_space(user, agency):

        return AgencySpaceItem.objects.none()



    filter_kwargs = {

        'q': q,

        'publisher_id': publisher_id,

        'visibility': visibility,

        'deal_mode': deal_mode,

        'property_type': property_type,

        'city': city,

        'district': district,

        'min_price': min_price,

        'max_price': max_price,

        'min_area': min_area,

        'max_area': max_area,

        'published_after': published_after,

        'published_before': published_before,

        'customer_type': customer_type,

        'region': region,

        'min_budget': min_budget,

        'max_budget': max_budget,

    }



    if tab == 'saved_by_me':

        qs = _saved_by_me_qs(user, agency)

    elif tab == 'published_by_me':

        qs = _published_by_me_qs(user, agency, publication_status)

    else:

        qs = (

            _base_agency_qs(user, agency)

            .filter(_visible_discovery_status_q())

            .filter(_visibility_q_for_user(user))

        )



    if kind == 'property':

        qs = qs.filter(property__isnull=False)

    elif kind == 'customer':

        qs = qs.filter(customer__isnull=False)



    if tab == 'properties':

        qs = qs.filter(property__isnull=False)

    elif tab == 'contacts':

        qs = qs.filter(customer__isnull=False)



    qs = _apply_common_filters(qs, user, **filter_kwargs)



    if tab == 'properties' or kind == 'property':

        qs = _apply_property_filters(qs, **filter_kwargs)

    if tab == 'contacts' or kind == 'customer':

        qs = _apply_customer_filters(qs, **filter_kwargs)



    qs = _apply_ordering(qs, ordering if ordering in (

        'newest', 'oldest', 'price_asc', 'price_desc', 'area_asc', 'area_desc',

    ) else 'newest')

    return annotate_space_list_for_user(qs, user)





def get_space_items_from_filters(user, filters: SpaceListFilters) -> QuerySet:

    tab = filters.normalized_tab()

    legacy_tab = ''

    if tab == 'published_by_me':

        legacy_tab = 'published_by_me'

    elif tab == 'saved_by_me':

        legacy_tab = 'saved_by_me'

    elif tab in ('properties', 'contacts'):

        legacy_tab = tab

    return get_space_items_qs(

        user,

        tab=legacy_tab,

        kind=filters.kind,

        q=filters.q,

        publisher_id=filters.publisher_id,

        visibility=filters.visibility,

        ordering=filters.ordering,

        deal_mode=filters.deal_mode,

        property_type=filters.property_type,

        city=filters.city,

        district=filters.district,

        min_price=filters.min_price,

        max_price=filters.max_price,

        min_area=filters.min_area,

        max_area=filters.max_area,

        published_after=filters.published_after,

        published_before=filters.published_before,

        customer_type=filters.customer_type,

        region=filters.region,

        min_budget=filters.min_budget,

        max_budget=filters.max_budget,

        publication_status=filters.publication_status,

    )





def get_space_management_qs(

    user,

    *,

    agency: Optional[CRMAgency] = None,

    status_filter: str = '',

) -> QuerySet:

    agency = agency or get_user_space_agency(user)

    if not agency or not can_moderate_agency_space(user, agency):

        return AgencySpaceItem.objects.none()



    qs = _base_agency_qs(user, agency).order_by('-published_at')

    if status_filter == 'active':

        qs = qs.filter(status=AgencySpaceItem.STATUS_ACTIVE)

    elif status_filter == 'hidden':

        qs = qs.filter(status=AgencySpaceItem.STATUS_MODERATION_HIDDEN)

    elif status_filter == 'archived':

        qs = qs.filter(status=AgencySpaceItem.STATUS_ARCHIVED)

    else:

        qs = qs.exclude(status=AgencySpaceItem.STATUS_ARCHIVED)

    return annotate_space_list_for_user(qs, user)





def paginate_space_items(

    qs: QuerySet,

    page: int,

    page_size: int = DEFAULT_PAGE_SIZE,

) -> Tuple[List[AgencySpaceItem], int, int]:

    paginator = Paginator(qs, page_size)

    page_obj = paginator.get_page(page)

    return list(page_obj.object_list), paginator.count, paginator.num_pages





def get_space_items_for_user(

    user,

    *,

    page: int = 1,

    page_size: int = DEFAULT_PAGE_SIZE,

    **filters,

) -> Tuple[List[AgencySpaceItem], int, int]:

    qs = get_space_items_qs(user, **filters)

    return paginate_space_items(qs, page, page_size)





def get_space_item_for_user(user, item_id: int) -> Optional[AgencySpaceItem]:

    agency = get_user_space_agency(user)

    if not agency:

        return None

    try:

        item = (

            AgencySpaceItem.objects.filter(agency=agency, pk=item_id)

            .select_related('publisher', 'property', 'customer')

            .prefetch_related('audience_members__member__user')

            .get()

        )

    except AgencySpaceItem.DoesNotExist:

        return None

    if not can_view_space_item(user, item):

        return None

    qs = annotate_space_list_for_user(

        AgencySpaceItem.objects.filter(pk=item.pk),

        user,

    )

    annotated = qs.first()

    return annotated or item





def get_active_space_item_for_source(

    user,

    *,

    property_id: Optional[int] = None,

    customer_id: Optional[int] = None,

) -> Optional[AgencySpaceItem]:

    agency = get_user_space_agency(user)

    if not agency:

        return None

    qs = AgencySpaceItem.objects.filter(

        agency=agency,

        publisher_id=user.id,

        status=AgencySpaceItem.STATUS_ACTIVE,

    )

    if property_id:

        qs = qs.filter(property_id=property_id)

    elif customer_id:

        qs = qs.filter(customer_id=customer_id)

    else:

        return None

    return qs.select_related('property', 'customer').first()





def serialize_management_row(item: AgencySpaceItem, user) -> Dict[str, Any]:

    from workspace.services.agency_space_serialize import (

        serialize_space_item,

        serialize_space_item_safe_metadata,

    )



    if can_view_space_item(user, item):

        payload = serialize_space_item(item, user, detail=False)

        if payload:

            payload['view_mode'] = 'full'

            return payload

    safe = serialize_space_item_safe_metadata(item, user)

    if safe:

        safe['view_mode'] = 'safe'

    return safe or {}


