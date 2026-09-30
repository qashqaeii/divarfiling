"""Agency Space UX — tab/scope/filter parsing."""
from workspace.services.agency_space_params import (
    SpaceListFilters,
    parse_space_list_filters,
)
from workspace.services.agency_space_query import get_space_items_from_filters
from workspace.tests.test_agency_space_phase1 import AgencySpaceTestBase
from workspace.services.agency_seats import assign_seat_to_member
from licenses.models import License
from workspace.models import AgencySpaceItem
from workspace.services.agency_space_publish import publish_property
from workspace.models import CRMProperty


class AgencySpaceUxNavTests(AgencySpaceTestBase):
    def test_overview_tab_alias(self):
        f = parse_space_list_filters({'tab': 'all'})
        self.assertEqual(f.normalized_tab(), 'overview')
        self.assertTrue(f.is_overview())

    def test_legacy_published_by_me_becomes_scope(self):
        f = parse_space_list_filters({'tab': 'published_by_me'})
        self.assertEqual(f.normalized_tab(), 'properties')
        self.assertEqual(f.normalized_scope(), 'published_by_me')

    def test_crm_tab_alias(self):
        f = parse_space_list_filters({'tab': 'saved_by_me'})
        self.assertEqual(f.normalized_tab(), 'crm')

    def test_scope_copied_by_me_filters(self):
        prop = CRMProperty.objects.create(
            user=self.advisor, agency=self.agency, title='Scope copy', sale_price=1_000_000,
        )
        item = publish_property(
            self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
        )
        from workspace.services.agency_space_copy import copy_space_item_to_personal_crm
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        copy_space_item_to_personal_crm(self.advisor2, item.pk)
        f = SpaceListFilters(tab='properties', scope='copied_by_me')
        self.assertEqual(get_space_items_from_filters(self.advisor2, f).count(), 1)
        f2 = SpaceListFilters(tab='properties', scope='all', crm_copy='not_copied')
        self.assertEqual(get_space_items_from_filters(self.advisor2, f2).count(), 0)

    def test_contact_share_level_filter(self):
        from workspace.services.agency_space_publish import publish_customer
        from workspace.models import Customer

        c = Customer.objects.create(user=self.advisor, agency=self.agency, name='Share F')
        publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        f = SpaceListFilters(tab='contacts', contact_share_level='summary')
        self.assertEqual(get_space_items_from_filters(self.advisor2, f).count(), 1)
        f2 = SpaceListFilters(tab='contacts', contact_share_level='full')
        self.assertEqual(get_space_items_from_filters(self.advisor2, f2).count(), 0)

    def test_query_string_keeps_scope(self):
        f = SpaceListFilters(tab='properties', scope='published_by_me', city='تهران')
        qs = f.query_string()
        self.assertIn('tab=properties', qs)
        self.assertIn('scope=published_by_me', qs)
        self.assertIn('city', qs)

    def test_jalali_date_filter_parsing(self):
        from django.http import QueryDict

        qd = QueryDict('tab=properties&published_after=1403/06/15')
        f = parse_space_list_filters(qd)
        self.assertIsNotNone(f.published_after)
        self.assertTrue(f.published_after_jalali())

    def test_price_range_chip_clears_min_and_max(self):
        from workspace.services.agency_space_params import build_space_filter_chips

        f = SpaceListFilters(tab='properties', min_price=100, max_price=500)
        chips = build_space_filter_chips(f)
        price_chip = next(c for c in chips if c['label'].startswith('قیمت'))
        self.assertNotIn('min_price=100', price_chip['clear_query'])
        self.assertNotIn('max_price=500', price_chip['clear_query'])

    def test_property_detail_includes_full_specs(self):
        from workspace.services.agency_space_serialize import serialize_space_item

        prop = CRMProperty.objects.create(
            user=self.advisor,
            agency=self.agency,
            title='Detail Prop',
            sale_price=5_000_000_000,
            area=120,
            land_area=200,
            phone='09121112233',
            owner_name='مالک',
            notes='یادداشت داخلی',
            feature_data={'گرمایش': 'پکیج'},
        )
        item = publish_property(
            self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
        )
        data = serialize_space_item(item, self.advisor2, detail=True)
        p = data['property']
        self.assertEqual(p['phone'], '09121112233')
        self.assertTrue(p['price_rows'])
        self.assertEqual(p['owner_name'], 'مالک')
        self.assertTrue(p['feature_data_rows'])

    def test_summary_contact_phone_not_discoverable_via_search(self):
        from workspace.services.agency_space_publish import publish_customer
        from workspace.models import Customer

        secret_phone = '09127776655'
        c = Customer.objects.create(
            user=self.advisor,
            agency=self.agency,
            name='مخاطب محرمانه',
            phone=secret_phone,
            notes=f'تماس {secret_phone}',
        )
        publish_customer(
            self.advisor,
            c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        f = SpaceListFilters(tab='contacts', q=secret_phone)
        self.assertEqual(get_space_items_from_filters(self.advisor2, f).count(), 0)

        c2 = Customer.objects.create(
            user=self.advisor,
            agency=self.agency,
            name='مخاطب کامل',
            phone=secret_phone,
        )
        publish_customer(
            self.advisor,
            c2.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_FULL,
        )
        f2 = SpaceListFilters(tab='contacts', q=secret_phone)
        self.assertEqual(get_space_items_from_filters(self.advisor2, f2).count(), 1)

    def test_publisher_filter_options_include_role_and_avatar(self):
        from workspace.services.agency_space_ui_context import build_space_publisher_filter_options

        opts = build_space_publisher_filter_options(None, self.agency, self.advisor.pk)
        by_id = {o['user_id']: o for o in opts}
        self.assertIn(self.advisor.pk, by_id)
        row = by_id[self.advisor.pk]
        self.assertTrue(row['selected'])
        self.assertTrue(row['avatar_url'])
        self.assertIn('role_label', row)
        self.assertIn('role_bg', row)

    def test_serialize_publisher_and_customer_avatars(self):
        from workspace.services.agency_space_publish import publish_customer
        from workspace.models import Customer
        from workspace.services.agency_space_serialize import serialize_space_item

        prop = CRMProperty.objects.create(
            user=self.advisor, agency=self.agency, title='Avatar card', sale_price=1,
        )
        p_item = publish_property(
            self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
        )
        pdata = serialize_space_item(p_item, self.advisor2, detail=False)
        self.assertIn('avatar_url', pdata['publisher'])
        self.assertIn('role_label', pdata['publisher'])

        c = Customer.objects.create(user=self.advisor, agency=self.agency, name='Avatar C')
        c_item = publish_customer(
            self.advisor,
            c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        cdata = serialize_space_item(c_item, self.advisor2, detail=False)
        self.assertIn('avatar_url', cdata['customer'])
        self.assertIn('finance_label', cdata['customer'])
        self.assertIn('area_label', cdata['customer'])
