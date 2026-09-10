"""تست‌های entitlement و دسترسی بخش آژانس."""
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from workspace.models import AgencySubscription, CRMAgency, CRMAgencyMember
from workspace.services.agency_entitlement import (
    can_access_agency_hub,
    can_manage_agency,
    has_active_agency_entitlement,
    provision_subscription_from_paid_order,
)

User = get_user_model()


class AgencyEntitlementTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='Bot', slug='bot-entitlement-test', description='test', is_active=True,
        )
        self.agency_plan = LicensePlan.objects.create(
            product=self.product,
            name='Agency Monthly',
            plan_type='monthly',
            price=990_000,
            duration_days=30,
            max_activations=2,
            allow_bulk_purchase=True,
            min_quantity=2,
            max_quantity=25,
            is_active=True,
        )
        self.personal_plan = LicensePlan.objects.create(
            product=self.product,
            name='Personal Monthly',
            plan_type='monthly',
            price=990_000,
            duration_days=30,
            max_activations=2,
            allow_bulk_purchase=False,
            is_active=True,
        )
        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        phones = [f'0912{base + i:07d}' for i in range(3)]
        self.owner = User.objects.create_user(username=phones[0], phone=phones[0], password='x')
        self.advisor = User.objects.create_user(username=phones[1], phone=phones[1], password='x')
        self.personal_user = User.objects.create_user(username=phones[2], phone=phones[2], password='x')

    def _paid_agency_order(self, user=None, qty=3):
        user = user or self.owner
        order = Order.objects.create(
            user=user,
            product=self.product,
            plan=self.agency_plan,
            quantity=qty,
            amount=qty * 990_000,
            status='paid',
            paid_at=timezone.now(),
        )
        from licenses.services.claim import issue_licenses_for_paid_order
        issue_licenses_for_paid_order(order)
        return order

    def test_personal_user_no_agency_access(self):
        order = Order.objects.create(
            user=self.personal_user,
            product=self.product,
            plan=self.personal_plan,
            quantity=1,
            amount=990_000,
            status='paid',
            paid_at=timezone.now(),
        )
        from licenses.services.claim import issue_licenses_for_paid_order
        issue_licenses_for_paid_order(order)
        self.assertFalse(has_active_agency_entitlement(self.personal_user))
        self.assertFalse(can_access_agency_hub(self.personal_user))

    def test_agency_owner_gets_entitlement(self):
        order = self._paid_agency_order()
        sub = provision_subscription_from_paid_order(order)
        self.assertIsNotNone(sub)
        self.assertEqual(sub.seat_count, 3)
        self.assertTrue(has_active_agency_entitlement(self.owner))
        self.assertTrue(can_manage_agency(self.owner))

    def test_provision_idempotent(self):
        order = self._paid_agency_order()
        sub1 = provision_subscription_from_paid_order(order)
        sub2 = provision_subscription_from_paid_order(order)
        self.assertEqual(sub1.pk, sub2.pk)

    def test_licenses_linked_to_subscription(self):
        order = self._paid_agency_order(qty=2)
        sub = provision_subscription_from_paid_order(order)
        linked = License.objects.filter(agency_subscription=sub).count()
        self.assertEqual(linked, 2)

    def test_team_url_denied_without_entitlement(self):
        self.client.force_login(self.personal_user)
        resp = self.client.get(reverse('workspace:crm_team'))
        self.assertEqual(resp.status_code, 302)

    def test_team_url_allowed_for_owner(self):
        order = self._paid_agency_order()
        provision_subscription_from_paid_order(order)
        agency = CRMAgency.objects.create(
            name='Test Agency', slug='test-agency', owner=self.owner, api_key='x' * 48,
        )
        CRMAgencyMember.objects.create(agency=agency, user=self.owner, role='owner')
        sub = AgencySubscription.objects.get(source_order=order)
        sub.agency = agency
        sub.save()
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('workspace:crm_team'))
        self.assertEqual(resp.status_code, 200)

    def test_expired_subscription_locked(self):
        order = self._paid_agency_order()
        sub = provision_subscription_from_paid_order(order)
        sub.expires_at = timezone.now() - timedelta(days=1)
        sub.save()
        from workspace.services.agency_entitlement import sync_expired_subscriptions
        sync_expired_subscriptions()
        sub.refresh_from_db()
        self.assertEqual(sub.status, AgencySubscription.STATUS_EXPIRED)
        self.assertFalse(has_active_agency_entitlement(self.owner))

    def test_api_denied_for_personal_user(self):
        self.client.force_login(self.personal_user)
        resp = self.client.get(reverse('workspace:api_crm_team_members'))
        self.assertEqual(resp.status_code, 403)
