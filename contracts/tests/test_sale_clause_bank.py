"""Tests for Sale Phase 1 clause bank and production visibility."""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from contracts.constants import CLAUSE_REVIEW_PENDING, CLAUSE_REVIEW_REVIEWED, CONTRACT_TYPE_LEASE, CONTRACT_TYPE_SALE
from contracts.models import ContractClauseDefinition
from contracts.services.clause_ux import (
    clause_review_badge,
    render_clause_sections_for_review,
    resolve_selected_clauses,
)
from contracts.services.clauses import get_applicable_clauses
from contracts.services.lifecycle import create_contract, save_wizard_step, sync_clauses_from_selection
from contracts.services.contract_renderer import render_contract_document
from contracts.services.sale_clause_bank import (
    SALE_PHASE1_DEFINITIONS,
    render_sale_clause_body,
)
from workspace.models import CRMDeal, CRMProperty, Customer

User = get_user_model()


class SaleClauseBankTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sb1', phone='09121111112', password='x')
        self.customer = Customer.objects.create(user=self.user, name='تست', phone='09123333334')
        self.prop = CRMProperty.objects.create(
            user=self.user, title='ملک فروش', address='تهران',
        )
        self.deal = CRMDeal.objects.create(
            user=self.user, customer=self.customer, property=self.prop,
            title='فروش', deal_kind='sale', value=5000000000,
        )
        call_command('seed_contract_clauses')

    def test_all_phase1_sale_clauses_pending_after_seed(self):
        codes = {d['code'] for d in SALE_PHASE1_DEFINITIONS}
        for code in codes:
            defn = ContractClauseDefinition.objects.get(code=code, version=1)
            self.assertEqual(defn.review_status, CLAUSE_REVIEW_PENDING)

    def test_production_user_sees_active_pending_sale_clauses(self):
        pending_db = ContractClauseDefinition.objects.filter(
            contract_type=CONTRACT_TYPE_SALE,
            is_active=True,
            review_status=CLAUSE_REVIEW_PENDING,
        ).count()
        self.assertEqual(pending_db, len(SALE_PHASE1_DEFINITIONS))
        with self.settings(DEBUG=False, LEGAL_REVIEW_PREVIEW=False):
            clauses = get_applicable_clauses('sale', user=self.user)
            codes = [c.code for c in clauses]
            self.assertIn('SALE_PROPERTY_DECLARATIONS', codes)
            visible_pending = [c for c in clauses if c.review_status == CLAUSE_REVIEW_PENDING]
            self.assertGreater(len(visible_pending), 0)

    def test_pending_badge_label(self):
        self.assertEqual(clause_review_badge(CLAUSE_REVIEW_PENDING), 'بند پیشنهادی')
        self.assertEqual(clause_review_badge(CLAUSE_REVIEW_REVIEWED), 'بند بررسی‌شده')

    def test_sale_clauses_not_in_lease(self):
        with self.settings(DEBUG=False):
            lease_codes = {c.code for c in get_applicable_clauses('lease', user=self.user)}
            for d in SALE_PHASE1_DEFINITIONS:
                self.assertNotIn(d['code'], lease_codes)

    def test_lease_clauses_not_in_sale(self):
        from contracts.services.lease_clause_bank import LEASE_PHASE1_DEFINITIONS
        with self.settings(DEBUG=False):
            sale_codes = {c.code for c in get_applicable_clauses('sale', user=self.user)}
            for d in LEASE_PHASE1_DEFINITIONS:
                self.assertNotIn(d['code'], sale_codes)

    def test_property_has_tenant_conditional(self):
        wizard_no_tenant = {
            'financial': {'total_price': 1000000, 'sale_costs': {}},
            'property': {'has_tenant': False},
        }
        codes_no = [c.get('code') for c in resolve_selected_clauses(CONTRACT_TYPE_SALE, wizard_no_tenant, user=self.user)]
        self.assertNotIn('SALE_EXISTING_TENANT', codes_no)

        wizard_tenant = {
            'financial': {'total_price': 1000000, 'sale_costs': {}},
            'property': {'has_tenant': True},
        }
        codes_yes = [c.get('code') for c in resolve_selected_clauses(CONTRACT_TYPE_SALE, wizard_tenant, user=self.user)]
        self.assertIn('SALE_EXISTING_TENANT', codes_yes)

    def test_payment_penalty_only_when_enabled_with_amount(self):
        wizard = {
            'financial': {
                'total_price': 1000000,
                'penalties': {'payment_delay': {'enabled': True, 'amount': 500000}},
            },
            'property': {},
        }
        codes = [c.get('code') for c in resolve_selected_clauses(CONTRACT_TYPE_SALE, wizard, user=self.user)]
        self.assertIn('SALE_PENALTY_PAYMENT', codes)

        wizard['financial']['penalties'] = {'payment_delay': {'enabled': False, 'amount': 500000}}
        codes2 = [c.get('code') for c in resolve_selected_clauses(CONTRACT_TYPE_SALE, wizard, user=self.user)]
        self.assertNotIn('SALE_PENALTY_PAYMENT', codes2)

    def test_delivery_penalty_condition(self):
        wizard = {
            'financial': {
                'total_price': 1000000,
                'penalties': {'delivery_delay': {'enabled': True, 'amount': 300000}},
            },
            'property': {},
        }
        codes = [c.get('code') for c in resolve_selected_clauses(CONTRACT_TYPE_SALE, wizard, user=self.user)]
        self.assertIn('SALE_PENALTY_DELIVERY', codes)

    def test_official_transfer_penalty_condition(self):
        wizard = {
            'financial': {
                'total_price': 1000000,
                'penalties': {'transfer_delay': {'enabled': True, 'amount': 200000}},
            },
            'property': {},
        }
        codes = [c.get('code') for c in resolve_selected_clauses(CONTRACT_TYPE_SALE, wizard, user=self.user)]
        self.assertIn('SALE_PENALTY_OFFICIAL_TRANSFER', codes)

    def test_no_default_penalty_amount(self):
        wizard = {
            'financial': {
                'total_price': 1000000,
                'penalties': {'payment_delay': {'enabled': True, 'amount': 0}},
            },
            'property': {},
        }
        codes = [c.get('code') for c in resolve_selected_clauses(CONTRACT_TYPE_SALE, wizard, user=self.user)]
        self.assertNotIn('SALE_PENALTY_PAYMENT', codes)

    def test_custom_agreements_separate(self):
        wizard = {
            'financial': {'total_price': 1000000},
            'property': {},
            'custom_agreements': [{'title': 'توافق', 'body': 'متن آزاد'}],
        }
        selected = resolve_selected_clauses(CONTRACT_TYPE_SALE, wizard, user=self.user)
        self.assertTrue(any(c.get('is_custom') for c in selected))
        sections = render_clause_sections_for_review(
            [{'is_custom': True, 'title': 'توافق', 'body_text': 'متن آزاد', 'is_active': True}],
            CONTRACT_TYPE_SALE,
        )
        self.assertEqual(len(sections), 1)
        self.assertIn('توافقات اختصاصی', sections[0]['title'])

    def test_review_includes_pending_clause_text(self):
        clauses = [
            {
                'code': 'SALE_PROPERTY_DECLARATIONS',
                'title': 'وضعیت اعلامی',
                'body_text': 'فروشنده اعلام می‌نماید ...',
                'is_active': True,
            },
        ]
        sections = render_clause_sections_for_review(clauses, CONTRACT_TYPE_SALE)
        self.assertTrue(any('فروشنده اعلام' in s.get('body', '') for s in sections))
        for s in sections:
            self.assertNotIn('review_pending', s.get('body', ''))
            self.assertNotIn('بند پیشنهادی', s.get('body', ''))

    def test_public_document_no_review_metadata(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_SALE)
        save_wizard_step(c, 'parties', [
            {'role': 'seller', 'first_name': 'ع', 'last_name': 'الف', 'mobile': '09121111111', 'national_id': '1111111111'},
            {'role': 'buyer', 'first_name': 'ب', 'last_name': 'ب', 'mobile': '09122222222', 'national_id': '2222222222'},
        ], user=self.user)
        save_wizard_step(c, 'property', {'address': 'تهران', 'area': 100}, user=self.user)
        save_wizard_step(c, 'financial', {
            'total_price': 5000000000,
            'delivery_date': '1404/06/01',
            'sale_costs': {'transfer_costs': 'seller'},
        }, user=self.user)
        save_wizard_step(c, 'clauses', {
            'property_has_tenant': False,
            'sale_costs': {'transfer_costs': 'seller'},
            'penalties': {},
            'optional_clauses': [],
            'custom_agreements': [],
        }, user=self.user)
        c.refresh_from_db()
        sync_clauses_from_selection(c, c.current_version)
        sections = render_contract_document(c)
        full_text = '\n'.join(s.get('body', '') for s in sections)
        self.assertIn('فروشنده اعلام', full_text)
        self.assertNotIn('review_pending', full_text)
        self.assertNotIn('بند پیشنهادی', full_text)

    def test_seed_idempotent(self):
        before = ContractClauseDefinition.objects.filter(
            contract_type=CONTRACT_TYPE_SALE, is_active=True,
        ).count()
        call_command('seed_contract_clauses')
        after = ContractClauseDefinition.objects.filter(
            contract_type=CONTRACT_TYPE_SALE, is_active=True,
        ).count()
        self.assertEqual(before, after)
        self.assertEqual(after, len(SALE_PHASE1_DEFINITIONS))

    def test_penalty_render_uses_user_amount(self):
        defn = ContractClauseDefinition.objects.get(code='SALE_PENALTY_PAYMENT', version=1)
        body = render_sale_clause_body(
            'SALE_PENALTY_PAYMENT', defn.body_template,
            inline_values={'amount': 750000, 'penalty_unit': 'daily'},
        )
        self.assertIn('750', body)

    def test_official_transfer_penalty_includes_amount_and_basis(self):
        defn = ContractClauseDefinition.objects.get(code='SALE_PENALTY_OFFICIAL_TRANSFER', version=1)
        body_daily = render_sale_clause_body(
            'SALE_PENALTY_OFFICIAL_TRANSFER', defn.body_template,
            inline_values={'amount': 5000000, 'penalty_unit': 'daily'},
        )
        self.assertIn('5', body_daily)
        self.assertIn('به ازای هر روز تأخیر', body_daily)

        body_fixed = render_sale_clause_body(
            'SALE_PENALTY_OFFICIAL_TRANSFER', defn.body_template,
            inline_values={'amount': 3000000, 'penalty_unit': 'fixed'},
        )
        self.assertIn('3', body_fixed)
        self.assertIn('به صورت مقطوع', body_fixed)

    def test_all_phase1_clauses_count_after_seed(self):
        lease_pending = ContractClauseDefinition.objects.filter(
            contract_type=CONTRACT_TYPE_LEASE, is_active=True,
            review_status=CLAUSE_REVIEW_PENDING,
        ).count()
        sale_pending = ContractClauseDefinition.objects.filter(
            contract_type=CONTRACT_TYPE_SALE, is_active=True,
            review_status=CLAUSE_REVIEW_PENDING,
        ).count()
        self.assertEqual(lease_pending, 14)
        self.assertEqual(sale_pending, 13)

    def test_wizard_stale_legal_approval_text_removed(self):
        from pathlib import Path
        wizard_path = Path(__file__).resolve().parents[2] / 'templates' / 'contracts' / 'wizard.html'
        content = wizard_path.read_text(encoding='utf-8')
        self.assertNotIn('پس از تأیید حقوقی', content)
        self.assertIn('بندهای پیشنهادی را متناسب با شرایط معامله', content)
