"""Agency Space Phase 2 — hardening audit tests."""
import threading
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.models import (
    AgencySpaceCopy,
    AgencySpaceItem,
    CRMProperty,
    CRMResourceShare,
    Customer,
    CustomerActivity,
    Reminder,
)
from workspace.services.agency_onboarding import link_agency_to_subscription
from workspace.services.agency_seats import assign_seat_to_member
from django.db import IntegrityError

from workspace.services.agency_space_copy import AgencySpaceCopyError, copy_space_item_to_personal_crm
from workspace.services.agency_space_moderation import hide_space_item_public
from workspace.services.agency_space_provenance import provenance_for_customer, provenance_for_property
from workspace.services.agency_space_publish import publish_customer, publish_property, update_space_item
from workspace.services.agency_space_query import get_space_item_for_user
from workspace.services.crm_agency import create_agency
from workspace.tests.test_agency_space_phase1 import AgencySpaceTestBase

User = get_user_model()


class AgencySpaceCopyIntegrityTests(AgencySpaceTestBase):
    def _seat_advisor2(self):
        lic = License.objects.filter(agency_subscription=self.sub).order_by('pk').last()
        assign_seat_to_member(self.owner, lic.pk, self.advisor2.pk)

    def test_delete_copied_customer_target_keeps_provenance_row(self):
        c = self._customer(phone='09121112233')
        c.national_id = '1234567890'
        c.save()
        item = publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_FULL,
        )
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_c = Customer.objects.get(pk=result.target_id)
        rec = AgencySpaceCopy.objects.get(pk=result.copy_id)
        copy_c.delete()
        rec.refresh_from_db()
        self.assertIsNone(rec.copied_customer_id)
        self.assertEqual(rec.target_kind, AgencySpaceCopy.TARGET_CUSTOMER)
        self.assertEqual(rec.target_id_snapshot, result.target_id)

    def test_hard_delete_copied_property_target_keeps_provenance_row(self):
        prop = self._prop()
        prop.phone = '09123334455'
        prop.save()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_prop = CRMProperty.objects.get(pk=result.target_id)
        rec = AgencySpaceCopy.objects.get(pk=result.copy_id)
        copy_prop.delete()
        rec.refresh_from_db()
        self.assertIsNone(rec.copied_property_id)
        self.assertEqual(rec.target_kind, AgencySpaceCopy.TARGET_PROPERTY)
        self.assertEqual(rec.target_id_snapshot, result.target_id)

    def test_national_id_never_copied_summary(self):
        c = self._customer(phone='09120001111')
        c.national_id = '1111111111'
        c.email = 'a@b.com'
        c.phone_alt = '09120002222'
        c.save()
        item = publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_c = Customer.objects.get(pk=result.target_id)
        self.assertEqual(copy_c.phone, '')
        self.assertEqual(copy_c.phone_alt, '')
        self.assertEqual(copy_c.email, '')
        self.assertEqual(copy_c.national_id, '')

    def test_national_id_never_copied_full(self):
        c = self._customer(phone='09120003333')
        c.national_id = '2222222222'
        c.email = 'c@d.com'
        c.save()
        item = publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_FULL,
        )
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_c = Customer.objects.get(pk=result.target_id)
        self.assertEqual(copy_c.phone, '09120003333')
        self.assertEqual(copy_c.email, 'c@d.com')
        self.assertEqual(copy_c.national_id, '')

    def test_property_sensitive_fields_not_copied(self):
        prop = self._prop()
        prop.phone = '09124445566'
        prop.owner_name = 'مالک مخفی'
        prop.tenant_name = 'مستاجر'
        prop.tenant_phone = '09125556677'
        prop.notes = 'یادداشت داخلی'
        prop.save()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_p = CRMProperty.objects.get(pk=result.target_id)
        self.assertEqual(copy_p.phone, '')
        self.assertEqual(copy_p.owner_name, '')
        self.assertEqual(copy_p.tenant_name, '')
        self.assertEqual(copy_p.tenant_phone, '')
        self.assertEqual(copy_p.notes, '')
        self.assertEqual(copy_p.title, 'ملک تست')

    def test_audience_removed_after_copy_personal_remains(self):
        prop = self._prop()
        item = publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        update_space_item(
            self.advisor, item.pk,
            member_ids=[self.secretary_member.pk],
        )
        self.assertIsNone(get_space_item_for_user(self.advisor2, item.pk))
        self.assertTrue(CRMProperty.objects.filter(pk=result.target_id).exists())
        self.assertTrue(AgencySpaceCopy.objects.filter(pk=result.copy_id).exists())

    def test_public_to_confidential_after_copy(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        update_space_item(
            self.advisor, item.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.secretary_member.pk],
        )
        self.assertTrue(CRMProperty.objects.filter(pk=result.target_id).exists())

    def test_moderation_hidden_after_copy(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        hide_space_item_public(self.manager, item.pk)
        self.assertTrue(CRMProperty.objects.filter(pk=result.target_id).exists())
        self.assertTrue(AgencySpaceCopy.objects.filter(pk=result.copy_id).exists())

    def test_property_source_edit_independence(self):
        prop = self._prop()
        prop.sale_price = 1_000_000_000
        prop.phone = '09120000001'
        prop.notes = 'n1'
        prop.area = 100
        prop.save()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_p = CRMProperty.objects.get(pk=result.target_id)
        prop.title = 'تغییر'
        prop.sale_price = 2_000_000_000
        prop.phone = '09129999999'
        prop.notes = 'n2'
        prop.area = 200
        prop.save()
        copy_p.refresh_from_db()
        self.assertEqual(copy_p.title, 'ملک تست')
        self.assertEqual(copy_p.sale_price, 1_000_000_000)
        self.assertEqual(copy_p.phone, '')
        self.assertEqual(copy_p.notes, '')
        self.assertEqual(copy_p.area, 100)

    def test_customer_source_edit_independence(self):
        c = self._customer(phone='09121110000')
        c.budget_max = 5_000_000_000
        c.notes = 'need1'
        c.status = 'در حال پیگیری'
        c.save()
        item = publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_FULL,
        )
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_c = Customer.objects.get(pk=result.target_id)
        c.phone = '09122220000'
        c.budget_max = 9_000_000_000
        c.notes = 'need2'
        c.status = 'بسته شده'
        c.save()
        copy_c.refresh_from_db()
        self.assertEqual(copy_c.phone, '09121110000')
        self.assertEqual(copy_c.budget_max, 5_000_000_000)
        self.assertEqual(copy_c.notes, 'need1')
        self.assertEqual(copy_c.status, 'جدید')

    def test_property_target_edit_does_not_affect_source(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_p = CRMProperty.objects.get(pk=result.target_id)
        copy_p.title = 'نسخه من'
        copy_p.sale_price = 999
        copy_p.save()
        prop.refresh_from_db()
        self.assertEqual(prop.title, 'ملک تست')

    def test_customer_target_edit_does_not_affect_source(self):
        c = self._customer()
        item = publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_c = Customer.objects.get(pk=result.target_id)
        copy_c.name = 'نام جدید'
        copy_c.save()
        c.refresh_from_db()
        self.assertEqual(c.name, 'مشتری تست')

    def test_target_agency_is_copier_membership(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_p = CRMProperty.objects.get(pk=result.target_id)
        self.assertEqual(copy_p.agency_id, self.agency.id)
        self.assertEqual(copy_p.user_id, self.advisor2.id)

    def test_customer_shares_and_relations_not_copied(self):
        c = self._customer()
        CRMResourceShare.objects.create(
            agency=self.agency, customer=c, owner=self.advisor,
            shared_by=self.advisor, shared_with=self.manager,
        )
        Reminder.objects.create(
            user=self.advisor, customer=c, title='r',
            due_at=timezone.now(),
        )
        CustomerActivity.objects.create(customer=c, activity_type='تماس', title='t')
        item = publish_customer(
            self.advisor, c.pk,
            visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
            contact_share_level=AgencySpaceItem.CONTACT_SUMMARY,
        )
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        self.assertFalse(CRMResourceShare.objects.filter(customer_id=result.target_id).exists())
        self.assertEqual(Reminder.objects.filter(customer_id=result.target_id).count(), 0)
        self.assertEqual(CustomerActivity.objects.filter(customer_id=result.target_id).count(), 0)

    def test_provenance_no_space_link_without_permission(self):
        prop = self._prop()
        item = publish_property(
            self.advisor, prop.pk,
            visibility=AgencySpaceItem.VISIBILITY_SELECTED_MEMBERS,
            member_ids=[self.advisor2_member.pk],
        )
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_p = CRMProperty.objects.get(pk=result.target_id)
        prov = provenance_for_property(copy_p, self.advisor2)
        self.assertTrue(prov.get('space_item_url'))
        update_space_item(self.advisor, item.pk, member_ids=[self.secretary_member.pk])
        prov2 = provenance_for_property(copy_p, self.advisor2)
        self.assertFalse(prov2.get('space_item_url'))

    def test_copy_count_historical_after_target_delete(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self._seat_advisor2()
        result = copy_space_item_to_personal_crm(self.advisor2, item.pk)
        copy_p = CRMProperty.objects.get(pk=result.target_id)
        copy_p.delete()
        self.assertEqual(AgencySpaceCopy.objects.filter(item=item).count(), 1)

    def test_transaction_rollback_no_orphan_property(self):
        prop = self._prop()
        item = publish_property(self.advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        self._seat_advisor2()
        before = CRMProperty.objects.filter(user=self.advisor2).count()

        def fail_create(*args, **kwargs):
            raise IntegrityError('forced')

        with patch.object(AgencySpaceCopy.objects, 'create', side_effect=fail_create):
            with self.assertRaises(AgencySpaceCopyError):
                copy_space_item_to_personal_crm(self.advisor2, item.pk)
        after = CRMProperty.objects.filter(user=self.advisor2).count()
        self.assertEqual(before, after)


class AgencySpacePostgresConcurrencyTests(TransactionTestCase):
    def setUp(self):
        if 'postgresql' not in connection.vendor:
            self.skipTest('PostgreSQL required for concurrency test')

    def test_concurrent_copy_one_target(self):
        from unittest.mock import patch
        from workspace.services.agency_onboarding import link_agency_to_subscription
        from workspace.services.agency_entitlement import provision_subscription_from_paid_order
        from workspace.models import CRMAgencyMember

        feature_patch = patch.dict(
            'workspace.constants.AGENCY_COMMAND_CENTER_FEATURES',
            {'agency_space': True},
            clear=False,
        )
        feature_patch.start()
        self.addCleanup(feature_patch.stop)

        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        owner = User.objects.create_user(username=f'0914{base:07d}', phone=f'0914{base:07d}', password='x')
        advisor = User.objects.create_user(username=f'0914{base+1:07d}', phone=f'0914{base+1:07d}', password='x')
        advisor2 = User.objects.create_user(username=f'0914{base+2:07d}', phone=f'0914{base+2:07d}', password='x')
        agency = create_agency(owner, 'PG')
        product = Product.objects.create(
            title='t', slug=f'pg-{uuid.uuid4().hex[:8]}', description='t', is_active=True,
        )
        plan = LicensePlan.objects.create(
            product=product, name='p', plan_type='monthly', price=990_000, duration_days=30,
            max_activations=2, allow_bulk_purchase=True, min_quantity=2, max_quantity=10, is_active=True,
        )
        order = Order.objects.create(
            user=owner, product=product, plan=plan, quantity=2, amount=1_980_000,
            status='paid', paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order)
        sub = provision_subscription_from_paid_order(order)
        link_agency_to_subscription(agency, sub)
        CRMAgencyMember.objects.create(
            agency=agency, user=advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        CRMAgencyMember.objects.create(
            agency=agency, user=advisor2, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        licenses = list(License.objects.filter(agency_subscription=sub).order_by('pk'))
        assign_seat_to_member(owner, licenses[0].pk, advisor.pk)
        assign_seat_to_member(owner, licenses[1].pk, advisor2.pk)
        prop = CRMProperty.objects.create(user=advisor, agency=agency, title='race')
        item = publish_property(advisor, prop.pk, visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC)
        errors = []

        def worker():
            try:
                connection.close()
                copy_space_item_to_personal_crm(advisor2, item.pk)
            except Exception as exc:
                errors.append(exc)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        self.assertEqual(errors, [])
        self.assertEqual(AgencySpaceCopy.objects.filter(item=item, copied_by=advisor2).count(), 1)
        self.assertEqual(CRMProperty.objects.filter(user=advisor2, title='race').count(), 1)
