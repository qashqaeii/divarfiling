"""تست‌های ظرفیت دعوت آژانس — invite capacity enforcement."""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.models import AgencyInvitation, CRMAgency, CRMAgencyMember
from workspace.services.agency_entitlement import get_subscription_for_agency, provision_subscription_from_paid_order
from workspace.services.agency_invitations import (
    AgencyInviteCapacityError,
    cancel_agency_invitation,
    create_agency_invitation,
    create_bulk_agency_invitations,
    get_agency_invite_capacity,
)
from workspace.services.agency_onboarding import create_or_link_agency
from workspace.services.agency_seats import assign_seat_to_member

User = get_user_model()


class InviteCapacityTestBase(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='Bot', slug=f'bot-cap-{uuid.uuid4().hex[:6]}',
            description='t', is_active=True,
        )
        self.agency_plan = LicensePlan.objects.create(
            product=self.product, name='Agency', plan_type='monthly',
            price=990_000, duration_days=30, max_activations=2,
            allow_bulk_purchase=True, min_quantity=2, max_quantity=25, is_active=True,
        )
        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        self.phones = [f'0915{base + i:07d}' for i in range(12)]
        self.owner = User.objects.create_user(username=self.phones[0], phone=self.phones[0], password='x')
        self.advisor = User.objects.create_user(username=self.phones[1], phone=self.phones[1], password='x')
        self.advisor2 = User.objects.create_user(username=self.phones[2], phone=self.phones[2], password='x')
        self.advisor3 = User.objects.create_user(username=self.phones[3], phone=self.phones[3], password='x')
        self.advisor4 = User.objects.create_user(username=self.phones[4], phone=self.phones[4], password='x')

    def _agency_order(self, qty=3):
        order = Order.objects.create(
            user=self.owner, product=self.product, plan=self.agency_plan,
            quantity=qty, amount=qty * 990_000, status='paid', paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order)
        return order

    def _setup_agency(self, qty=3):
        self._agency_order(qty=qty)
        self.agency = create_or_link_agency(self.owner, 'Capacity Agency')
        self.sub = get_subscription_for_agency(self.agency)
        CRMAgencyMember.objects.get_or_create(
            agency=self.agency, user=self.owner, defaults={'role': 'owner'},
        )
        return self.agency, self.sub


class InviteCapacityCalculationTests(InviteCapacityTestBase):
    def test_plan_three_empty_capacity(self):
        _, sub = self._setup_agency(qty=3)
        cap = get_agency_invite_capacity(self.agency, sub)
        self.assertEqual(cap['total'], 3)
        self.assertEqual(cap['invite_available'], 3)

    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_three_invites_ok_fourth_denied(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        for i in range(3):
            create_agency_invitation(self.owner, self.phones[5 + i], request=None)
        cap = get_agency_invite_capacity(self.agency, self.sub)
        self.assertEqual(cap['invite_available'], 0)
        with self.assertRaises(AgencyInviteCapacityError):
            create_agency_invitation(self.owner, self.phones[9], request=None)

    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_two_assigned_one_invite_ok_second_denied(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        member1 = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        member2 = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor2, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        licenses = list(License.objects.filter(agency_subscription=self.sub))
        assign_seat_to_member(self.owner, licenses[0].pk, self.advisor.pk)
        assign_seat_to_member(self.owner, licenses[1].pk, self.advisor2.pk)
        create_agency_invitation(self.owner, self.phones[5], request=None)
        cap = get_agency_invite_capacity(self.agency, self.sub)
        self.assertEqual(cap['invite_available'], 0)
        with self.assertRaises(AgencyInviteCapacityError):
            create_agency_invitation(self.owner, self.phones[6], request=None)

    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_two_assigned_one_pending_blocks_new(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor2, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        licenses = list(License.objects.filter(agency_subscription=self.sub))
        assign_seat_to_member(self.owner, licenses[0].pk, self.advisor.pk)
        assign_seat_to_member(self.owner, licenses[1].pk, self.advisor2.pk)
        create_agency_invitation(self.owner, self.phones[5], request=None)
        with self.assertRaises(AgencyInviteCapacityError):
            create_agency_invitation(self.owner, self.phones[6], request=None)

    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_cancelled_pending_frees_capacity(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        inv = create_agency_invitation(self.owner, self.phones[5], request=None)
        cancel_agency_invitation(self.owner, inv.pk)
        cap = get_agency_invite_capacity(self.agency, self.sub)
        self.assertEqual(cap['invite_available'], 3)

    def test_expired_pending_frees_capacity(self):
        self._setup_agency(qty=3)
        AgencyInvitation.objects.create(
            agency=self.agency, inviter=self.owner, phone=self.phones[5],
            role='advisor', token_hash=f'hash-{uuid.uuid4().hex}',
            status=AgencyInvitation.STATUS_PENDING,
            expires_at=timezone.now() - timedelta(hours=1),
        )
        cap = get_agency_invite_capacity(self.agency, self.sub)
        self.assertEqual(cap['invite_available'], 3)

    def test_declined_frees_capacity(self):
        self._setup_agency(qty=3)
        AgencyInvitation.objects.create(
            agency=self.agency, inviter=self.owner, phone=self.phones[5],
            role='advisor', token_hash=f'hash-{uuid.uuid4().hex}',
            status=AgencyInvitation.STATUS_DECLINED,
            expires_at=timezone.now() + timedelta(days=7),
        )
        cap = get_agency_invite_capacity(self.agency, self.sub)
        self.assertEqual(cap['invite_available'], 3)


class InviteCapacityValidationTests(InviteCapacityTestBase):
    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_invalid_phone_denied(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        with self.assertRaises(ValueError):
            create_agency_invitation(self.owner, '08123456789', request=None)
        with self.assertRaises(ValueError):
            create_agency_invitation(self.owner, '09123', request=None)

    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_duplicate_phone_denied(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        create_agency_invitation(self.owner, self.phones[5], request=None)
        with self.assertRaises(ValueError):
            create_agency_invitation(self.owner, self.phones[5], request=None)

    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_bulk_rejects_when_over_capacity(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        create_agency_invitation(self.owner, self.phones[5], request=None)
        create_agency_invitation(self.owner, self.phones[6], request=None)
        result = create_bulk_agency_invitations(
            self.owner, [self.phones[7], self.phones[8]], request=None,
        )
        self.assertTrue(result.get('capacity_error'))
        self.assertEqual(len(result['created']), 0)
        self.assertEqual(
            AgencyInvitation.objects.filter(agency=self.agency, status=AgencyInvitation.STATUS_PENDING).count(),
            2,
        )

    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_api_returns_409_on_capacity(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        for i in range(3):
            create_agency_invitation(self.owner, self.phones[5 + i], request=None)
        self.client.force_login(self.owner)
        resp = self.client.post(
            reverse('workspace:api_agency_invitations'),
            data='{"phone":"09120001111"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 409)
        data = resp.json()
        self.assertEqual(data.get('code'), 'agency_seat_capacity_reached')


class InviteCapacityConcurrencyTests(InviteCapacityTestBase):
    """Bulk boundary — no partial success when capacity exceeded."""

    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_bulk_at_exact_capacity_ok(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        result = create_bulk_agency_invitations(
            self.owner,
            [self.phones[5], self.phones[6], self.phones[7]],
            request=None,
        )
        self.assertEqual(len(result['created']), 3)
        self.assertEqual(
            AgencyInvitation.objects.filter(
                agency=self.agency, status=AgencyInvitation.STATUS_PENDING,
            ).count(),
            3,
        )

    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_sequential_invites_stop_at_capacity(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        for i in range(3):
            create_agency_invitation(self.owner, self.phones[5 + i], request=None)
        with self.assertRaises(AgencyInviteCapacityError):
            create_agency_invitation(self.owner, self.phones[8], request=None)
        self.assertEqual(
            AgencyInvitation.objects.filter(
                agency=self.agency, status=AgencyInvitation.STATUS_PENDING,
            ).count(),
            3,
        )
