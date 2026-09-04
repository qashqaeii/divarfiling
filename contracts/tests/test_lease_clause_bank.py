"""Tests for Lease Phase 1 clause bank."""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from contracts.constants import CLAUSE_REVIEW_PENDING, CLAUSE_REVIEW_REVIEWED, CONTRACT_TYPE_LEASE
from contracts.models import ContractClauseDefinition
from contracts.services.clause_ux import resolve_selected_clauses
from contracts.services.lease_clause_bank import (
    LEASE_PHASE1_DEFINITIONS,
    render_costs_body,
    render_lease_clause_body,
)

User = get_user_model()


class LeaseClauseBankTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='lb1', phone='09121111111', password='x')
        call_command('seed_contract_clauses')

    def _reviewed(self, code):
        ContractClauseDefinition.objects.filter(code=code, version=1).update(
            review_status=CLAUSE_REVIEW_REVIEWED,
        )

    def test_all_phase1_clauses_reviewed_after_seed(self):
        codes = {d['code'] for d in LEASE_PHASE1_DEFINITIONS}
        for code in codes:
            defn = ContractClauseDefinition.objects.get(code=code, version=1)
            self.assertEqual(defn.review_status, CLAUSE_REVIEW_REVIEWED)

    def test_production_user_sees_active_reviewed(self):
        from contracts.services.clauses import get_applicable_clauses
        with self.settings(DEBUG=False, LEGAL_REVIEW_PREVIEW=False):
            codes = [c.code for c in get_applicable_clauses('lease', user=self.user)]
            self.assertIn('LEASE_USE_PURPOSE', codes)
            self.assertIn('LEASE_CARE', codes)
            reviewed = [
                c for c in get_applicable_clauses('lease', user=self.user)
                if c.review_status == CLAUSE_REVIEW_REVIEWED
            ]
            self.assertGreater(len(reviewed), 0)

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
        body = render_lease_clause_body(
            'LEASE_PENALTY_VACATE',
            ContractClauseDefinition.objects.get(code='LEASE_PENALTY_VACATE', version=1).body_template,
            inline_values={'amount': 500000},
        )
        self.assertIn('500', body)

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
