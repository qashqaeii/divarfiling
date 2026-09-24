"""Agency Space — Phase 3 discovery, management, analytics."""
from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from workspace.models import AgencySpaceCopy, AgencySpaceItem, CRMProperty, Customer
from workspace.services.agency_space_analytics import (
    can_view_space_analytics,
    get_contributor_metrics,
    get_space_analytics_payload,
)
from workspace.services.agency_space_moderation import hide_space_item_public
from workspace.services.agency_space_publish import publish_customer, publish_property, unpublish_space_item
from workspace.services.agency_space_query import get_space_items_from_filters, get_space_management_qs
from workspace.services.agency_space_params import SpaceListFilters, parse_space_list_filters
from licenses.models import License
from workspace.services.agency_seats import assign_seat_to_member
from workspace.tests.test_agency_space_phase1 import AgencySpaceTestBase


class AgencySpacePhase3DiscoveryTests(AgencySpaceTestBase):
    def setUp(self):
        super().setUp()
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        if lic and not lic.assigned_user_id:
            assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)

    def _publish_prop(self, title='ملک جستجو', **prop_kw):
        defaults = {
            'user': self.advisor,
            'agency': self.agency,
            'title': title,
            'city': 'تهران',
            'district': 'منطقه ۳',
            'neighborhood': 'جردن',
            'property_type': 'آپارتمان',
            'deal_mode': 'فروش',
            'sale_price': 5_000_000_000,
            'area': 120,
        }
        defaults.update(prop_kw)
        prop = CRMProperty.objects.create(**defaults)
        return publish_property(
            self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
        )

    def test_property_search_by_title(self):
        self._publish_prop(title='ویلای لوکس شمال')
        f = SpaceListFilters(tab='properties', q='ویلای لوکس')
        ids = list(get_space_items_from_filters(self.advisor2, f).values_list('pk', flat=True))
        self.assertEqual(len(ids), 1)

    def test_customer_search_by_name(self):
        c = Customer.objects.create(
            user=self.advisor, agency=self.agency, name='شرکت آلفا',
            company_name='آلفا سازه', notes='خرید اداری', areas='سعادت‌آباد',
            customer_type='خریدار',
        )
        publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        f = SpaceListFilters(tab='contacts', q='آلفا سازه')
        self.assertEqual(get_space_items_from_filters(self.advisor2, f).count(), 1)

    def test_confidential_not_discoverable_via_search(self):
        prop = CRMProperty.objects.create(
            user=self.advisor, agency=self.agency, title='SECRET_UNIQUE_XYZ_99',
        )
        publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        f = SpaceListFilters(q='SECRET_UNIQUE_XYZ_99')
        self.assertEqual(get_space_items_from_filters(self.manager, f).count(), 0)

    def test_property_price_filter(self):
        self._publish_prop(sale_price=2_000_000_000)
        self._publish_prop(title='گران', sale_price=9_000_000_000)
        f = SpaceListFilters(tab='properties', min_price=8_000_000_000)
        self.assertEqual(get_space_items_from_filters(self.advisor2, f).count(), 1)

    def test_property_area_filter(self):
        self._publish_prop(area=50)
        self._publish_prop(title='بزرگ', area=200)
        f = SpaceListFilters(tab='properties', min_area=150)
        self.assertEqual(get_space_items_from_filters(self.advisor2, f).count(), 1)

    def test_publisher_filter(self):
        self._publish_prop()
        prop2 = CRMProperty.objects.create(user=self.advisor2, agency=self.agency, title='دیگر')
        publish_property(self.advisor2, prop2.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        f = SpaceListFilters(publisher_id=self.advisor2.id)
        self.assertEqual(get_space_items_from_filters(self.manager, f).count(), 1)

    def test_visibility_filter(self):
        prop = CRMProperty.objects.create(user=self.advisor, agency=self.agency, title='محرمانه')
        publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        f = SpaceListFilters(visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS)
        self.assertEqual(get_space_items_from_filters(self.advisor2, f).count(), 1)

    def test_ordering_whitelist_ignores_invalid(self):
        self._publish_prop(title='الف')
        f = SpaceListFilters(ordering='DROP TABLE;')
        qs = get_space_items_from_filters(self.advisor2, f)
        self.assertTrue(qs.query.order_by)

    def test_pagination(self):
        for i in range(26):
            p = CRMProperty.objects.create(
                user=self.advisor, agency=self.agency, title=f'فایل {i}',
            )
            publish_property(self.advisor, p.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        f = SpaceListFilters(tab='properties', page=2)
        from workspace.services.agency_space_query import paginate_space_items

        rows, total, pages = paginate_space_items(get_space_items_from_filters(self.advisor2, f), 2)
        self.assertEqual(total, 26)
        self.assertGreaterEqual(pages, 2)
        self.assertEqual(len(rows), 2)

    def test_published_by_me_active(self):
        item = self._publish_prop()
        f = SpaceListFilters(tab='published_by_me', publication_status='active')
        self.assertIn(item.pk, list(get_space_items_from_filters(self.advisor, f).values_list('pk', flat=True)))

    def test_published_by_me_archived(self):
        item = self._publish_prop()
        unpublish_space_item(self.advisor, item.pk)
        f = SpaceListFilters(tab='published_by_me', publication_status='archived')
        self.assertEqual(get_space_items_from_filters(self.advisor, f).count(), 1)

    def test_saved_by_me_live_copy_only(self):
        item = self._publish_prop()
        from workspace.services.agency_space_copy import copy_space_item_to_personal_crm

        copy_space_item_to_personal_crm(self.advisor2, item.pk)
        f = SpaceListFilters(tab='saved_by_me')
        self.assertEqual(get_space_items_from_filters(self.advisor2, f).count(), 1)

    def test_deleted_target_not_in_saved_by_me(self):
        item = self._publish_prop()
        from workspace.services.agency_space_copy import copy_space_item_to_personal_crm

        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        prop = CRMProperty.objects.get(pk=result.target_id)
        prop.deleted_at = timezone.now()
        prop.save(update_fields=['deleted_at'])
        rec = AgencySpaceCopy.objects.get(item=item, copied_by=self.advisor2)
        rec.copied_property_id = None
        rec.save(update_fields=['copied_property_id'])
        f = SpaceListFilters(tab='saved_by_me')
        self.assertEqual(get_space_items_from_filters(self.advisor2, f).count(), 0)

    def test_moderation_hidden_excluded_from_public_discovery(self):
        item = self._publish_prop()
        hide_space_item_public(self.manager, item.pk)
        f = SpaceListFilters(tab='all')
        self.assertEqual(get_space_items_from_filters(self.advisor2, f).count(), 0)

    def test_archived_excluded_from_discovery(self):
        item = self._publish_prop()
        unpublish_space_item(self.advisor, item.pk)
        f = SpaceListFilters(tab='properties')
        self.assertEqual(get_space_items_from_filters(self.advisor2, f).count(), 0)

    def test_filter_query_string_persistence(self):
        f = SpaceListFilters(tab='properties', q='test', min_price=100)
        qs = f.query_string()
        self.assertIn('tab=properties', qs)
        self.assertIn('min_price=100', qs)

    def test_query_count_bounded_for_list(self):
        for i in range(15):
            p = CRMProperty.objects.create(
                user=self.advisor, agency=self.agency, title=f'N+1 {i}', sale_price=i * 1_000_000,
            )
            publish_property(self.advisor, p.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        f = SpaceListFilters(tab='properties')
        qs = get_space_items_from_filters(self.advisor2, f)
        with CaptureQueriesContext(connection) as ctx:
            rows = list(qs[:20])
        self.assertLess(len(ctx), 12)
        self.assertEqual(len(rows), 15)
        first = rows[0]
        self.assertTrue(hasattr(first, 'space_copy_count'))
        self.assertTrue(hasattr(first, 'viewer_has_live_copy'))


class AgencySpacePhase3AnalyticsTests(AgencySpaceTestBase):
    def test_owner_analytics_api(self):
        prop = CRMProperty.objects.create(user=self.advisor, agency=self.agency, title='a')
        publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self.client.force_login(self.owner)
        url = reverse('workspace:api_agency_space_analytics')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['ok'])
        self.assertGreaterEqual(data['analytics']['active_properties'], 1)

    def test_manager_analytics(self):
        self.assertTrue(can_view_space_analytics(self.manager, self.agency))
        payload = get_space_analytics_payload(self.agency)
        self.assertIn('total_copies', payload)

    def test_advisor_analytics_denied(self):
        self.assertFalse(can_view_space_analytics(self.advisor, self.agency))
        self.client.force_login(self.advisor)
        url = reverse('workspace:api_agency_space_analytics')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 403)

    def test_contributor_stats(self):
        prop = CRMProperty.objects.create(user=self.advisor, agency=self.agency, title='x')
        publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        rows = get_contributor_metrics(self.agency)
        self.assertTrue(any(r['user_id'] == self.advisor.id for r in rows))

    def test_no_pii_in_analytics(self):
        payload = get_space_analytics_payload(self.agency)
        blob = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn(self.advisor.phone, blob)

    def test_no_cross_agency_analytics(self):
        prop = CRMProperty.objects.create(user=self.advisor, agency=self.agency, title='ours')
        publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self.client.force_login(self.other_agency_user)
        url = reverse('workspace:api_agency_space_analytics')
        res = self.client.get(url)
        if res.status_code == 200:
            self.assertEqual(res.json()['analytics']['active_properties'], 0)
        else:
            self.assertIn(res.status_code, (403, 404))


class AgencySpacePhase3ManagementTests(AgencySpaceTestBase):
    def test_moderation_hidden_visible_in_management(self):
        prop = CRMProperty.objects.create(user=self.advisor, agency=self.agency, title='m')
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        hide_space_item_public(self.manager, item.pk)
        qs = get_space_management_qs(self.manager, status_filter='hidden')
        self.assertEqual(qs.count(), 1)

    def test_confidential_safe_metadata_management(self):
        prop = CRMProperty.objects.create(
            user=self.advisor, agency=self.agency, title='CONFIDENTIAL_TITLE_HIDDEN',
        )
        item = publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        from workspace.services.agency_space_query import serialize_management_row

        row = serialize_management_row(item, self.manager)
        self.assertEqual(row.get('view_mode'), 'safe')
        self.assertNotIn('property', row)

    def test_moderation_hidden_visible_management_list(self):
        self.client.force_login(self.manager)
        prop = CRMProperty.objects.create(user=self.advisor, agency=self.agency, title='h')
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        hide_space_item_public(self.manager, item.pk)
        url = reverse('workspace:agency_hub_space_manage')
        res = self.client.get(url + '?status=hidden')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, f'#{item.pk}')
