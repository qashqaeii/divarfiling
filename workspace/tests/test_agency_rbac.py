"""تست RBAC v2 آژانس — سازگاری و feature flag."""
import uuid

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.models import CRMAgencyMember
from workspace.services.agency_entitlement import can_access_agency_hub
from workspace.services.agency_onboarding import create_or_link_agency
from workspace.services.agency_rbac import (
    NAV_PROFILE_SECRETARY,
    PERM_CONTRACTS_VIEW_TEAM,
    PERM_DEALS_VIEW_TEAM,
    PERM_LICENSES_MANAGE,
    has_agency_permission,
    is_agency_rbac_v2_enabled,
    resolve_nav_profile,
)
from workspace.services.agency_seats import assign_seat_to_member
from licenses.models import License
from django.contrib.auth import get_user_model

User = get_user_model()


class AgencyRbacV2Tests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='Bot', slug=f'bot-rbac-{uuid.uuid4().hex[:6]}',
            description='t', is_active=True,
        )
        self.agency_plan = LicensePlan.objects.create(
            product=self.product, name='Agency', plan_type='monthly',
            price=990_000, duration_days=30, max_activations=2,
            allow_bulk_purchase=True, min_quantity=2, max_quantity=25, is_active=True,
        )
        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        self.owner_phone = f'0915{base:07d}'
        self.sec_phone = f'0915{base + 1:07d}'
        self.owner = User.objects.create_user(
            username=self.owner_phone, phone=self.owner_phone, password='x',
        )
        self.secretary = User.objects.create_user(
            username=self.sec_phone, phone=self.sec_phone, password='x',
        )
        order = Order.objects.create(
            user=self.owner, product=self.product, plan=self.agency_plan,
            quantity=2, amount=1_980_000, status='paid', paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order)
        self.agency = create_or_link_agency(self.owner, 'RBAC Agency')
        self.sec_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.secretary, role='secretary', is_active=True,
        )

    def test_rbac_v2_off_preserves_legacy_hub_access_for_secretary_without_seat(self):
        self.assertFalse(is_agency_rbac_v2_enabled(self.agency))
        self.assertFalse(can_access_agency_hub(self.secretary))

    def test_rbac_v2_on_secretary_hub_access_without_seat(self):
        self.agency.feature_flags = {'agency_rbac_v2': True}
        self.agency.save(update_fields=['feature_flags'])
        self.assertTrue(is_agency_rbac_v2_enabled(self.agency))
        self.assertTrue(can_access_agency_hub(self.secretary))
        self.assertEqual(resolve_nav_profile(self.secretary), NAV_PROFILE_SECRETARY)

    def test_secretary_denied_team_deals_when_rbac_v2(self):
        self.agency.feature_flags = {'agency_rbac_v2': True}
        self.agency.save(update_fields=['feature_flags'])
        self.assertFalse(has_agency_permission(self.secretary, PERM_DEALS_VIEW_TEAM))
        self.assertFalse(has_agency_permission(self.secretary, PERM_CONTRACTS_VIEW_TEAM))
        self.assertFalse(has_agency_permission(self.secretary, PERM_LICENSES_MANAGE))

    def test_owner_retains_licenses_when_rbac_v2(self):
        self.agency.feature_flags = {'agency_rbac_v2': True}
        self.agency.save(update_fields=['feature_flags'])
        self.assertTrue(has_agency_permission(self.owner, PERM_LICENSES_MANAGE))

    def test_secretary_dashboard_route(self):
        self.agency.feature_flags = {'agency_rbac_v2': True}
        self.agency.save(update_fields=['feature_flags'])
        self.client.force_login(self.secretary)
        resp = self.client.get(reverse('workspace:agency_hub_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'میزکار پذیرش')

    def test_invite_role_manager_rejected_when_rbac_v2(self):
        from workspace.services.agency_invitations import create_agency_invitation

        self.agency.feature_flags = {'agency_rbac_v2': True}
        self.agency.save(update_fields=['feature_flags'])
        with self.assertRaises(ValueError):
            create_agency_invitation(self.owner, '09129998877', 'manager')

    def test_secretary_denied_crm_deals_and_finance_urls(self):
        self.agency.feature_flags = {'agency_rbac_v2': True}
        self.agency.save(update_fields=['feature_flags'])
        self.client.force_login(self.secretary)
        self.assertEqual(self.client.get(reverse('workspace:crm_deals')).status_code, 403)
        self.assertEqual(self.client.get(reverse('workspace:crm_deals_finance')).status_code, 403)
        self.assertEqual(self.client.get(reverse('workspace:contracts_dashboard')).status_code, 403)

    def test_rbac_off_secretary_crm_deals_not_blocked_by_guard(self):
        self.client.force_login(self.secretary)
        resp = self.client.get(reverse('workspace:crm_deals'))
        self.assertIn(resp.status_code, (200, 302))

    def test_manager_legacy_template(self):
        mgr = User.objects.create_user(username=f'0915{int(uuid.uuid4().hex[:6], 16):06d}', password='x')
        CRMAgencyMember.objects.create(
            agency=self.agency, user=mgr, role='manager', is_active=True,
        )
        self.agency.feature_flags = {'agency_rbac_v2': True}
        self.agency.save(update_fields=['feature_flags'])
        self.assertTrue(has_agency_permission(mgr, PERM_DEALS_VIEW_TEAM))
        self.assertFalse(has_agency_permission(mgr, PERM_LICENSES_MANAGE))

    def test_secretary_blocked_deal_create_when_rbac_v2(self):
        self.agency.feature_flags = {'agency_rbac_v2': True}
        self.agency.save(update_fields=['feature_flags'])
        self.client.force_login(self.secretary)
        url = reverse('workspace:crm_deal_create')
        resp = self.client.post(url, {})
        self.assertEqual(resp.status_code, 403)

    def test_advisor_finance_dashboard_allowed_when_rbac_v2(self):
        from workspace.services.agency_rbac import serialize_permissions_for_api

        adv_phone = f'0915{int(uuid.uuid4().hex[:7], 16) % 9_000_000:07d}'
        advisor = User.objects.create_user(username=adv_phone, phone=adv_phone, password='x')
        adv_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        lic = License.objects.filter(
            order__user=self.owner, assigned_user__isnull=True,
        ).first()
        if lic:
            assign_seat_to_member(self.owner, lic.pk, advisor.pk)
        self.agency.feature_flags = {'agency_rbac_v2': True}
        self.agency.save(update_fields=['feature_flags'])
        payload = serialize_permissions_for_api(advisor)
        self.assertTrue(payload['capabilities']['can_view_finance'])
        self.client.force_login(advisor)
        self.assertEqual(
            self.client.get(reverse('workspace:crm_deals_finance')).status_code,
            200,
        )

    def test_inactive_member_denied_hub_when_rbac_v2(self):
        self.agency.feature_flags = {'agency_rbac_v2': True}
        self.agency.save(update_fields=['feature_flags'])
        self.sec_member.is_active = False
        self.sec_member.save(update_fields=['is_active'])
        self.assertFalse(can_access_agency_hub(self.secretary))
