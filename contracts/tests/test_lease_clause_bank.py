"""Tests for Lease Phase 1 clause bank."""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from contracts.constants import CLAUSE_REVIEW_PENDING, CLAUSE_REVIEW_REVIEWED, CONTRACT_TYPE_LEASE
from contracts.models import ContractClauseDefinition
from contracts.services.clause_ux import resolve_selected_clauses
from contracts.services.clause_ux import clause_review_badge
from contracts.services.clauses import get_applicable_clauses
from contracts.services.lifecycle import create_contract, validate_contract_ready
from contracts.services.lifecycle import sync_clauses_from_selection, save_wizard_step
from contracts.services.lease_clause_bank import (
    LEASE_PHASE1_DEFINITIONS,
    render_costs_body,
    render_lease_clause_body,
)
from workspace.models import CRMDeal, CRMProperty, Customer

User = get_user_model()


class LeaseClauseBankTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='lb1', phone='09121111111', password='x')
        self.customer = Customer.objects.create(user=self.user, name='تست', phone='09123333335')
        self.prop = CRMProperty.objects.create(
            user=self.user, title='ملک اجاره', address='تهران',
        )
        self.deal = CRMDeal.objects.create(
            user=self.user, customer=self.customer, property=self.prop,
            title='اجاره', deal_kind='rent', value=10000000,
        )
        call_command('seed_contract_clauses')

    def _reviewed(self, code):
        ContractClauseDefinition.objects.filter(code=code, version=1).update(
            review_status=CLAUSE_REVIEW_REVIEWED,
        )

    def test_all_phase1_clauses_pending_after_seed(self):
        codes = {d['code'] for d in LEASE_PHASE1_DEFINITIONS}
        for code in codes:
            defn = ContractClauseDefinition.objects.get(code=code, version=1)
            self.assertEqual(defn.review_status, CLAUSE_REVIEW_PENDING)

    def test_production_user_sees_active_pending_clauses(self):
        pending_db = ContractClauseDefinition.objects.filter(
            contract_type=CONTRACT_TYPE_LEASE,
            is_active=True,
            review_status=CLAUSE_REVIEW_PENDING,
        ).count()
        self.assertEqual(pending_db, len(LEASE_PHASE1_DEFINITIONS))
        with self.settings(DEBUG=False, LEGAL_REVIEW_PREVIEW=False):
            clauses = get_applicable_clauses('lease', user=self.user)
            codes = [c.code for c in clauses]
            self.assertIn('LEASE_USE_PURPOSE', codes)
            self.assertIn('LEASE_CARE', codes)
            visible_pending = [c for c in clauses if c.review_status == CLAUSE_REVIEW_PENDING]
            self.assertGreater(len(visible_pending), 0)

    def test_pending_badge_label(self):
        self.assertEqual(clause_review_badge(CLAUSE_REVIEW_PENDING), 'بند پیشنهادی')

    def test_transfer_forbidden_includes_sublease(self):
        self._reviewed('LEASE_SUBLEASE')
        self._reviewed('LEASE_USE_PURPOSE')
        wizard = {
            'financial': {
                'transfer_to_third_party_allowed': False,
                'costs': {'minor_repairs': 'tenant', 'major_repairs': 'landlord'},
                'lease_end': '1405/01/01',
                'deposit': 1000000,
            },
            'property': {},
        }
        codes = [c.get('code') for c in resolve_selected_clauses(CONTRACT_TYPE_LEASE, wizard, user=self.user)]
        self.assertIn('LEASE_SUBLEASE', codes)
        self.assertNotIn('LEASE_SUBLEASE_WITH_CONSENT', codes)

    def test_transfer_with_consent_alternative_clause(self):
        self._reviewed('LEASE_SUBLEASE_WITH_CONSENT')
        self._reviewed('LEASE_USE_PURPOSE')
        wizard = {
            'financial': {
                'transfer_to_third_party_allowed': True,
                'transfer_requires_landlord_consent': True,
                'costs': {'minor_repairs': 'tenant', 'major_repairs': 'landlord'},
                'lease_end': '1405/01/01',
                'deposit': 1000000,
            },
            'property': {},
        }
        codes = [c.get('code') for c in resolve_selected_clauses(CONTRACT_TYPE_LEASE, wizard, user=self.user)]
        self.assertIn('LEASE_SUBLEASE_WITH_CONSENT', codes)
        self.assertNotIn('LEASE_SUBLEASE', codes)

    def test_no_deposit_omits_deposit_clause(self):
        self._reviewed('LEASE_USE_PURPOSE')
        wizard = {'financial': {'deposit': 0, 'costs': {}}, 'property': {}}
        codes = [c.get('code') for c in resolve_selected_clauses(CONTRACT_TYPE_LEASE, wizard, user=self.user)]
        self.assertNotIn('LEASE_DEPOSIT_RETURN', codes)
        self.assertNotIn('LEASE_DEPOSIT_RETAINED', codes)

    def test_retained_deposit_clause(self):
        self._reviewed('LEASE_DEPOSIT_RETAINED')
        self._reviewed('LEASE_USE_PURPOSE')
        wizard = {
            'financial': {
                'deposit_mode': 'retained',
                'previous_deposit_amount': 5000000,
                'previous_contract_ref': 'RNT-OLD-1',
                'costs': {'minor_repairs': 'tenant', 'major_repairs': 'landlord'},
            },
            'property': {},
        }
        codes = [c.get('code') for c in resolve_selected_clauses(CONTRACT_TYPE_LEASE, wizard, user=self.user)]
        self.assertIn('LEASE_DEPOSIT_RETAINED', codes)

    def test_penalty_disabled_omitted(self):
        self._reviewed('LEASE_USE_PURPOSE')
        self._reviewed('LEASE_PENALTY_VACATE')
        wizard = {
            'financial': {
                'penalties': {'tenant_vacate_delay': {'enabled': False}},
                'costs': {},
            },
            'property': {},
        }
        codes = [c.get('code') for c in resolve_selected_clauses(CONTRACT_TYPE_LEASE, wizard, user=self.user)]
        self.assertNotIn('LEASE_PENALTY_VACATE', codes)

    def test_penalty_enabled_renders_amount(self):
        self._reviewed('LEASE_PENALTY_VACATE')
        defn = ContractClauseDefinition.objects.get(code='LEASE_PENALTY_VACATE', version=1)
        body = render_lease_clause_body(
            'LEASE_PENALTY_VACATE', defn.body_template,
            inline_values={'amount': 500000, 'penalty_unit': 'daily'},
        )
        self.assertIn('500', body)
        self.assertIn('به ازای هر روز تأخیر', body)

    def test_penalty_daily_basis_rendered(self):
        defn = ContractClauseDefinition.objects.get(code='LEASE_PENALTY_DELIVERY', version=1)
        body = render_lease_clause_body(
            'LEASE_PENALTY_DELIVERY', defn.body_template,
            inline_values={'amount': 100000, 'unit': 'daily'},
        )
        self.assertIn('به ازای هر روز تأخیر', body)
        self.assertNotIn('بابت هر روز', body)

    def test_penalty_fixed_basis_rendered(self):
        defn = ContractClauseDefinition.objects.get(code='LEASE_PENALTY_DEPOSIT_RETURN', version=1)
        body = render_lease_clause_body(
            'LEASE_PENALTY_DEPOSIT_RETURN', defn.body_template,
            inline_values={'amount': 2000000, 'penalty_unit': 'fixed'},
        )
        self.assertIn('به صورت مقطوع', body)
        self.assertNotIn('به ازای هر روز', body)
        self.assertIn('2', body)

    def test_retained_deposit_missing_reference_validation_error(self):
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        version = c.current_version
        version.financial_data = {
            'monthly_rent': 10000000,
            'deposit': 1000000,
            'deposit_mode': 'retained',
            'previous_deposit_amount': 5000000,
            'lease_start': '1404/01/01',
            'lease_end': '1405/01/01',
        }
        version.save()
        errors = validate_contract_ready(c, version)
        self.assertTrue(
            any('مشخصات قرارداد قبلی' in e for e in errors),
        )

    def test_retained_deposit_renders_without_em_dash(self):
        defn = ContractClauseDefinition.objects.get(code='LEASE_DEPOSIT_RETAINED', version=1)
        body = render_lease_clause_body(
            'LEASE_DEPOSIT_RETAINED', defn.body_template,
            fin={
                'deposit_mode': 'retained',
                'previous_deposit_amount': 5000000,
                'previous_contract_ref': 'RNT-OLD-1',
            },
        )
        self.assertIn('RNT-OLD-1', body)
        self.assertNotIn('—', body)

    def test_retained_deposit_in_review_document(self):
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        save_wizard_step(c, 'parties', [
            {'role': 'landlord', 'first_name': 'ع', 'last_name': 'الف', 'mobile': '09121111111', 'national_id': '1111111111'},
            {'role': 'tenant', 'first_name': 'ب', 'last_name': 'ب', 'mobile': '09122222222', 'national_id': '2222222222'},
        ], user=self.user)
        save_wizard_step(c, 'property', {'address': 'تهران', 'area': 100}, user=self.user)
        save_wizard_step(c, 'financial', {
            'monthly_rent': 10000000,
            'deposit': 5000000,
            'deposit_mode': 'retained',
            'previous_deposit_amount': 5000000,
            'previous_contract_ref': 'RNT-OLD-99',
            'lease_start': '1404/01/01',
            'lease_end': '1405/01/01',
            'costs': {'minor_repairs': 'tenant', 'major_repairs': 'landlord'},
        }, user=self.user)
        save_wizard_step(c, 'clauses', {
            'costs': {'minor_repairs': 'tenant', 'major_repairs': 'landlord'},
            'penalties': {},
            'optional_clauses': [],
        }, user=self.user)
        c.refresh_from_db()
        sync_clauses_from_selection(c, c.current_version)
        c.current_version.refresh_from_db()
        retained = c.current_version.clauses.filter(code='LEASE_DEPOSIT_RETAINED').first()
        self.assertIsNotNone(retained)
        self.assertIn('RNT-OLD-99', retained.body_text)
        self.assertNotIn('—', retained.body_text)

    def test_costs_render_selected_parties(self):
        text = render_costs_body({'water': 'landlord', 'charge': 'tenant'})
        self.assertIn('آب', text)
        self.assertIn('موجر', text)
        self.assertIn('شارژ', text)
        self.assertIn('مستأجر', text)

    def test_repairs_render_separately(self):
        self._reviewed('LEASE_REPAIRS')
        defn = ContractClauseDefinition.objects.get(code='LEASE_REPAIRS', version=1)
        body = render_lease_clause_body(
            'LEASE_REPAIRS', defn.body_template,
            fin={'costs': {'major_repairs': 'landlord', 'minor_repairs': 'tenant'}},
        )
        self.assertIn('موجر', body)
        self.assertIn('مستأجر', body)

    def test_custom_agreements_separate(self):
        wizard = {
            'financial': {'costs': {}},
            'property': {},
            'custom_agreements': [{'title': 'توافق', 'body': 'متن آزاد'}],
        }
        selected = resolve_selected_clauses(CONTRACT_TYPE_LEASE, wizard, user=self.user)
        self.assertTrue(any(c.get('is_custom') for c in selected))
