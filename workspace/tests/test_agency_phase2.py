"""تست‌های فاز ۲ — onboarding، دعوت، Seat، redirect."""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.models import AgencyInvitation, AgencySubscription, CRMAgency, CRMAgencyMember
from workspace.services.agency_entitlement import (
    can_access_agency_hub,
    get_subscription_for_agency,
    has_assigned_agency_seat,
    is_agency_management_locked,
    provision_subscription_from_paid_order,
    resolve_post_agency_payment_redirect,
    sync_agency_management_status,
)
from workspace.services.agency_invitations import (
    accept_agency_invitation,
    cancel_agency_invitation,
    create_agency_invitation,
    get_invitation_by_token,
    resend_invitation_sms,
)
from workspace.services.agency_onboarding import create_or_link_agency
from workspace.services.agency_seats import assign_seat_to_member, unassign_seat
from workspace.models import AgencyLicenseAssignmentLog

User = get_user_model()


class AgencyPhase2TestBase(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='Bot', slug=f'bot-p2-{uuid.uuid4().hex[:6]}',
            description='t', is_active=True,
        )
        self.agency_plan = LicensePlan.objects.create(
            product=self.product, name='Agency', plan_type='monthly',
            price=990_000, duration_days=30, max_activations=2,
            allow_bulk_purchase=True, min_quantity=2, max_quantity=25, is_active=True,
        )
        self.personal_plan = LicensePlan.objects.create(
            product=self.product, name='Personal', plan_type='monthly',
            price=990_000, duration_days=30, max_activations=2,
            allow_bulk_purchase=False, is_active=True,
        )
        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        self.phones = [f'0913{base + i:07d}' for i in range(4)]
        self.owner = User.objects.create_user(username=self.phones[0], phone=self.phones[0], password='x')
        self.advisor = User.objects.create_user(username=self.phones[1], phone=self.phones[1], password='x')
        self.other = User.objects.create_user(username=self.phones[2], phone=self.phones[2], password='x')

    def _agency_order(self, user=None, qty=2):
        user = user or self.owner
        order = Order.objects.create(
            user=user, product=self.product, plan=self.agency_plan,
            quantity=qty, amount=qty * 990_000, status='paid', paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order)
        return order


class ArchitectureTests(AgencyPhase2TestBase):
    def test_management_status_not_source_of_truth(self):
        order = self._agency_order()
        sub = provision_subscription_from_paid_order(order)
        agency = CRMAgency.objects.create(
            name='A', slug=f'a-{uuid.uuid4().hex[:6]}', owner=self.owner, api_key='k' * 48,
            management_status='locked',
        )
        sub.agency = agency
        sub.save()
        self.assertFalse(is_agency_management_locked(agency))
        sync_agency_management_status(agency)
        agency.refresh_from_db()
        self.assertEqual(agency.management_status, 'active')

    def test_advisor_without_seat_no_hub_access(self):
        order = self._agency_order()
        sub = provision_subscription_from_paid_order(order)
        agency = create_or_link_agency(self.owner, 'Test Agency')
        CRMAgencyMember.objects.create(
            agency=agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        self.assertFalse(has_assigned_agency_seat(self.advisor))
        self.assertFalse(can_access_agency_hub(self.advisor))

    def test_advisor_with_seat_has_hub_access(self):
        order = self._agency_order()
        sub = provision_subscription_from_paid_order(order)
        agency = create_or_link_agency(self.owner, 'Test Agency')
        member = CRMAgencyMember.objects.create(
            agency=agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(), consent_version='2026-03-01',
        )
        lic = License.objects.filter(agency_subscription=sub).first()
        assign_seat_to_member(self.owner, lic.pk, self.advisor.pk)
        self.assertTrue(has_assigned_agency_seat(self.advisor))
        self.assertTrue(can_access_agency_hub(self.advisor))


class PostPurchaseTests(AgencyPhase2TestBase):
    def test_agency_purchase_redirect_onboarding(self):
        order = self._agency_order()
        url = resolve_post_agency_payment_redirect(order)
        self.assertIn('onboarding', url)

    def test_agency_with_agency_redirect_members(self):
        order = self._agency_order()
        agency = create_or_link_agency(self.owner, 'My Agency')
        url = resolve_post_agency_payment_redirect(order)
        self.assertIn('/crm/agency/advisors', url)

    def test_personal_no_agency_redirect(self):
        order = Order.objects.create(
            user=self.owner, product=self.product, plan=self.personal_plan,
            quantity=1, amount=990_000, status='paid', paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order)
        self.assertIsNone(resolve_post_agency_payment_redirect(order))

    def test_fulfillment_idempotent_subscription(self):
        order = self._agency_order()
        s1 = provision_subscription_from_paid_order(order)
        s2 = provision_subscription_from_paid_order(order)
        self.assertEqual(s1.pk, s2.pk)


class InvitationTests(AgencyPhase2TestBase):
    def setUp(self):
        super().setUp()
        self._agency_order()
        self.agency = create_or_link_agency(self.owner, 'Invite Agency')
        CRMAgencyMember.objects.get_or_create(
            agency=self.agency, user=self.owner, defaults={'role': 'owner'},
        )

    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_create_invitation_and_sms(self, mock_sms):
        mock_sms.return_value = None
        inv = create_agency_invitation(self.owner, self.phones[1], request=None)
        self.assertEqual(inv.status, AgencyInvitation.STATUS_PENDING)
        mock_sms.assert_called_once()

    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_sms_failure_keeps_invitation(self, mock_sms):
        from accounts.services.sms import SmsError
        mock_sms.side_effect = SmsError('fail')
        inv = create_agency_invitation(self.owner, self.phones[1], request=None)
        self.assertTrue(AgencyInvitation.objects.filter(pk=inv.pk).exists())
        self.assertEqual(inv.sms_metadata.get('last_status'), 'failed')

    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_accept_creates_membership_with_consent(self, mock_sms):
        mock_sms.return_value = None
        inv, raw = None, None
        from workspace.services.agency_invitations import _generate_invite_token
        raw, th = _generate_invite_token()
        inv = AgencyInvitation.objects.create(
            agency=self.agency, inviter=self.owner, phone=self.phones[1],
            role='advisor', token_hash=th,
            expires_at=timezone.now() + timedelta(days=7),
        )
        member = accept_agency_invitation(inv, self.advisor, consent_acknowledged=True)
        self.assertTrue(member.data_visibility_consent_at)
        self.assertTrue(member.is_active)
        inv.refresh_from_db()
        self.assertEqual(inv.status, AgencyInvitation.STATUS_ACCEPTED)

    def test_wrong_phone_cannot_accept(self):
        from contracts.services.tokens import generate_bearer_token
        raw, th = generate_bearer_token()
        inv = AgencyInvitation.objects.create(
            agency=self.agency, inviter=self.owner, phone=self.phones[1],
            role='advisor', token_hash=th,
            expires_at=timezone.now() + timedelta(days=7),
        )
        with self.assertRaises(ValueError):
            accept_agency_invitation(inv, self.other, consent_acknowledged=True)

    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_expired_subscription_blocks_accept(self, mock_sms):
        sub = get_subscription_for_agency(self.agency)
        sub.expires_at = timezone.now() - timedelta(hours=1)
        sub.save()
        from contracts.services.tokens import generate_bearer_token
        raw, th = generate_bearer_token()
        inv = AgencyInvitation.objects.create(
            agency=self.agency, inviter=self.owner, phone=self.phones[1],
            role='advisor', token_hash=th,
            expires_at=timezone.now() + timedelta(days=7),
        )
        with self.assertRaises(ValueError):
            accept_agency_invitation(inv, self.advisor, consent_acknowledged=True)


class SeatTests(AgencyPhase2TestBase):
    def setUp(self):
        super().setUp()
        self.order = self._agency_order(qty=2)
        self.sub = provision_subscription_from_paid_order(self.order)
        self.agency = create_or_link_agency(self.owner, 'Seat Agency')
        self.member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(), consent_version='2026-03-01',
        )

    def test_assign_and_unassign_logs(self):
        lic = License.objects.filter(agency_subscription=self.sub).first()
        assign_seat_to_member(self.owner, lic.pk, self.advisor.pk)
        self.assertEqual(
            AgencyLicenseAssignmentLog.objects.filter(action='assign').count(), 1,
        )
        unassign_seat(self.owner, lic.pk)
        self.assertEqual(
            AgencyLicenseAssignmentLog.objects.filter(action='unassign').count(), 1,
        )

    def test_double_assignment_denied(self):
        licenses = list(License.objects.filter(agency_subscription=self.sub))
        assign_seat_to_member(self.owner, licenses[0].pk, self.advisor.pk)
        with self.assertRaises(Exception):
            assign_seat_to_member(self.owner, licenses[1].pk, self.advisor.pk)


class SecurityTests(AgencyPhase2TestBase):
    @patch('workspace.services.agency_invitations.send_simple_sms')
    def test_advisor_cannot_create_invitation(self, mock_sms):
        self._agency_order()
        agency = create_or_link_agency(self.owner, 'Sec Agency')
        sub = get_subscription_for_agency(agency)
        lic = License.objects.filter(agency_subscription=sub).first()
        CRMAgencyMember.objects.create(
            agency=agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        assign_seat_to_member(self.owner, lic.pk, self.advisor.pk)
        with self.assertRaises(ValueError):
            create_agency_invitation(self.advisor, '09138887777')

    def test_personal_user_api_denied(self):
        self.client.force_login(self.other)
        resp = self.client.post(
            reverse('workspace:api_agency_invitations'),
            data='{"phone":"09120001111"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)
