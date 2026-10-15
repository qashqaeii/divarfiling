"""دعوت عضو با نقش منشی/مشاور — مستقل از RBAC v2 و ظرفیت صندلی."""
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from licenses.models import License
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.constants import AGENCY_MAX_SECRETARIES_PER_AGENCY, AGENCY_ROLE_SECRETARY
from workspace.models import AgencyInvitation, CRMAgencyMember
from workspace.services.agency_entitlement import can_access_agency_hub, get_subscription_for_agency
from workspace.services.agency_invitations import (
    AgencyInviteCapacityError,
    accept_agency_invitation,
    create_agency_invitation,
    get_agency_invite_capacity,
)
from workspace.services.agency_onboarding import create_or_link_agency
from workspace.services.agency_seats import assign_seat_to_member
from workspace.services.crm_agency import update_member_role

User = get_user_model()


@override_settings(SITE_URL='https://divarfiling.ir')
class AgencyInviteRolesTestBase(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='Bot', slug=f'bot-inv-{uuid.uuid4().hex[:6]}',
            description='t', is_active=True,
        )
        self.agency_plan = LicensePlan.objects.create(
            product=self.product, name='Agency', plan_type='monthly',
            price=990_000, duration_days=30, max_activations=2,
            allow_bulk_purchase=True, min_quantity=2, max_quantity=25, is_active=True,
        )
        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        self.phones = [f'0916{base + i:07d}' for i in range(20)]
        self.owner = User.objects.create_user(
            username=self.phones[0], phone=self.phones[0], password='x',
        )

    def _setup_agency(self, qty=2):
        order = Order.objects.create(
            user=self.owner, product=self.product, plan=self.agency_plan,
            quantity=qty, amount=qty * 990_000, status='paid', paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order)
        self.agency = create_or_link_agency(self.owner, 'Invite Roles Agency')
        self.sub = get_subscription_for_agency(self.agency)
        CRMAgencyMember.objects.get_or_create(
            agency=self.agency, user=self.owner, defaults={'role': 'owner'},
        )
        return self.agency, self.sub


class AgencyInviteRoleTests(AgencyInviteRolesTestBase):
    @patch('workspace.services.agency_invitations.send_pattern_sms')
    def test_invite_secretary_with_rbac_off(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=2)
        for i in range(2):
            create_agency_invitation(
                self.owner, self.phones[5 + i], role='advisor', request=None,
            )
        inv = create_agency_invitation(
            self.owner, self.phones[8], role='secretary', request=None,
        )
        self.assertEqual(inv.role, AGENCY_ROLE_SECRETARY)

    @patch('workspace.services.agency_invitations.send_pattern_sms')
    def test_invite_advisor_blocked_when_seats_full(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=2)
        create_agency_invitation(self.owner, self.phones[5], request=None)
        create_agency_invitation(self.owner, self.phones[6], request=None)
        with self.assertRaises(AgencyInviteCapacityError):
            create_agency_invitation(self.owner, self.phones[7], role='advisor', request=None)

    @patch('workspace.services.agency_invitations.send_pattern_sms')
    def test_invite_secretary_when_advisor_capacity_full(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=2)
        create_agency_invitation(self.owner, self.phones[5], request=None)
        create_agency_invitation(self.owner, self.phones[6], request=None)
        inv = create_agency_invitation(
            self.owner, self.phones[7], role='secretary', request=None,
        )
        self.assertEqual(inv.role, AGENCY_ROLE_SECRETARY)

    @patch('workspace.services.agency_invitations.send_pattern_sms')
    def test_accept_invitation_stores_role(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        inv = create_agency_invitation(
            self.owner, self.phones[9], role='secretary', request=None,
        )
        invitee = User.objects.create_user(
            username=self.phones[9], phone=self.phones[9], password='x',
        )
        member = accept_agency_invitation(inv, invitee, consent_acknowledged=True)
        self.assertEqual(member.role, AGENCY_ROLE_SECRETARY)

    @patch('workspace.services.agency_invitations.send_pattern_sms')
    def test_secretary_not_counted_in_advisor_without_seat(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=2)
        sec = User.objects.create_user(username=self.phones[5], phone=self.phones[5], password='x')
        CRMAgencyMember.objects.create(
            agency=self.agency, user=sec, role='secretary', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        cap = get_agency_invite_capacity(self.agency, self.sub)
        self.assertEqual(cap['invite_available'], 2)

    @patch('workspace.services.agency_invitations.send_pattern_sms')
    def test_invalid_invite_role_rejected(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        with self.assertRaises(ValueError):
            create_agency_invitation(self.owner, self.phones[5], role='owner', request=None)

    @patch('workspace.services.agency_invitations.send_pattern_sms')
    def test_api_invite_secretary_rbac_off(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        self.client.force_login(self.owner)
        resp = self.client.post(
            reverse('workspace:api_agency_invitations'),
            data='{"phone":"09120002222","role":"secretary"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        inv = AgencyInvitation.objects.get(phone='09120002222')
        self.assertEqual(inv.role, AGENCY_ROLE_SECRETARY)

    def test_role_change_secretary_to_advisor(self):
        self._setup_agency(qty=3)
        sec = User.objects.create_user(username=self.phones[5], phone=self.phones[5], password='x')
        member = CRMAgencyMember.objects.create(
            agency=self.agency, user=sec, role='secretary', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        updated = update_member_role(self.owner, member.pk, 'advisor')
        self.assertEqual(updated.role, 'advisor')

    def test_role_change_advisor_with_seat_to_secretary_keeps_seat(self):
        self._setup_agency(qty=3)
        adv = User.objects.create_user(username=self.phones[5], phone=self.phones[5], password='x')
        member = CRMAgencyMember.objects.create(
            agency=self.agency, user=adv, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        lic = License.objects.filter(agency_subscription=self.sub, assigned_user__isnull=True).first()
        assign_seat_to_member(self.owner, lic.pk, adv.pk)
        update_member_role(self.owner, member.pk, 'secretary')
        lic.refresh_from_db()
        self.assertEqual(lic.assigned_user_id, adv.pk)

    @patch('workspace.services.agency_invitations.send_pattern_sms')
    def test_secretary_hub_access_with_flag_not_rbac(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        self.agency.feature_flags = {'agency_secretary_hub': True}
        self.agency.save(update_fields=['feature_flags'])
        sec = User.objects.create_user(username=self.phones[5], phone=self.phones[5], password='x')
        CRMAgencyMember.objects.create(
            agency=self.agency, user=sec, role='secretary', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        self.assertTrue(can_access_agency_hub(sec))
        self.client.force_login(sec)
        resp = self.client.get(reverse('workspace:agency_hub_dashboard'))
        self.assertEqual(resp.status_code, 200)

    @patch('workspace.services.agency_invitations.send_pattern_sms')
    def test_secretary_denied_sensitive_hub_without_rbac_v2(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        self.agency.feature_flags = {'agency_secretary_hub': True}
        self.agency.save(update_fields=['feature_flags'])
        sec = User.objects.create_user(username=self.phones[5], phone=self.phones[5], password='x')
        CRMAgencyMember.objects.create(
            agency=self.agency, user=sec, role='secretary', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        self.client.force_login(sec)
        resp = self.client.get(reverse('workspace:agency_hub_licenses'))
        self.assertIn(resp.status_code, (302, 403))

    @patch('workspace.services.agency_invitations.send_pattern_sms')
    def test_secretary_capacity_limit(self, mock_sms):
        mock_sms.return_value = None
        self._setup_agency(qty=3)
        for i in range(AGENCY_MAX_SECRETARIES_PER_AGENCY):
            create_agency_invitation(
                self.owner, self.phones[10 + i], role='secretary', request=None,
            )
        with self.assertRaises(AgencyInviteCapacityError) as ctx:
            create_agency_invitation(
                self.owner, self.phones[19], role='secretary', request=None,
            )
        self.assertEqual(ctx.exception.code, 'agency_secretary_capacity_reached')
