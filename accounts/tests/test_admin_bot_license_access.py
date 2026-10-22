"""Regression: نمایش دسترسی لایسنس در پنل مدیریت — هم‌تراز workspace access."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.services.admin_users_management import list_users_management
from licenses.models import License, LicenseActivation
from licenses.tests.test_weekly_trial_campaign import _ensure_bot_monthly_plan
from shop.models import Order

User = get_user_model()


def _row_for_phone(phone: str):
    data = list_users_management(q=phone, page_size=10)
    for row in data['results']:
        if row['phone'] == phone:
            return row
    return None


class AdminBotLicenseAccessTests(TestCase):
    def setUp(self):
        self.product, self.plan = _ensure_bot_monthly_plan()

    def _create_user(self, phone: str) -> User:
        return User.objects.create_user(username=phone, password='x', phone=phone)

    def test_owner_active_license_shown(self):
        user = self._create_user('09130000001')
        order = Order.objects.create(
            user=user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='granted',
        )
        License.objects.create(
            order=order,
            license_key='OWNER-KEY-0001',
            plan=self.plan,
            status='active',
            expires_at=timezone.now() + timedelta(days=7),
        )
        row = _row_for_phone('09130000001')
        self.assertTrue(row['has_active_license'])
        self.assertEqual(row['license_access_kind'], 'owner')

    def test_assigned_license_member_shown(self):
        owner = self._create_user('09130000002')
        member = self._create_user('09130000003')
        order = Order.objects.create(
            user=owner,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
        )
        License.objects.create(
            order=order,
            license_key='ASSIGNED-KEY-01',
            plan=self.plan,
            status='active',
            assigned_user=member,
            expires_at=timezone.now() + timedelta(days=30),
        )
        row = _row_for_phone('09130000003')
        self.assertTrue(row['has_active_license'])
        self.assertEqual(row['license_access_kind'], 'assigned')

    def test_agency_seat_active_shown(self):
        owner = self._create_user('09130000004')
        member = self._create_user('09130000005')
        order = Order.objects.create(
            user=owner,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
        )
        lic = License.objects.create(
            order=order,
            license_key='SEAT-KEY-0001',
            plan=self.plan,
            status='active',
            expires_at=timezone.now() + timedelta(days=30),
        )
        LicenseActivation.objects.create(
            license=lic,
            assigned_user=member,
            is_active=True,
            hardware_fingerprint='a' * 64,
            label='Android',
            notes='device_type=mobile',
        )
        row = _row_for_phone('09130000005')
        self.assertTrue(row['has_active_license'])
        self.assertEqual(row['license_access_kind'], 'seat')

    def test_expired_license_not_counted(self):
        user = self._create_user('09130000006')
        order = Order.objects.create(
            user=user,
            product=self.product,
            plan=self.plan,
            amount=0,
            status='granted',
        )
        License.objects.create(
            order=order,
            license_key='EXPIRED-KEY-01',
            plan=self.plan,
            status='active',
            expires_at=timezone.now() - timedelta(days=1),
        )
        row = _row_for_phone('09130000006')
        self.assertFalse(row['has_active_license'])

    def test_invalid_order_status_not_counted(self):
        user = self._create_user('09130000007')
        order = Order.objects.create(
            user=user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='pending',
        )
        License.objects.create(
            order=order,
            license_key='PENDING-ORD-01',
            plan=self.plan,
            status='active',
            expires_at=timezone.now() + timedelta(days=7),
        )
        row = _row_for_phone('09130000007')
        self.assertFalse(row['has_active_license'])

    def test_paid_without_active_shows_pending(self):
        user = self._create_user('09130000008')
        Order.objects.create(
            user=user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='paid',
        )
        row = _row_for_phone('09130000008')
        self.assertFalse(row['has_active_license'])
        self.assertTrue(row['has_pending_bot_activation'])
