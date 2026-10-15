"""کارت آژانس در میزکار."""
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
from workspace.services.workspace_agency_home import (
    build_workspace_agency_panel,
    resolve_workspace_agency_nav_url,
)

User = get_user_model()


class WorkspaceAgencyHomePanelTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='Bot', slug=f'bot-wsh-{uuid.uuid4().hex[:6]}',
            description='t', is_active=True,
        )
        self.agency_plan = LicensePlan.objects.create(
            product=self.product, name='Agency', plan_type='monthly',
            price=990_000, duration_days=30, max_activations=2,
            allow_bulk_purchase=True, min_quantity=2, max_quantity=25, is_active=True,
        )
        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        self.owner_phone = f'0917{base:07d}'
        self.owner = User.objects.create_user(
            username=self.owner_phone, phone=self.owner_phone, password='x',
        )
        order = Order.objects.create(
            user=self.owner, product=self.product, plan=self.agency_plan,
            quantity=2, amount=1_980_000, status='paid', paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order)
        self.agency = create_or_link_agency(self.owner, 'Workspace Agency')
        sec_phone = f'0917{(base + 1) % 9_000_000:07d}'
        adv_phone = f'0917{(base + 2) % 9_000_000:07d}'
        self.secretary = User.objects.create_user(
            username=sec_phone, phone=sec_phone, password='x',
        )
        self.advisor = User.objects.create_user(
            username=adv_phone, phone=adv_phone, password='x',
        )
        CRMAgencyMember.objects.create(
            agency=self.agency, user=self.secretary, role='secretary', is_active=True,
        )
        CRMAgencyMember.objects.create(
            agency=self.agency, user=self.advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        lic = License.objects.filter(order__user=self.owner, assigned_user__isnull=True).first()
        if lic:
            assign_seat_to_member(self.owner, lic.pk, self.advisor.pk)

    def _assert_shortcuts_allowed(self, user):
        panel = build_workspace_agency_panel(user)
        self.assertIsNotNone(panel)
        self.client.force_login(user)
        enter = self.client.get(panel['enter_url'])
        self.assertIn(enter.status_code, (200, 302))
        if enter.status_code == 302:
            self.assertNotEqual(enter.url, panel['enter_url'])
        for item in panel.get('shortcuts', []):
            resp = self.client.get(item['url'])
            self.assertNotIn(resp.status_code, (403, 500))
            if resp.status_code == 302:
                self.assertNotEqual(resp.url, item['url'])

    def test_owner_gets_active_panel_with_shortcuts(self):
        panel = build_workspace_agency_panel(self.owner)
        self.assertIsNotNone(panel)
        self.assertEqual(panel['status'], 'active')
        self.assertTrue(panel['show_shortcuts'])
        self.assertGreaterEqual(len(panel['shortcuts']), 2)

    def test_home_renders_agency_panel_for_owner(self):
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('workspace:home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Workspace Agency')
        self.assertContains(resp, 'ورود به آژانس')

    def test_personal_user_without_agency_no_panel(self):
        lone_phone = f'0917{int(uuid.uuid4().hex[:7], 16) % 9_000_000:07d}'
        lone = User.objects.create_user(username=lone_phone, phone=lone_phone, password='x')
        self.assertIsNone(build_workspace_agency_panel(lone))
        self.client.force_login(lone)
        resp = self.client.get(reverse('workspace:home'))
        self.assertNotContains(resp, 'wsh-agency__card')

    def test_expired_owner_gets_locked_panel_without_shortcuts(self):
        AgencySubscription.objects.filter(agency=self.agency).update(
            expires_at=timezone.now() - timedelta(days=2),
        )
        panel = build_workspace_agency_panel(self.owner)
        self.assertEqual(panel['status'], 'locked')
        self.assertFalse(panel['show_shortcuts'])
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('workspace:home'))
        self.assertContains(resp, 'تمدید اشتراک')
        self.assertNotContains(resp, 'wsh-agency__link')
        locked = self.client.get(reverse('workspace:agency_locked'))
        self.assertEqual(locked.status_code, 200)

    def test_legacy_rbac_off_secretary_no_panel_without_hub_access(self):
        self.assertIsNone(build_workspace_agency_panel(self.secretary))
        self.client.force_login(self.secretary)
        resp = self.client.get(reverse('workspace:home'))
        self.assertNotContains(resp, 'wsh-agency__card')

    def test_secretary_hub_flag_enables_panel_without_rbac_v2(self):
        self.agency.feature_flags = {'agency_secretary_hub': True}
        self.agency.save(update_fields=['feature_flags'])
        panel = build_workspace_agency_panel(self.secretary)
        self.assertIsNotNone(panel)
        self.assertEqual(panel['enter_label'], 'ورود به آژانس')

    def test_rbac_v2_secretary_panel_and_shortcuts(self):
        self.agency.feature_flags = {'agency_rbac_v2': True}
        self.agency.save(update_fields=['feature_flags'])
        panel = build_workspace_agency_panel(self.secretary)
        self.assertEqual(panel['enter_label'], 'ورود به آژانس')
        self.assertTrue(any('میزکار پذیرش' in s['label'] for s in panel['shortcuts']))
        self._assert_shortcuts_allowed(self.secretary)
        self.client.force_login(self.secretary)
        resp = self.client.get(reverse('workspace:home'))
        self.assertContains(resp, 'پذیرش · عضو تیم')

    def test_advisor_sidebar_entry_points_to_member_hub(self):
        url = resolve_workspace_agency_nav_url(self.advisor)
        self.assertEqual(url, reverse('workspace:agency_advisor_member'))

    def test_advisor_panel_cta_and_shortcuts(self):
        panel = build_workspace_agency_panel(self.advisor)
        self.assertEqual(panel['enter_label'], 'میزکار مشاور')
        self._assert_shortcuts_allowed(self.advisor)
        self.client.force_login(self.advisor)
        resp = self.client.get(reverse('workspace:home'))
        self.assertContains(resp, 'میزکار مشاور')
