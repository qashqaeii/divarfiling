"""Tests for Contract Wizard review step."""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from contracts.constants import CONTRACT_TYPE_LEASE, CONTRACT_TYPE_SALE
from contracts.services.contract_renderer import render_contract_document
from contracts.services.lifecycle import create_contract, save_wizard_step, sync_clauses_from_selection, validate_contract_ready
from contracts.services.review_context import build_review_context
from workspace.models import CRMDeal, CRMProperty, Customer

User = get_user_model()


class ReviewStepTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rev1', phone='09121111113', password='x')
        self.customer = Customer.objects.create(user=self.user, name='تست', phone='09123333335')
        self.prop = CRMProperty.objects.create(
            user=self.user, title='ملک', address='تهران، ونک',
            deposit=100000000, monthly_rent=5000000, area=95,
        )
        self.deal_rent = CRMDeal.objects.create(
            user=self.user, customer=self.customer, property=self.prop,
            title='اجاره', deal_kind='rent',
        )
        self.deal_sale = CRMDeal.objects.create(
            user=self.user, customer=self.customer, property=self.prop,
            title='فروش', deal_kind='sale', value=44000000000,
        )
        call_command('seed_contract_clauses')
        self.client = Client()
        self.client.force_login(self.user)

    def _sale_contract(self):
        c = create_contract(self.user, self.deal_sale.pk, CONTRACT_TYPE_SALE)
        save_wizard_step(c, 'parties', [
            {'role': 'seller', 'first_name': 'علی', 'last_name': 'فروشنده', 'mobile': '09121111111', 'national_id': '1111111111'},
            {'role': 'buyer', 'first_name': 'رضا', 'last_name': 'خریدار', 'mobile': '09122222222', 'national_id': '2222222222'},
        ], user=self.user)
        save_wizard_step(c, 'property', {
            'property_type': 'آپارتمان', 'city': 'تهران', 'district': 'ونک',
            'address': 'تهران', 'area': 100, 'bedrooms': 2, 'has_parking': True,
        }, user=self.user)
        save_wizard_step(c, 'financial', {
            'total_price': 44000000000,
            'payments': [
                {'label': 'بیعانه', 'amount': 5000000000, 'due_date': '1405/06/10', 'payment_method': 'چک'},
                {'label': 'انتقال سند', 'amount': 39000000000, 'due_date': '1405/09/01', 'payment_method': 'نقد'},
            ],
            'transfer_date': '1405/09/01',
            'transfer_place': 'دفترخانه ۱۲۳',
            'delivery_date': '1405/07/01',
            'sale_costs': {
                'transfer_costs': 'shared',
                'notary_costs': 'seller',
                'pre_delivery_costs': 'buyer',
                'other_costs': 'shared',
            },
        }, user=self.user)
        save_wizard_step(c, 'clauses', {
            'property_has_tenant': False,
            'sale_costs': {
                'transfer_costs': 'shared',
                'notary_costs': 'seller',
                'pre_delivery_costs': 'buyer',
                'other_costs': 'shared',
            },
            'penalties': {'payment_delay': {'enabled': True, 'amount': 2000000}},
            'optional_clauses': [],
            'custom_agreements': [{'title': 'توافق ۱', 'body': 'متن توافق اختصاصی طرفین'}],
        }, user=self.user)
        c.refresh_from_db()
        sync_clauses_from_selection(c, c.current_version)
        return c

    def _lease_contract(self):
        c = create_contract(self.user, self.deal_rent.pk, CONTRACT_TYPE_LEASE)
        save_wizard_step(c, 'parties', [
            {'role': 'landlord', 'first_name': 'موجر', 'last_name': 'الف', 'mobile': '09121111111'},
            {'role': 'tenant', 'first_name': 'مستأجر', 'last_name': 'ب', 'mobile': '09122222222'},
        ], user=self.user)
        save_wizard_step(c, 'property', {'city': 'تهران', 'area': 95}, user=self.user)
        save_wizard_step(c, 'financial', {
            'monthly_rent': 5000000, 'deposit': 100000000,
            'lease_start': '1404/01/01', 'lease_end': '1405/01/01',
            'delivery_date': '1404/01/05',
            'costs': {'water': 'tenant', 'charge': 'tenant'},
        }, user=self.user)
        save_wizard_step(c, 'clauses', {
            'transfer_choice': 'denied',
            'costs': {'water': 'tenant', 'charge': 'tenant'},
            'penalties': {},
            'optional_clauses': [],
            'custom_agreements': [],
        }, user=self.user)
        save_wizard_step(c, 'witnesses', [
            {'witness_number': 1, 'first_name': 'شاهد', 'last_name': '۱', 'mobile': '09123333333', 'national_id': '3333333333'},
            {'witness_number': 2, 'first_name': 'شاهد', 'last_name': '۲', 'mobile': '09124444444', 'national_id': '4444444444'},
        ], user=self.user)
        c.refresh_from_db()
        sync_clauses_from_selection(c, c.current_version)
        return c

    def test_sale_review_shows_core_sections(self):
        c = self._sale_contract()
        sections = render_contract_document(c)
        titles = ' '.join(s['title'] for s in sections)
        self.assertIn('طرفین', titles)
        self.assertIn('مشخصات', titles)
        self.assertIn('مبلغ', titles)
        self.assertIn('برنامه پرداخت', titles)

    def test_lease_review_shows_core_sections(self):
        c = self._lease_contract()
        sections = render_contract_document(c)
        titles = ' '.join(s['title'] for s in sections)
        self.assertIn('طرفین', titles)
        self.assertIn('ودیعه', titles)
        self.assertIn('شاهدان', titles)

    def test_included_clauses_have_full_body(self):
        c = self._sale_contract()
        sections = render_contract_document(c)
        bodies = '\n'.join(s['body'] for s in sections)
        self.assertTrue(len(bodies) > 100)
        self.assertIn('فروشنده اعلام', bodies)

    def test_custom_agreements_in_review_context(self):
        c = self._sale_contract()
        ctx = build_review_context(c, validation_errors=validate_contract_ready(c, c.current_version))
        self.assertEqual(len(ctx['custom_agreements']), 1)
        self.assertIn('متن توافق', ctx['custom_agreements'][0]['body'])

    def test_payment_schedule_rows(self):
        c = self._sale_contract()
        ctx = build_review_context(c, validation_errors=[])
        self.assertEqual(len(ctx['payment_schedule']['rows']), 2)
        self.assertFalse(ctx['payment_schedule']['mismatch'])

    def test_readiness_ready_when_complete(self):
        c = self._sale_contract()
        errors = validate_contract_ready(c, c.current_version)
        ctx = build_review_context(c, validation_errors=errors)
        self.assertEqual(ctx['readiness'], 'ready')
        self.assertFalse(ctx['send_disabled'])

    def test_blocking_validation_disables_send(self):
        c = self._lease_contract()
        save_wizard_step(c, 'witnesses', [], user=self.user)
        c.refresh_from_db()
        errors = validate_contract_ready(c, c.current_version)
        ctx = build_review_context(c, validation_errors=errors)
        self.assertEqual(ctx['readiness'], 'blocked')
        self.assertTrue(ctx['send_disabled'])

    def test_no_placeholder_in_review_body(self):
        c = self._sale_contract()
        sections = render_contract_document(c)
        full = '\n'.join(s['body'] for s in sections)
        self.assertNotIn('{{', full)
        self.assertNotIn('undefined', full)
        self.assertNotIn('None', full)

    def test_review_status_not_in_document(self):
        c = self._sale_contract()
        sections = render_contract_document(c)
        full = '\n'.join(s['body'] for s in sections)
        self.assertNotIn('review_pending', full)
        self.assertNotIn('بند پیشنهادی', full)

    def test_edit_links_in_issues(self):
        c = self._sale_contract()
        parties = list(c.wizard_data.get('parties') or [])
        parties[0]['mobile'] = ''
        save_wizard_step(c, 'parties', parties, user=self.user)
        c.refresh_from_db()
        ctx = build_review_context(c, validation_errors=validate_contract_ready(c, c.current_version))
        warn_issues = [i for i in ctx['issues'] if i['severity'] == 'warn']
        self.assertTrue(any(i['edit_step'] == 'parties' for i in warn_issues))

    def test_review_step_http_renders(self):
        c = self._sale_contract()
        url = reverse('workspace:contract_wizard', kwargs={'deal_id': self.deal_sale.pk, 'contract_id': c.pk})
        resp = self.client.get(url + '?step=review')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'مرور نهایی')
        self.assertContains(resp, 'ct-review-layout')
        self.assertContains(resp, 'creator_ack')
        self.assertContains(resp, 'پیش‌نمایش PDF')

    def test_pdf_preview_route(self):
        c = self._sale_contract()
        url = reverse('workspace:contract_pdf_preview', kwargs={'deal_id': self.deal_sale.pk, 'contract_id': c.pk})
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (200, 404))

    def test_transfer_plan_in_financial_summary(self):
        c = self._sale_contract()
        ctx = build_review_context(c, validation_errors=[])
        self.assertEqual(ctx['financial_summary']['transfer_place'], 'دفترخانه ۱۲۳')

    def test_penalty_summary_from_data(self):
        c = self._sale_contract()
        ctx = build_review_context(c, validation_errors=[])
        self.assertTrue(len(ctx['penalty_summary']) >= 1)

    def test_sale_costs_summary_persian_labels(self):
        c = self._sale_contract()
        ctx = build_review_context(c, validation_errors=[])
        labels = [row['label'] for row in ctx['costs_summary']]
        self.assertIn('هزینه‌های انتقال', labels)
        self.assertIn('هزینه‌های دفترخانه', labels)
        self.assertIn('بدهی‌ها و هزینه‌های قبل از تحویل', labels)
        self.assertIn('سایر هزینه توافق‌شده', labels)
        joined = ' '.join(labels)
        self.assertNotIn('other_costs', joined)
        self.assertNotIn('notary_costs', joined)

    def test_clause_completeness_wording(self):
        c = self._sale_contract()
        ctx = build_review_context(c, validation_errors=[])
        clause_row = next(i for i in ctx['completeness'] if i['label'] == 'بندهای قرارداد')
        self.assertTrue(clause_row['value'].endswith('مورد'))

    def test_review_step_has_wide_modifier_class(self):
        c = self._sale_contract()
        url = reverse('workspace:contract_wizard', kwargs={'deal_id': self.deal_sale.pk, 'contract_id': c.pk})
        resp = self.client.get(url + '?step=review')
        self.assertContains(resp, 'ct-wizard--review')

    def test_section_ids_for_navigation(self):
        c = self._sale_contract()
        sections = render_contract_document(c)
        self.assertTrue(all(s.get('section_id') for s in sections))
        self.assertTrue(all(s.get('nav_key') for s in sections))
