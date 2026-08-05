"""تست مدیریت اسلات لایسنس و دسترسی تیم."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from licenses.models import License, LicenseActivation
from licenses.services.management import (
    activate_license_for_owner,
    assign_license_to_member,
    assign_seat_to_member,
    register_device_slot,
    release_license_to_pool,
    remove_device_slot,
    revoke_license_assignment,
    _allocation_state,
)
from shop.models import LicensePlan, Order, Product
from workspace.models import CRMAgency, CRMAgencyMember
from workspace.services.access import _assigned_license_qs, has_active_bot_license

User = get_user_model()


class LicenseSeatManagementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner', password='pass1234', phone='09123333331',
        )
        self.member = User.objects.create_user(
            username='advisor', password='pass1234', phone='09123333332',
        )
        self.product = Product.objects.create(
            title='ربات تست',
            slug='test-bot-seats',
            description='محصول تست',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='پلن ۳ سیستمی',
            plan_type='multi',
            price=300000,
            duration_days=30,
            max_activations=3,
            is_active=True,
        )
        order = Order.objects.create(
            user=self.owner,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
        )
        self.license = License.objects.create(
            order=order,
            plan=self.plan,
            license_key='MULT-0001-0002-0003',
            status='active',
            max_activations=3,
        )
        self.agency = CRMAgency.objects.create(
            name='آژانس تست',
            slug='test-agency',
            owner=self.owner,
        )
        CRMAgencyMember.objects.create(agency=self.agency, user=self.owner, role='owner')
        CRMAgencyMember.objects.create(agency=self.agency, user=self.member, role='advisor')

    def test_register_multiple_device_slots(self):
        register_device_slot(self.owner, self.license.pk, 'HW-FINGERPRINT-001', label='PC 1')
        register_device_slot(self.owner, self.license.pk, 'HW-FINGERPRINT-002', label='PC 2')
        self.assertEqual(self.license.activations.count(), 2)

    def test_register_exceeds_max_raises(self):
        register_device_slot(self.owner, self.license.pk, 'HW-FINGERPRINT-001')
        register_device_slot(self.owner, self.license.pk, 'HW-FINGERPRINT-002')
        register_device_slot(self.owner, self.license.pk, 'HW-FINGERPRINT-003')
        with self.assertRaises(Exception):
            register_device_slot(self.owner, self.license.pk, 'HW-FINGERPRINT-004')

    def test_team_member_gets_access_when_assigned_active_license(self):
        activation = register_device_slot(
            self.owner, self.license.pk, 'HW-FINGERPRINT-001',
        )
        activation.is_active = True
        activation.save()
        assign_seat_to_member(self.owner, activation.pk, self.member.id)
        self.assertTrue(has_active_bot_license(self.member))

    def test_team_member_without_assignment_no_access(self):
        self.assertFalse(has_active_bot_license(self.member))

    def test_register_device_api(self):
        self.client.login(username='owner', password='pass1234')
        resp = self.client.post(reverse('license_register_device'), {
            'license_id': self.license.pk,
            'hardware_fingerprint': 'HW-API-TEST-99',
            'label': 'لپ‌تاپ',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(self.license.activations.count(), 1)

    def test_remove_pending_slot(self):
        activation = register_device_slot(self.owner, self.license.pk, 'HW-REMOVE-PENDING')
        remove_device_slot(self.owner, activation.pk)
        self.assertEqual(self.license.activations.count(), 0)

    def test_remove_active_slot(self):
        activation = register_device_slot(self.owner, self.license.pk, 'HW-REMOVE-ACTIVE', label='PC فعال')
        activation.is_active = True
        activation.save()
        remove_device_slot(self.owner, activation.pk)
        self.assertEqual(self.license.activations.count(), 0)

    def test_remove_active_slot_via_api(self):
        activation = register_device_slot(self.owner, self.license.pk, 'HW-API-REMOVE')
        activation.is_active = True
        activation.save()
        self.client.login(username='owner', password='pass1234')
        resp = self.client.post(reverse('license_remove_device'), {'activation_id': activation.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        self.assertEqual(self.license.activations.count(), 0)


class LicenseKeyAssignmentTests(TestCase):
    """تخصیص کلید کامل لایسنس به عضو آژانس."""

    def setUp(self):
        self.owner = User.objects.create_user(
            username='agency_owner', password='pass1234', phone='09124444441',
        )
        self.member = User.objects.create_user(
            username='agency_advisor', password='pass1234', phone='09124444442',
        )
        self.member2 = User.objects.create_user(
            username='agency_advisor2', password='pass1234', phone='09124444443',
        )
        self.product = Product.objects.create(
            title='ربات آژانس',
            slug='test-bot-agency-assign',
            description='محصول تست',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='پلن آژانس ۳ کلید',
            plan_type='multi',
            price=900000,
            duration_days=30,
            max_activations=2,
            is_active=True,
        )
        self.order = Order.objects.create(
            user=self.owner,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
        )
        self.license_a = License.objects.create(
            order=self.order,
            plan=self.plan,
            license_key='AGCY-AAAA-0001-0001',
            status='inactive',
            max_activations=2,
            sequence=1,
        )
        self.license_b = License.objects.create(
            order=self.order,
            plan=self.plan,
            license_key='AGCY-BBBB-0002-0002',
            status='inactive',
            max_activations=2,
            sequence=2,
        )
        self.license_c = License.objects.create(
            order=self.order,
            plan=self.plan,
            license_key='AGCY-CCCC-0003-0003',
            status='inactive',
            max_activations=2,
            sequence=3,
        )
        self.agency = CRMAgency.objects.create(
            name='آژانس تخصیص',
            slug='test-agency-assign',
            owner=self.owner,
        )
        CRMAgencyMember.objects.create(agency=self.agency, user=self.owner, role='owner')
        CRMAgencyMember.objects.create(agency=self.agency, user=self.member, role='advisor')
        CRMAgencyMember.objects.create(agency=self.agency, user=self.member2, role='advisor')

    def test_assign_grants_immediate_access(self):
        self.assertFalse(has_active_bot_license(self.member))
        assign_license_to_member(self.owner, self.license_a.pk, self.member.id)
        self.license_a.refresh_from_db()
        self.assertEqual(self.license_a.assigned_user_id, self.member.id)
        self.assertEqual(self.license_a.status, 'active')
        self.assertTrue(has_active_bot_license(self.member))

    def test_revoke_removes_member_access(self):
        assign_license_to_member(self.owner, self.license_a.pk, self.member.id)
        self.assertTrue(has_active_bot_license(self.member))
        revoke_license_assignment(self.owner, self.license_a.pk)
        self.license_a.refresh_from_db()
        self.assertIsNone(self.license_a.assigned_user_id)
        self.assertEqual(self.license_a.status, 'inactive')
        self.assertFalse(has_active_bot_license(self.member))

    def test_one_license_per_member_from_same_owner(self):
        assign_license_to_member(self.owner, self.license_a.pk, self.member.id)
        with self.assertRaises(ValidationError):
            assign_license_to_member(self.owner, self.license_b.pk, self.member.id)

    def test_activate_for_owner_without_assigned_user(self):
        activate_license_for_owner(self.owner, self.license_a.pk)
        self.license_a.refresh_from_db()
        self.assertEqual(self.license_a.status, 'active')
        self.assertIsNone(self.license_a.assigned_user_id)
        self.assertTrue(has_active_bot_license(self.owner))

    def test_activate_for_owner_rejects_assigned_license(self):
        assign_license_to_member(self.owner, self.license_a.pk, self.member.id)
        with self.assertRaises(ValidationError):
            activate_license_for_owner(self.owner, self.license_a.pk)

    def test_owner_with_existing_active_license_still_has_access(self):
        """رگرسیون: مالک با لایسنس active قبلی همچنان دسترسی دارد."""
        self.license_a.status = 'active'
        self.license_a.save(update_fields=['status'])
        self.assertTrue(has_active_bot_license(self.owner))
        # تخصیص کلید دیگر به عضو نباید دسترسی مالک را بشکند
        assign_license_to_member(self.owner, self.license_b.pk, self.member.id)
        self.assertTrue(has_active_bot_license(self.owner))
        self.assertTrue(has_active_bot_license(self.member))

    def test_member_with_only_active_seat_still_has_access(self):
        """رگرسیون: عضو با فقط اسلات دستگاه فعال قبلی همچنان دسترسی دارد."""
        self.license_a.status = 'active'
        self.license_a.save(update_fields=['status'])
        activation = register_device_slot(
            self.owner, self.license_a.pk, 'HW-SEAT-REGRESSION-01',
        )
        activation.is_active = True
        activation.save(update_fields=['is_active'])
        assign_seat_to_member(self.owner, activation.pk, self.member.id)
        self.assertTrue(has_active_bot_license(self.member))
        # مسیر تخصیص کلید روی لایسنس دیگر نباید مسیر اسلات را خراب کند
        assign_license_to_member(self.owner, self.license_b.pk, self.member2.id)
        self.assertTrue(has_active_bot_license(self.member))

    def test_assigned_license_visible_in_device_lookup(self):
        assign_license_to_member(self.owner, self.license_a.pk, self.member.id)
        qs = _assigned_license_qs(self.member)
        self.assertTrue(qs.filter(pk=self.license_a.pk).exists())

    def test_assign_revoke_api_endpoints(self):
        self.client.login(username='agency_owner', password='pass1234')
        resp = self.client.post(reverse('license_assign_license'), {
            'license_id': self.license_a.pk,
            'member_id': self.member.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        self.license_a.refresh_from_db()
        self.assertEqual(self.license_a.assigned_user_id, self.member.id)

        resp = self.client.post(reverse('license_revoke_license'), {
            'license_id': self.license_a.pk,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        self.license_a.refresh_from_db()
        self.assertIsNone(self.license_a.assigned_user_id)

    def test_activate_for_owner_api(self):
        self.client.login(username='agency_owner', password='pass1234')
        resp = self.client.post(reverse('license_activate_for_owner'), {
            'license_id': self.license_c.pk,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        self.license_c.refresh_from_db()
        self.assertEqual(self.license_c.status, 'active')
        self.assertIsNone(self.license_c.assigned_user_id)

    def test_active_status_without_devices_is_available_for_pool(self):
        activate_license_for_owner(self.owner, self.license_a.pk)
        self.license_a.refresh_from_db()
        self.assertEqual(self.license_a.status, 'active')
        self.assertEqual(_allocation_state(self.license_a), 'available')

    def test_revoke_clears_member_devices_and_returns_to_pool(self):
        assign_license_to_member(self.owner, self.license_a.pk, self.member.id)
        LicenseActivation.objects.create(
            license=self.license_a,
            hardware_fingerprint='a' * 64,
            is_active=True,
        )
        revoke_license_assignment(self.owner, self.license_a.pk)
        self.license_a.refresh_from_db()
        self.assertEqual(_allocation_state(self.license_a), 'available')
        self.assertEqual(self.license_a.status, 'inactive')
        self.assertFalse(
            LicenseActivation.objects.filter(license=self.license_a, is_active=True).exists(),
        )

    def test_release_to_pool_after_device_use(self):
        LicenseActivation.objects.create(
            license=self.license_b,
            hardware_fingerprint='b' * 64,
            is_active=True,
        )
        self.assertEqual(_allocation_state(self.license_b), 'owner_active')
        release_license_to_pool(self.owner, self.license_b.pk)
        self.license_b.refresh_from_db()
        self.assertEqual(_allocation_state(self.license_b), 'available')
        self.assertEqual(self.license_b.status, 'inactive')
