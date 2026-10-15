"""HTTP — اشتراک آژانس منقضی و مسیرهای Hub."""
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.models import AgencySubscription, CRMAgencyMember
from workspace.services.agency_onboarding import create_or_link_agency
from workspace.services.agency_seats import assign_seat_to_member

User = get_user_model()


class AgencyHubExpiredSubscriptionHTTPTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='Bot', slug=f'bot-exp-{uuid.uuid4().hex[:6]}',
            description='t', is_active=True,
        )
        self.agency_plan = LicensePlan.objects.create(
            product=self.product, name='Agency', plan_type='monthly',
            price=990_000, duration_days=30, max_activations=2,
            allow_bulk_purchase=True, min_quantity=2, max_quantity=25, is_active=True,
        )
        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        self.owner = User.objects.create_user(
            username=f'0918{base:07d}', phone=f'0918{base:07d}', password='x',
        )
        self.sec = User.objects.create_user(
            username=f'0918{base + 1:07d}', phone=f'0918{base + 1:07d}', password='x',
        )
        self.advisor = User.objects.create_user(
            username=f'0918{base + 2:07d}', phone=f'0918{base + 2:07d}', password='x',
        )
        order = Order.objects.create(
            user=self.owner, product=self.product, plan=self.agency_plan,
            quantity=2, amount=1_980_000, status='paid', paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order)
        self.agency = create_or_link_agency(self.owner, 'Expired Sub Agency')
        CRMAgencyMember.objects.create(
            agency=self.agency, user=self.sec, role='secretary', is_active=True,
        )
        adv_m = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        lic = License.objects.filter(order__user=self.owner, assigned_user__isnull=True).first()
        if lic:
            assign_seat_to_member(self.owner, lic.pk, self.advisor.pk)
        self.agency.feature_flags = {'agency_rbac_v2': True}
        self.agency.save(update_fields=['feature_flags'])
        AgencySubscription.objects.filter(agency=self.agency).update(
            expires_at=timezone.now() - timedelta(days=1),
        )

    def test_owner_hub_dashboard_redirects_to_locked(self):
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('workspace:agency_hub_dashboard'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('workspace:agency_locked'))

    def test_secretary_denied_hub_when_subscription_expired(self):
        self.client.force_login(self.sec)
        resp = self.client.get(reverse('workspace:agency_hub_dashboard'))
        self.assertIn(resp.status_code, (302, 403))
        if resp.status_code == 302:
            self.assertNotEqual(resp.url, reverse('workspace:agency_hub_dashboard'))

    def test_advisor_denied_team_hub_when_subscription_expired(self):
        self.client.force_login(self.advisor)
        resp = self.client.get(reverse('workspace:agency_hub_dashboard'))
        self.assertIn(resp.status_code, (302, 403))

    def test_owner_licenses_route_redirects_when_expired(self):
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('workspace:agency_hub_licenses'))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('workspace:agency_locked'))
