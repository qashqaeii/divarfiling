"""تست‌های فاز ۳ — Data Scope، Advisor 360، Export، IDOR."""
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.models import Contract
from licenses.models import License
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.models import (
    AgencyActivityEvent,
    CRMAgency,
    CRMAgencyMember,
    CRMDeal,
    CRMProperty,
    Customer,
    Dataset,
)
from workspace.services.agency_data_scope import (
    AgencyDataScopeError,
    get_member_contacts_qs,
    get_member_contracts_qs,
    get_member_deals_qs,
    get_member_filing_qs,
    get_member_properties_qs,
    resolve_visible_agency_member,
)
from workspace.services.agency_exports import export_member_data
from workspace.services.agency_onboarding import create_or_link_agency
from workspace.services.agency_seats import assign_seat_to_member

User = get_user_model()


class AgencyPhase3Base(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='Bot', slug=f'bot-p3-{uuid.uuid4().hex[:6]}',
            description='t', is_active=True,
        )
        self.agency_plan = LicensePlan.objects.create(
            product=self.product, name='Agency', plan_type='monthly',
            price=990_000, duration_days=30, max_activations=2,
            allow_bulk_purchase=True, min_quantity=2, max_quantity=25, is_active=True,
        )
        base = int(uuid.uuid4().hex[:8], 16) % 9_000_000
        self.phones = [f'0914{base + i:07d}' for i in range(6)]
        self.owner_a = User.objects.create_user(username=self.phones[0], phone=self.phones[0], password='x')
        self.advisor_a = User.objects.create_user(username=self.phones[1], phone=self.phones[1], password='x')
        self.owner_b = User.objects.create_user(username=self.phones[2], phone=self.phones[2], password='x')
        self.advisor_b = User.objects.create_user(username=self.phones[3], phone=self.phones[3], password='x')
        self.personal = User.objects.create_user(username=self.phones[4], phone=self.phones[4], password='x')

        for owner in (self.owner_a, self.owner_b):
            order = Order.objects.create(
                user=owner, product=self.product, plan=self.agency_plan,
                quantity=2, amount=1_980_000, status='paid', paid_at=timezone.now(),
            )
            fulfill_order_after_payment(order)

        self.agency_a = create_or_link_agency(self.owner_a, 'Agency A')
        self.agency_b = create_or_link_agency(self.owner_b, 'Agency B')
        self.member_a = CRMAgencyMember.objects.create(
            agency=self.agency_a, user=self.advisor_a, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(), consent_version='2026-03-01',
        )
        self.member_b = CRMAgencyMember.objects.create(
            agency=self.agency_b, user=self.advisor_b, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(), consent_version='2026-03-01',
        )
        sub_a = License.objects.filter(order__user=self.owner_a).first().agency_subscription
        lic_a = License.objects.filter(agency_subscription=sub_a).first()
        assign_seat_to_member(self.owner_a, lic_a.pk, self.advisor_a.pk)

        self.contact_a = Customer.objects.create(
            user=self.advisor_a, agency=self.agency_a, name='Contact A', phone='09111111111',
        )
        self.contact_b = Customer.objects.create(
            user=self.advisor_b, agency=self.agency_b, name='Contact B', phone='09222222222',
        )
        self.property_a = CRMProperty.objects.create(
            user=self.advisor_a, agency=self.agency_a, title='Prop A',
        )
        self.deal_a = CRMDeal.objects.create(
            user=self.advisor_a, agency=self.agency_a, customer=self.contact_a, title='Deal A',
        )
        self.dataset_a = Dataset.objects.create(
            user=self.advisor_a, name='DS A', original_filename='a.csv', file_format='csv',
        )


class DataScopeTests(AgencyPhase3Base):
    def test_owner_sees_own_agency_advisor(self):
        m = resolve_visible_agency_member(self.owner_a, self.member_a.pk)
        self.assertEqual(m.pk, self.member_a.pk)

    def test_owner_cannot_see_other_agency_advisor(self):
        with self.assertRaises(AgencyDataScopeError):
            resolve_visible_agency_member(self.owner_a, self.member_b.pk)

    def test_personal_user_denied(self):
        with self.assertRaises(AgencyDataScopeError):
            resolve_visible_agency_member(self.personal, self.member_a.pk)

    def test_advisor_denied(self):
        with self.assertRaises(AgencyDataScopeError):
            resolve_visible_agency_member(self.advisor_a, self.member_a.pk)

    def test_no_consent_denied(self):
        self.member_a.data_visibility_consent_at = None
        self.member_a.save()
        with self.assertRaises(AgencyDataScopeError):
            resolve_visible_agency_member(self.owner_a, self.member_a.pk)

    def test_inactive_membership_denied(self):
        self.member_a.is_active = False
        self.member_a.save()
        with self.assertRaises(AgencyDataScopeError):
            resolve_visible_agency_member(self.owner_a, self.member_a.pk)

    def test_expired_subscription_denied(self):
        from workspace.models import AgencySubscription
        sub = AgencySubscription.objects.filter(owner=self.owner_a).first()
        sub.expires_at = timezone.now() - timedelta(hours=1)
        sub.save()
        with self.assertRaises(AgencyDataScopeError):
            resolve_visible_agency_member(self.owner_a, self.member_a.pk)


class ContactsScopeTests(AgencyPhase3Base):
    def test_own_agency_contacts_visible(self):
        qs = get_member_contacts_qs(self.owner_a, self.member_a)
        self.assertIn(self.contact_a, list(qs))

    def test_other_advisor_contacts_excluded(self):
        qs = get_member_contacts_qs(self.owner_a, self.member_a)
        self.assertNotIn(self.contact_b, list(qs))

    def test_search_scoped(self):
        qs = get_member_contacts_qs(self.owner_a, self.member_a, search='Contact A')
        self.assertEqual(qs.count(), 1)


class PropertiesScopeTests(AgencyPhase3Base):
    def test_scoped_correctly(self):
        qs = get_member_properties_qs(self.owner_a, self.member_a)
        self.assertIn(self.property_a, list(qs))

    def test_foreign_excluded(self):
        CRMProperty.objects.create(user=self.advisor_b, agency=self.agency_b, title='Foreign')
        qs = get_member_properties_qs(self.owner_a, self.member_a)
        self.assertEqual(qs.filter(title='Foreign').count(), 0)


class FilingScopeTests(AgencyPhase3Base):
    def test_dataset_scoped(self):
        qs = get_member_filing_qs(self.owner_a, self.member_a)
        self.assertIn(self.dataset_a, list(qs))


class DealsScopeTests(AgencyPhase3Base):
    def test_deals_scoped(self):
        qs = get_member_deals_qs(self.owner_a, self.member_a)
        self.assertIn(self.deal_a, list(qs))


class ContractsScopeTests(AgencyPhase3Base):
    def _make_contract(self, **kwargs):
        from contracts.services.tokens import generate_bearer_token
        _, th = generate_bearer_token()
        defaults = {
            'contract_type': 'lease',
            'internal_number': f'C-{uuid.uuid4().hex[:8]}',
            'verification_token_hash': th,
            'title': 'Test Contract',
        }
        defaults.update(kwargs)
        return Contract.objects.create(**defaults)

    def test_dashboard_contracts_qs_excludes_colleague_standalone(self):
        """داشبورد قراردادها — قرارداد مستقل هم‌تیمی در لیست من نیاید."""
        from contracts.services.scope import contracts_qs

        colleague = self._make_contract(
            user=self.advisor_a,
            agency=self.agency_a,
            deal=None,
        )
        self.assertIn(colleague, list(contracts_qs(self.advisor_a)))
        self.assertNotIn(colleague, list(contracts_qs(self.owner_a)))

    def test_dashboard_contracts_qs_excludes_colleague_deal_contract(self):
        from contracts.services.scope import contracts_qs

        colleague = self._make_contract(
            user=self.advisor_a,
            agency=self.agency_a,
            deal=self.deal_a,
        )
        self.assertIn(colleague, list(contracts_qs(self.advisor_a)))
        self.assertNotIn(colleague, list(contracts_qs(self.owner_a)))

    def test_owner_without_seat_can_read_advisor_contract(self):
        from contracts.services.tokens import generate_bearer_token
        raw, th = generate_bearer_token()
        contract = Contract.objects.create(
            user=self.advisor_a,
            agency=self.agency_a,
            deal=self.deal_a,
            contract_type='lease',
            internal_number=f'C-{uuid.uuid4().hex[:8]}',
            verification_token_hash=th,
            title='Advisor Contract',
        )
        qs = get_member_contracts_qs(self.owner_a, self.member_a)
        self.assertIn(contract, list(qs))

    def test_cross_agency_contract_denied(self):
        from contracts.services.tokens import generate_bearer_token
        raw, th = generate_bearer_token()
        deal_b = CRMDeal.objects.create(
            user=self.advisor_b, agency=self.agency_b,
            customer=self.contact_b, title='Deal B',
        )
        contract_b = Contract.objects.create(
            user=self.advisor_b, agency=self.agency_b, deal=deal_b,
            contract_type='lease', internal_number=f'C-{uuid.uuid4().hex[:8]}',
            verification_token_hash=th,
        )
        qs = get_member_contracts_qs(self.owner_a, self.member_a)
        self.assertNotIn(contract_b, list(qs))


class ExportTests(AgencyPhase3Base):
    def test_csv_export_and_audit(self):
        resp = export_member_data(self.owner_a, self.member_a.pk, 'contacts', 'csv')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertTrue(
            AgencyActivityEvent.objects.filter(
                agency=self.agency_a, event_type='advisor_data_export',
            ).exists()
        )

    def test_xlsx_export(self):
        resp = export_member_data(self.owner_a, self.member_a.pk, 'contacts', 'xlsx')
        self.assertEqual(resp.status_code, 200)

    def test_cross_agency_export_denied(self):
        with self.assertRaises(AgencyDataScopeError):
            export_member_data(self.owner_a, self.member_b.pk, 'contacts', 'csv')

    def test_advisor_export_denied(self):
        with self.assertRaises(AgencyDataScopeError):
            export_member_data(self.advisor_a, self.member_a.pk, 'contacts', 'csv')


class MembershipLifecycleTests(AgencyPhase3Base):
    def test_removed_advisor_loses_visibility(self):
        from workspace.services.agency_members import remove_agency_member
        remove_agency_member(self.owner_a, self.member_a.pk)
        with self.assertRaises(AgencyDataScopeError):
            resolve_visible_agency_member(self.owner_a, self.member_a.pk)
        self.assertTrue(Customer.objects.filter(pk=self.contact_a.pk).exists())


class IDORTests(AgencyPhase3Base):
    def test_advisor_detail_cross_agency_403(self):
        self.client.force_login(self.owner_a)
        url = reverse('workspace:agency_advisor_detail', kwargs={'member_id': self.member_b.pk})
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (403, 404))

    def test_export_cross_agency_403(self):
        self.client.force_login(self.owner_a)
        url = reverse('workspace:agency_advisor_export', kwargs={'member_id': self.member_b.pk})
        resp = self.client.get(url, {'type': 'contacts', 'format': 'csv'})
        self.assertIn(resp.status_code, (302, 403, 404))

    def test_api_cross_agency_403(self):
        self.client.force_login(self.owner_a)
        url = reverse('workspace:api_agency_advisor_detail', kwargs={'member_id': self.member_b.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_personal_user_denied(self):
        self.client.force_login(self.personal)
        url = reverse('workspace:agency_advisor_detail', kwargs={'member_id': self.member_a.pk})
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (302, 403, 404))


class AdvisorMemberViewTests(AgencyPhase3Base):
    def test_advisor_gets_member_view_not_owner_team(self):
        self.client.force_login(self.advisor_a)
        resp = self.client.get(reverse('workspace:crm_team'))
        self.assertRedirects(resp, reverse('workspace:agency_advisor_member'), fetch_redirect_response=False)

    def test_owner_legacy_team_members_redirects(self):
        self.client.force_login(self.owner_a)
        resp = self.client.get(reverse('workspace:crm_team') + '?tab=members')
        self.assertRedirects(resp, reverse('workspace:agency_hub_advisors'), fetch_redirect_response=False)
