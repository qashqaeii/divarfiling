"""Agency Space Phase 2 — personal copy tests."""
import threading
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.models import (
    AgencySpaceCopy,
    AgencySpaceItem,
    AgencySubscription,
    CRMAgencyAuditLog,
    CRMProperty,
    CRMResourceShare,
    Customer,
    Reminder,
)
from workspace.services.agency_members import remove_agency_member
from workspace.services.agency_onboarding import link_agency_to_subscription
from workspace.services.agency_seats import assign_seat_to_member
from workspace.services.agency_space_copy import AgencySpaceCopyError, copy_space_item_to_personal_crm
from workspace.services.agency_space_publish import publish_customer, publish_property, unpublish_space_item
from workspace.services.crm_agency import create_agency
from workspace.services.crm_scope import property_for_user
from workspace.tests.test_agency_space_phase1 import AgencySpaceTestBase

User = get_user_model()


class AgencySpaceCopyTests(AgencySpaceTestBase):
    def test_advisor_seat_copies_public_property(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        self.assertFalse(result.already_copied)
        self.assertEqual(result.kind, 'property')

    def test_copied_property_owner_is_copier(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_prop = CRMProperty.objects.get(pk=result.target_id)
        self.assertEqual(copy_prop.user_id, self.advisor2.id)

    def test_source_property_unchanged(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        copy_space_item_to_personal_crm(self.advisor2, item.pk)
        prop.refresh_from_db()
        self.assertEqual(prop.user_id, self.advisor.id)
        self.assertEqual(prop.title, 'ملک تست')

    def test_copy_independent_after_source_edit(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        prop.title = 'تغییر منبع'
        prop.save()
        copy_prop = CRMProperty.objects.get(pk=result.target_id)
        self.assertEqual(copy_prop.title, 'ملک تست')

    def test_customer_full_includes_phone(self):
        c = self._customer(phone='09125556677')
        item = publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_FULL,
        )
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_c = Customer.objects.get(pk=result.target_id)
        self.assertEqual(copy_c.phone, '09125556677')

    def test_customer_summary_excludes_phone(self):
        c = self._customer(phone='09126667788')
        item = publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_c = Customer.objects.get(pk=result.target_id)
        self.assertEqual(copy_c.phone, '')

    def test_confidential_selected_advisor_can_copy(self):
        prop = self._prop()
        item = publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        self.assertTrue(result.target_id)

    def test_unselected_advisor_cannot_copy(self):
        prop = self._prop()
        item = publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        with self.assertRaises((PermissionError, AgencySpaceCopyError)):
            copy_space_item_to_personal_crm(self.secretary, item.pk)

    def test_manager_cannot_copy_confidential_without_audience(self):
        prop = self._prop()
        item = publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        with self.assertRaises((PermissionError, AgencySpaceCopyError)):
            copy_space_item_to_personal_crm(self.manager, item.pk)

    def test_advisor_no_seat_cannot_copy(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        with self.assertRaises((PermissionError, AgencySpaceCopyError)):
            copy_space_item_to_personal_crm(self.advisor2, item.pk)

    def test_secretary_cannot_copy(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        with self.assertRaises((PermissionError, AgencySpaceCopyError)):
            copy_space_item_to_personal_crm(self.secretary, item.pk)

    def test_cross_agency_cannot_copy(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        foreign_prop = CRMProperty.objects.create(
            user=self.other_agency_user, agency=self.other_agency, title='x',
        )
        self.assertNotEqual(item.agency_id, self.other_agency.id)
        with self.assertRaises((AgencySpaceCopyError, PermissionError)):
            copy_space_item_to_personal_crm(self.other_agency_user, item.pk)

    def test_duplicate_copy_returns_existing(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        r1 = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        r2 = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        self.assertFalse(r1.already_copied)
        self.assertTrue(r2.already_copied)
        self.assertEqual(r1.target_id, r2.target_id)

    def test_only_one_agency_space_copy_row(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_space_item_to_personal_crm(self.advisor2, item.pk)
        self.assertEqual(AgencySpaceCopy.objects.filter(item=item, copied_by=self.advisor2).count(), 1)

    def test_source_unpublish_copy_remains(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        unpublish_space_item(self.advisor, item.pk)
        self.assertTrue(CRMProperty.objects.filter(pk=result.target_id).exists())

    def test_source_delete_copy_remains(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        prop.deleted_at = timezone.now()
        prop.save()
        self.assertTrue(CRMProperty.objects.filter(pk=result.target_id).exists())

    def test_publisher_leaves_copy_remains(self):
        prop = self._prop(self.advisor2)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        item = publish_property(self.advisor2, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        result = copy_space_item_to_personal_crm(self.advisor, item.pk)
        remove_agency_member(self.owner, self.advisor2_member.pk)
        self.assertTrue(CRMProperty.objects.filter(pk=result.target_id).exists())

    def test_copier_leaves_agency_copy_remains(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        remove_agency_member(self.owner, self.advisor2_member.pk)
        self.assertTrue(CRMProperty.objects.filter(pk=result.target_id).exists())
        self.assertTrue(AgencySpaceCopy.objects.filter(pk=result.copy_id).exists())

    def test_audit_item_copied(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        copy_space_item_to_personal_crm(self.advisor2, item.pk)
        self.assertTrue(
            CRMAgencyAuditLog.objects.filter(agency=self.agency, event='space.item_copied').exists()
        )

    def test_copied_in_personal_crm(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        self.assertIsNotNone(property_for_user(self.advisor2, result.target_id))

    def test_source_shares_not_copied(self):
        prop = self._prop()
        CRMResourceShare.objects.create(
            agency=self.agency,
            property=prop,
            owner=self.advisor,
            shared_by=self.advisor,
            shared_with=self.manager,
        )
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        self.assertFalse(
            CRMResourceShare.objects.filter(property_id=result.target_id).exists()
        )

    def test_customer_team_state_not_copied(self):
        c = self._customer()
        c.assigned_to = self.manager
        c.team_visibility = 'team_inbox'
        c.save()
        item = publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_c = Customer.objects.get(pk=result.target_id)
        self.assertIsNone(copy_c.assigned_to_id)
        self.assertEqual(copy_c.team_visibility, 'private')

    def test_customer_reminders_not_copied(self):
        c = self._customer()
        Reminder.objects.create(
            user=self.advisor, customer=c, title='y', due_at=timezone.now() + timedelta(days=1),
        )
        item = publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        self.assertEqual(Reminder.objects.filter(customer_id=result.target_id).count(), 0)

    def test_target_url_correct(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        self.client.force_login(self.advisor2)
        resp = self.client.get(result.target_url)
        self.assertEqual(resp.status_code, 200)


class AgencySpaceCopyConcurrencyTests(TransactionTestCase):
    def setUp(self):
        from unittest.mock import patch
        self.feature_patch = patch.dict(
            'workspace.constants.AGENCY_COMMAND_CENTER_FEATURES',
            {'agency_space': True},
            clear=False,
        )
        self.feature_patch.start()
        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        self.owner = User.objects.create_user(username=f'0914{base:07d}', phone=f'0914{base:07d}', password='x')
        self.advisor = User.objects.create_user(username=f'0914{base+1:07d}', phone=f'0914{base+1:07d}', password='x')
        self.advisor2 = User.objects.create_user(username=f'0914{base+2:07d}', phone=f'0914{base+2:07d}', password='x')
        self.agency = create_agency(self.owner, 'آژانس')
        product = Product.objects.create(
            title='t', slug=f'c-{uuid.uuid4().hex[:8]}', description='t', is_active=True,
        )
        plan = LicensePlan.objects.create(
            product=product, name='p', plan_type='monthly', price=990_000, duration_days=30,
            max_activations=2, allow_bulk_purchase=True, min_quantity=2, max_quantity=10, is_active=True,
        )
        order = Order.objects.create(
            user=self.owner, product=product, plan=plan, quantity=2, amount=1_980_000,
            status='paid', paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order)
        from workspace.services.agency_entitlement import provision_subscription_from_paid_order
        self.sub = provision_subscription_from_paid_order(order)
        link_agency_to_subscription(self.agency, self.sub)
        from workspace.models import CRMAgencyMember
        CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor2, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        licenses = list(License.objects.filter(agency_subscription=self.sub).order_by('pk'))
        assign_seat_to_member(self.owner, licenses[0].pk, self.advisor.pk)
        assign_seat_to_member(self.owner, licenses[1].pk, self.advisor2.pk)

    def tearDown(self):
        self.feature_patch.stop()

    def test_concurrent_copy_single_target(self):
        if connection.vendor == 'sqlite':
            self.skipTest('SQLite table locking limits threaded concurrency test')
        prop = CRMProperty.objects.create(user=self.advisor, agency=self.agency, title='race')
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        errors = []

        def worker():
            try:
                connection.close()
                copy_space_item_to_personal_crm(self.advisor2, item.pk)
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.assertEqual(errors, [])
        self.assertEqual(AgencySpaceCopy.objects.filter(item=item, copied_by=self.advisor2).count(), 1)
        self.assertEqual(CRMProperty.objects.filter(user=self.advisor2, title='race').count(), 1)
