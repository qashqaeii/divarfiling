"""Regression tests for Clause Center UX and rule engine."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from contracts.constants import CLAUSE_REVIEW_PENDING, CLAUSE_REVIEW_REVIEWED, CONTRACT_TYPE_LEASE
from contracts.models import ContractClauseDefinition
from contracts.services.clause_ux import (
    MAIN_ARTICLE_CODES,
    apply_clauses_step,
    build_clause_context,
    render_clause_sections_for_review,
    resolve_selected_clauses,
)
from contracts.services.clauses import get_applicable_clauses
from contracts.services.lifecycle import create_contract, save_wizard_step
from contracts.services.contract_renderer import render_contract_document
from workspace.models import CRMDeal, CRMProperty, Customer

User = get_user_model()


class ClauseUxTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cu1', phone='09121111111', password='x')
        self.customer = Customer.objects.create(user=self.user, name='تست', phone='09123333333')
        self.prop = CRMProperty.objects.create(
            user=self.user, title='ملک', address='تهران',
            deposit=100000000, monthly_rent=5000000,
        )
        self.deal = CRMDeal.objects.create(
            user=self.user, customer=self.customer, property=self.prop,
            title='معامله', deal_kind='rent',
        )

    def _reviewed_lease_clause(self, code, **kwargs):
        return ContractClauseDefinition.objects.create(
            code=code,
            title=kwargs.get('title', code),
            category=kwargs.get('category', 'c'),
            contract_type=CONTRACT_TYPE_LEASE,
            body_template=kwargs.get('body_template', f'متن {code}'),
            review_status=CLAUSE_REVIEW_REVIEWED,
            is_active=True,
        )

    def test_production_excludes_pending_clauses(self):
        ContractClauseDefinition.objects.create(
            code='UX_PENDING', title='t', category='c', contract_type='lease',
            body_template='x', review_status=CLAUSE_REVIEW_PENDING,
        )
        with self.settings(DEBUG=False, LEGAL_REVIEW_PREVIEW=False):
            codes = [c.code for c in get_applicable_clauses('lease', user=self.user)]
            self.assertNotIn('UX_PENDING', codes)

    def test_conditional_transfer_includes_sublease_clause(self):
        self._reviewed_lease_clause('LEASE_SUBLEASE', body_template='منع انتقال')
        self._reviewed_lease_clause('LEASE_USE_PURPOSE')
        wizard = {
            'financial': {
                'transfer_to_third_party_allowed': False,
                'costs': {'minor_repairs': 'tenant', 'major_repairs': 'landlord'},
            },
            'property': {},
        }
        selected = resolve_selected_clauses(CONTRACT_TYPE_LEASE, wizard, user=self.user)
        codes = [s.get('code') for s in selected if s.get('code')]
        self.assertIn('LEASE_SUBLEASE', codes)

    def test_transfer_allowed_excludes_sublease(self):
        self._reviewed_lease_clause('LEASE_SUBLEASE')
        self._reviewed_lease_clause('LEASE_SUBLEASE_WITH_CONSENT')
        self._reviewed_lease_clause('LEASE_USE_PURPOSE')
        wizard = {
            'financial': {
                'transfer_to_third_party_allowed': True,
                'transfer_requires_landlord_consent': True,
                'costs': {'minor_repairs': 'tenant', 'major_repairs': 'landlord'},
            },
            'property': {},
        }
        selected = resolve_selected_clauses(CONTRACT_TYPE_LEASE, wizard, user=self.user)
        codes = [s.get('code') for s in selected if s.get('code')]
        self.assertNotIn('LEASE_SUBLEASE', codes)
        self.assertIn('LEASE_SUBLEASE_WITH_CONSENT', codes)

    def test_penalty_clause_only_when_enabled(self):
        self._reviewed_lease_clause('LEASE_PENALTY_VACATE', body_template='جریمه {{amount}}')
        self._reviewed_lease_clause('LEASE_USE_PURPOSE')
        wizard = {
            'financial': {
                'penalties': {
                    'tenant_vacate_delay': {'enabled': True, 'amount_per_day': 500000},
                },
                'costs': {'minor_repairs': 'tenant', 'major_repairs': 'landlord'},
            },
            'property': {},
        }
        selected = resolve_selected_clauses(CONTRACT_TYPE_LEASE, wizard, user=self.user)
        codes = [s.get('code') for s in selected if s.get('code')]
        self.assertIn('LEASE_PENALTY_VACATE', codes)

        wizard['financial']['penalties'] = {}
        selected2 = resolve_selected_clauses(CONTRACT_TYPE_LEASE, wizard, user=self.user)
        codes2 = [s.get('code') for s in selected2 if s.get('code')]
        self.assertNotIn('LEASE_PENALTY_VACATE', codes2)

    def test_custom_agreement_separation_in_review(self):
        clauses = [
            {'is_custom': True, 'title': 'توافق ۱', 'body_text': 'متن اختصاصی', 'is_active': True},
            {'code': 'LEASE_BREACH_TERMINATION', 'title': 'فسخ', 'body_text': 'داوری', 'is_active': True},
        ]
        sections = render_clause_sections_for_review(clauses, CONTRACT_TYPE_LEASE)
        custom = [s for s in sections if s.get('is_custom_section')]
        self.assertEqual(len(custom), 1)
        self.assertIn('توافقات اختصاصی', custom[0]['title'])
        self.assertIn('متن اختصاصی', custom[0]['body'])

    def test_main_articles_not_in_clause_selection(self):
        for code in MAIN_ARTICLE_CODES[CONTRACT_TYPE_LEASE]:
            self._reviewed_lease_clause(code)
        wizard = {'financial': {'costs': {}}, 'property': {}}
        selected = resolve_selected_clauses(CONTRACT_TYPE_LEASE, wizard, user=self.user)
        codes = {s.get('code') for s in selected if s.get('code')}
        self.assertFalse(codes & MAIN_ARTICLE_CODES[CONTRACT_TYPE_LEASE])

    def test_apply_clauses_step_merges_financial_decisions(self):
        wizard = {'financial': {'costs': {}}, 'property': {}}
        parsed = {
            'transfer_choice': 'denied',
            'costs': {'water': 'landlord', 'charge': 'tenant', 'minor_repairs': 'tenant', 'major_repairs': 'landlord'},
            'penalties': {
                'tenant_vacate_delay': {'enabled': True, 'amount_per_day': 100000, 'unit': 'daily'},
            },
            'optional_clauses': [],
            'custom_agreements': [{'title': 'توافق', 'body': 'متن'}],
        }
        out = apply_clauses_step(wizard, parsed, CONTRACT_TYPE_LEASE, user=self.user)
        self.assertFalse(out['financial']['transfer_to_third_party_allowed'])
        self.assertEqual(out['financial']['costs']['water'], 'landlord')
        self.assertTrue(out['financial']['penalties']['tenant_vacate_delay']['enabled'])
        self.assertTrue(any(c.get('is_custom') for c in out['selected_clauses']))

    def test_review_document_no_duplicate_main_clause_sections(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        save_wizard_step(c, 'financial', {
            'monthly_rent': 5000000, 'deposit': 100000000,
            'lease_start': '1404/01/01', 'lease_end': '1405/01/01',
            'costs': {'charge': 'tenant'},
        }, user=self.user)
        self._reviewed_lease_clause('LEASE_SUBLEASE')
        save_wizard_step(c, 'clauses', {
            'transfer_choice': 'denied',
            'costs': {'charge': 'tenant'},
            'penalties': {},
            'optional_clauses': [],
            'custom_agreements': [],
        }, user=self.user)
        c.refresh_from_db()
        sections = render_contract_document(c)
        titles = [s['title'] for s in sections]
        self.assertTrue(any('ودیعه و اجاره' in t for t in titles))
        main_dup = [t for t in titles if 'LEASE_SUBJECT' in t or t.count('ودیعه') > 1]
        self.assertEqual(main_dup, [])

    def test_build_clause_context_property_flags(self):
        ctx = build_clause_context({
            'property': {'has_tenant': True},
            'financial': {'deposit_mode': 'retained'},
        })
        self.assertTrue(ctx['property_has_tenant'])
        self.assertTrue(ctx['old_deposit_retained'])
