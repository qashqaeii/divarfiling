"""تست مدیریت اسلات لایسنس و دسترسی تیم."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from licenses.models import License, LicenseActivation
from licenses.services.management import assign_seat_to_member, register_device_slot, remove_device_slot
from shop.models import LicensePlan, Order, Product
from workspace.models import CRMAgency, CRMAgencyMember
from workspace.services.access import has_active_bot_license

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
