"""Agency Space — Phase 1 tests."""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.models import (
    AgencySpaceItem,
    AgencySubscription,
    CRMAgencyMember,
    CRMProperty,
    Customer,
)
from workspace.services.agency_entitlement import provision_subscription_from_paid_order
from workspace.services.agency_members import remove_agency_member
from workspace.services.agency_seats import assign_seat_to_member
from workspace.services.agency_space_access import (
    can_publish_to_agency_space,
    can_view_space_item,
)
from workspace.services.agency_space_publish import publish_customer, publish_property
from workspace.services.agency_space_query import get_space_item_for_user
from workspace.services.agency_space_serialize import serialize_space_item
from workspace.services.crm_agency import create_agency, remove_member
from workspace.services.crm_scope import get_membership
from workspace.services.agency_onboarding import link_agency_to_subscription
from workspace.tests.agency_test_utils import ensure_agency_subscription

User = get_user_model()


class AgencySpaceTestBase(TestCase):
    def setUp(self):
        self.feature_patch = patch.dict(
            'workspace.constants.AGENCY_COMMAND_CENTER_FEATURES',
            {'agency_space': True},
            clear=False,
        )
        self.feature_patch.start()
        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        self.phones = [f'0914{base + i:07d}' for i in range(6)]
        self.owner = User.objects.create_user(username=self.phones[0], phone=self.phones[0], password='x')
        self.manager = User.objects.create_user(username=self.phones[1], phone=self.phones[1], password='x')
        self.advisor = User.objects.create_user(username=self.phones[2], phone=self.phones[2], password='x')
        self.advisor2 = User.objects.create_user(username=self.phones[3], phone=self.phones[3], password='x')
        self.secretary = User.objects.create_user(username=self.phones[4], phone=self.phones[4], password='x')
        self.other_agency_user = User.objects.create_user(username=self.phones[5], phone=self.phones[5], password='x')

        self.agency = create_agency(self.owner, 'آژانس Space')
        product = Product.objects.create(
            title='Agency Space Test', slug=f'ag-sp-{uuid.uuid4().hex[:8]}',
            description='t', is_active=True,
        )
        plan = LicensePlan.objects.create(
            product=product, name='Agency', plan_type='monthly',
            price=990_000, duration_days=30, max_activations=2,
            allow_bulk_purchase=True, min_quantity=2, max_quantity=10, is_active=True,
        )
        order = Order.objects.create(
            user=self.owner, product=product, plan=plan,
            quantity=2, amount=1_980_000, status='paid', paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order)
        self.sub = provision_subscription_from_paid_order(order)
        link_agency_to_subscription(self.agency, self.sub)
        self.manager_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.manager, role='manager', is_active=True,
        )
        self.advisor_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        self.advisor2_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor2, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        self.secretary_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.secretary, role='secretary', is_active=True,
        )
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').first()
        assign_seat_to_member(self.owner, lic.pk, self.advisor.pk)

        self.other_agency = create_agency(self.other_agency_user, 'آژانس دیگر')
        ensure_agency_subscription(self.other_agency_user, self.other_agency)

        self.client = Client()

    def tearDown(self):
        self.feature_patch.stop()

    def _prop(self, user=None):
        user = user or self.advisor
        return CRMProperty.objects.create(
            user=user, agency=self.agency, title='ملک تست', phone='09121111111',
        )

    def _customer(self, user=None, phone='09122222222', notes='نیاز آپارتمان', **fields):
        user = user or self.advisor
        return Customer.objects.create(
            user=user,
            agency=self.agency,
            name='مشتری تست',
            phone=phone,
            notes=notes,
            **fields,
        )


class AgencySpacePublishTests(AgencySpaceTestBase):
    def test_public_property_publish(self):
        prop = self._prop(self.advisor)
        item = publish_property(
            self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
        )
        self.assertEqual(item.status, AgencySpaceItem.STATUS_ACTIVE)
        self.assertEqual(prop.user_id, self.advisor.id)

    def test_public_customer_publish_summary(self):
        c = self._customer()
        item = publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        data = serialize_space_item(item, self.advisor2, detail=True)
        self.assertEqual(data['customer']['phone'], '')

    def test_advisor_same_agency_sees_public(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self.assertTrue(can_view_space_item(self.advisor2, item))
        got = get_space_item_for_user(self.advisor2, item.pk)
        self.assertIsNotNone(got)

    def test_seated_advisor_member_hub_links_agency_space(self):
        self.client.force_login(self.advisor)
        resp = self.client.get(reverse('workspace:agency_advisor_member'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse('workspace:agency_hub_space'))
        self.assertContains(resp, 'فضای آژانس')

    def test_advisor_agency_space_uses_member_hub_shell(self):
        self.client.force_login(self.advisor)
        resp = self.client.get(reverse('workspace:agency_hub_space'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'agency-member-hub--space')
        self.assertContains(resp, 'پنل عضویت آژانس')
        self.assertContains(resp, 'amh-tab--space is-active')
        self.assertNotContains(resp, 'agency-hub-nav--ref')
        self.assertNotContains(resp, 'agency-hero__eyebrow">مدیریت آژانس')

    def test_advisor_no_seat_sees_public_read_only(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self.assertTrue(can_view_space_item(self.advisor2, item))
        self.assertFalse(can_publish_to_agency_space(self.advisor2))

    def test_advisor_no_seat_cannot_publish(self):
        prop = self._prop(self.advisor2)
        with self.assertRaises(Exception):
            publish_property(self.advisor2, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)

    def test_agency_b_cannot_see(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self.assertIsNone(get_space_item_for_user(self.other_agency_user, item.pk))

    def test_confidential_selected_user_sees(self):
        prop = self._prop()
        item = publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        self.assertTrue(can_view_space_item(self.advisor2, item))
        self.assertFalse(can_view_space_item(self.secretary, item))

    def test_manager_not_auto_confidential(self):
        prop = self._prop()
        item = publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        self.assertFalse(can_view_space_item(self.manager, item))

    def test_publisher_sees_own_confidential(self):
        prop = self._prop()
        item = publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        self.assertTrue(can_view_space_item(self.advisor, item))

    def test_publisher_owns_source_not_copy_target(self):
        from workspace.services.agency_space_serialize import serialize_space_item

        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        data = serialize_space_item(item, self.advisor, detail=True)
        self.assertTrue(data['owns_source_in_crm'])
        self.assertFalse(data['can_copy'])
        self.assertIn(str(prop.pk), data['source_crm_url'])

    def test_secretary_sees_public(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self.assertTrue(can_view_space_item(self.secretary, item))

    def test_secretary_cannot_publish(self):
        prop = self._prop(self.secretary)
        self.assertFalse(can_publish_to_agency_space(self.secretary))
        with self.assertRaises(Exception):
            publish_property(self.secretary, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)

    def test_duplicate_active_blocked(self):
        prop = self._prop()
        publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        with self.assertRaises(Exception):
            publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)

    def test_customer_full_phone_authorized_only(self):
        c = self._customer(phone='09123334444')
        item = publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            contact_share_level=AgencySpaceItem.CONTACT_FULL,
            member_ids=[self.advisor2_member.pk],
        )
        data_auth = serialize_space_item(item, self.advisor2, detail=True)
        data_denied = serialize_space_item(item, self.secretary, detail=True)
        self.assertIsNone(data_denied)
        self.assertEqual(data_auth['customer']['phone'], '09123334444')

    def test_cross_agency_publish_blocked(self):
        foreign = CRMProperty.objects.create(
            user=self.other_agency_user, agency=self.other_agency, title='خارجی',
        )
        with self.assertRaises(Exception):
            publish_property(self.advisor, foreign.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)


class AgencySpaceLifecycleTests(AgencySpaceTestBase):
    def test_unpublish_archives_only(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        from workspace.services.agency_space_publish import unpublish_space_item
        unpublish_space_item(self.advisor, item.pk)
        item.refresh_from_db()
        prop.refresh_from_db()
        self.assertEqual(item.status, AgencySpaceItem.STATUS_ARCHIVED)
        self.assertEqual(prop.user_id, self.advisor.id)

    def test_removed_member_archives(self):
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        prop = self._prop(self.advisor2)
        publish_property(self.advisor2, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        remove_agency_member(self.owner, self.advisor2_member.pk)
        item = AgencySpaceItem.objects.get(property=prop)
        self.assertEqual(item.status, AgencySpaceItem.STATUS_ARCHIVED)

    def test_deactivated_member_archives(self):
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        prop = self._prop(self.advisor2)
        publish_property(self.advisor2, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        remove_member(self.manager, self.advisor2_member.pk)
        item = AgencySpaceItem.objects.get(property=prop)
        self.assertEqual(item.status, AgencySpaceItem.STATUS_ARCHIVED)

    def test_deleted_source_archives(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        prop.deleted_at = timezone.now()
        prop.save()
        item.refresh_from_db()
        self.assertEqual(item.status, AgencySpaceItem.STATUS_ARCHIVED)

    def test_expired_subscription_blocks_access(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        AgencySubscription.objects.filter(agency=self.agency).update(
            status=AgencySubscription.STATUS_EXPIRED,
            expires_at=timezone.now() - timedelta(days=1),
        )
        self.assertIsNone(get_space_item_for_user(self.advisor2, item.pk))

    def test_audit_on_publish(self):
        from workspace.models import CRMAgencyAuditLog
        prop = self._prop()
        publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self.assertTrue(
            CRMAgencyAuditLog.objects.filter(agency=self.agency, event='space.published').exists()
        )


class AgencySpaceAuditEventTests(AgencySpaceTestBase):
    def test_audit_visibility_changed(self):
        from workspace.models import CRMAgencyAuditLog
        from workspace.services.agency_space_publish import update_space_item

        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        update_space_item(
            self.advisor, item.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        self.assertTrue(
            CRMAgencyAuditLog.objects.filter(agency=self.agency, event='space.visibility_changed').exists()
        )

    def test_audit_audience_changed(self):
        from workspace.models import CRMAgencyAuditLog
        from workspace.services.agency_space_publish import update_space_item

        prop = self._prop()
        item = publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        update_space_item(
            self.advisor, item.pk,
            member_ids=[self.secretary_member.pk],
        )
        self.assertTrue(
            CRMAgencyAuditLog.objects.filter(agency=self.agency, event='space.audience_changed').exists()
        )

    def test_audit_moderation_hidden(self):
        from workspace.models import CRMAgencyAuditLog
        from workspace.services.agency_space_moderation import hide_space_item_public

        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        hide_space_item_public(self.manager, item.pk)
        self.assertTrue(
            CRMAgencyAuditLog.objects.filter(agency=self.agency, event='space.moderation_hidden').exists()
        )

    def test_audit_moderation_restored(self):
        from workspace.models import CRMAgencyAuditLog
        from workspace.services.agency_space_moderation import hide_space_item_public, restore_space_item_moderation

        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        hide_space_item_public(self.manager, item.pk)
        restore_space_item_moderation(self.manager, item.pk)
        self.assertTrue(
            CRMAgencyAuditLog.objects.filter(agency=self.agency, event='space.moderation_restored').exists()
        )


class AgencySpaceAPITests(AgencySpaceTestBase):
    def test_idor_detail_blocked(self):
        prop = self._prop()
        item = publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        self.client.force_login(self.secretary)
        resp = self.client.get(
            reverse('workspace:api_agency_space_item', kwargs={'item_id': item.pk}),
        )
        self.assertEqual(resp.status_code, 404)

    def test_moderation_public(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self.client.force_login(self.manager)
        resp = self.client.post(
            reverse('workspace:api_agency_space_moderate', kwargs={'item_id': item.pk}),
            data='{"action":"hide"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, AgencySpaceItem.STATUS_MODERATION_HIDDEN)
