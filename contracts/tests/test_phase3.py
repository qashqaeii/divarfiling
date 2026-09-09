"""Phase 3 tests — sale E2E, attachments, concurrency, handover."""
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from contracts.constants import CONTRACT_TYPE_SALE
from contracts.models import Contract, ContractHandover
from contracts.services.attachments import save_contract_attachment, validate_upload_file
from contracts.services.handover import accept_handover, create_handover, publish_handover, save_handover_step
from contracts.services.lifecycle import (
    create_contract,
    finalize_contract,
    prepare_for_send,
    save_wizard_step,
)
from contracts.services.invitations import send_invitations
from contracts.services.acceptance import accept_contract
from contracts.models import ContractInvitation
from workspace.models import CRMDeal, CRMProperty, Customer

User = get_user_model()


def _sale_wizard_data():
    return {
        'parties': [
            {'role': 'seller', 'first_name': 'ف', 'last_name': 'فروشنده', 'mobile': '09121111111', 'national_id': '1111111111'},
            {'role': 'buyer', 'first_name': 'خ', 'last_name': 'خریدار', 'mobile': '09122222222', 'national_id': '2222222222'},
        ],
        'property': {'address': 'تهران', 'area': 120, 'declared_by_parties': True},
        'financial': {
            'total_price': 5000000000,
            'payments': [
                {'label': 'بیعانه', 'amount': 500000000, 'due_date': '1404/02/01', 'payment_method': 'transfer'},
                {'label': 'مانده', 'amount': 4500000000, 'due_date': '1404/06/01', 'payment_method': 'cheque'},
            ],
            'transfer_date': '1404/06/15',
            'transfer_place': 'دفترخانه',
        },
        'selected_clauses': [{'is_custom': True, 'title': 'بند', 'body_text': 'متن'}],
        'witnesses': [],
    }


class ContractTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u1', phone='09120000001', password='x')
        self.other = User.objects.create_user(username='u2', phone='09120000002', password='x')
        self.customer = Customer.objects.create(user=self.user, name='مشتری', phone='09125555555')
        self.prop = CRMProperty.objects.create(
            user=self.user, title='ملک', address='تهران', sale_price=5000000000,
        )
        self.deal = CRMDeal.objects.create(
            user=self.user, customer=self.customer, property=self.prop,
            title='فروش', deal_kind='sale', value=5000000000,
        )


class SaleE2ETests(ContractTestBase):
    @patch('contracts.services.invitations.send_simple_sms')
    @patch('contracts.services.pdf.generate_contract_pdf')
    def test_sale_full_flow(self, mock_pdf, mock_sms):
        mock_sms.return_value = type('R', (), {'message_id': '1'})()
        c = create_contract(self.user, CONTRACT_TYPE_SALE, deal_id=self.deal.pk)
        wd = _sale_wizard_data()
        for step in ('parties', 'property', 'financial', 'clauses'):
            save_wizard_step(c, step, wd.get(step) or wd['selected_clauses'], user=self.user)
        prepare_for_send(c, user=self.user)
        send_invitations(c, user=self.user)
        for inv in ContractInvitation.objects.filter(contract=c):
            accept_contract(
                inv, phone=inv.mobile,
                national_id=inv.party.national_id,
                ack_checkboxes=['a'], otp_already_verified=True,
            )
        c.refresh_from_db()
        self.assertEqual(c.status, 'finalized')
        self.deal.refresh_from_db()
        self.assertTrue(self.deal.contract_number)


class AttachmentSecurityTests(ContractTestBase):
    def test_rejects_invalid_extension(self):
        bad = SimpleUploadedFile('x.exe', b'data', content_type='application/octet-stream')
        with self.assertRaises(Exception):
            validate_upload_file(bad)

    def test_upload_and_idor(self):
        c = create_contract(self.user, CONTRACT_TYPE_SALE, deal_id=self.deal.pk)
        v = c.current_version
        good = SimpleUploadedFile('doc.pdf', b'%PDF-1.4', content_type='application/pdf')
        att = save_contract_attachment(
            contract=c, version=v, uploaded=good, user=self.user,
        )
        self.assertNotIn('.pdf', att.file.name.split('/')[-1][:4])  # uuid prefix

        client = Client()
        client.force_login(self.user)
        url = reverse('workspace:contract_attachment_download', kwargs={
            'deal_id': self.deal.pk, 'contract_id': c.pk, 'attachment_id': att.pk,
        })
        self.assertEqual(client.get(url).status_code, 200)

        client.force_login(self.other)
        self.assertEqual(client.get(url).status_code, 404)


class ConcurrencyFinalizeTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='uc', phone='09128888888', password='x')
        self.customer = Customer.objects.create(user=self.user, name='c', phone='09127777777')
        self.deal = CRMDeal.objects.create(user=self.user, customer=self.customer, title='d', deal_kind='rent')
        self.prop = CRMProperty.objects.create(
            user=self.user, title='p', deposit=100, monthly_rent=10,
        )
        self.deal.property = self.prop
        self.deal.save()

    @patch('contracts.services.pdf.generate_contract_pdf')
    @patch('contracts.services.invitations.send_simple_sms')
    def test_concurrent_last_acceptance(self, mock_sms, mock_pdf):
        from contracts.constants import CONTRACT_TYPE_LEASE
        from contracts.tests.test_phase2 import _lease_wizard_data

        mock_sms.return_value = type('R', (), {'message_id': '1'})()
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        wd = _lease_wizard_data()
        for step in ('parties', 'property', 'financial', 'witnesses', 'clauses'):
            save_wizard_step(c, step, wd.get(step) or wd['selected_clauses'], user=self.user)
        prepare_for_send(c, user=self.user)
        send_invitations(c, user=self.user)
        invs = list(ContractInvitation.objects.filter(contract=c).order_by('pk'))
        for inv in invs[:-1]:
            accept_contract(
                inv, phone=inv.mobile,
                national_id=inv.party.national_id if inv.party_id else inv.witness.national_id,
                ack_checkboxes=['a'], otp_already_verified=True,
            )
        last = invs[-1]
        accept_contract(
            last, phone=last.mobile,
            national_id=last.party.national_id if last.party_id else last.witness.national_id,
            ack_checkboxes=['a'], otp_already_verified=True,
        )
        c.refresh_from_db()
        self.assertEqual(c.status, 'finalized')
        self.assertEqual(mock_pdf.call_count, 1)


class HandoverTests(ContractTestBase):
    @patch('contracts.services.handover_invitations.send_simple_sms')
    @patch('contracts.services.pdf.generate_contract_pdf')
    def _finalize_lease(self, mock_pdf, mock_sms):
        from contracts.constants import CONTRACT_TYPE_LEASE
        from contracts.tests.test_phase2 import _lease_wizard_data
        mock_sms.return_value = type('R', (), {'message_id': '1'})()
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        wd = _lease_wizard_data()
        for step in ('parties', 'property', 'financial', 'witnesses', 'clauses'):
            save_wizard_step(c, step, wd.get(step) or wd['selected_clauses'], user=self.user)
        prepare_for_send(c, user=self.user)
        send_invitations(c, user=self.user)
        for inv in ContractInvitation.objects.filter(contract=c):
            accept_contract(
                inv, phone=inv.mobile,
                national_id=inv.party.national_id if inv.party_id else inv.witness.national_id,
                ack_checkboxes=['a'], otp_already_verified=True,
            )
        return Contract.objects.get(pk=c.pk)

    @patch('contracts.services.handover_invitations.send_simple_sms')
    @patch('contracts.services.handover_pdf.generate_handover_pdf')
    def test_handover_flow(self, mock_hpdf, mock_sms):
        with patch('contracts.services.invitations.send_simple_sms') as ms, \
             patch('contracts.services.pdf.generate_contract_pdf'):
            ms.return_value = type('R', (), {'message_id': '1'})()
            from contracts.constants import CONTRACT_TYPE_LEASE
            from contracts.tests.test_phase2 import _lease_wizard_data
            c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
            wd = _lease_wizard_data()
            for step in ('parties', 'property', 'financial', 'witnesses', 'clauses'):
                save_wizard_step(c, step, wd.get(step) or wd['selected_clauses'], user=self.user)
            prepare_for_send(c, user=self.user)
            send_invitations(c, user=self.user)
            for inv in ContractInvitation.objects.filter(contract=c):
                accept_contract(
                    inv, phone=inv.mobile,
                    national_id=inv.party.national_id if inv.party_id else inv.witness.national_id,
                    ack_checkboxes=['a'], otp_already_verified=True,
                )
            c.refresh_from_db()

        mock_sms.return_value = type('R', (), {'message_id': '1'})()
        handover = create_handover(self.user, c.pk)
        parties = handover.snapshot_json['parties']
        save_handover_step(handover, 'basic', {
            'delivered_by': parties[0],
            'received_by': parties[1],
            'notes': 'تحویل',
        }, user=self.user)
        publish_handover(handover, user=self.user)
        for inv in handover.invitations.all():
            nid = inv.national_id or (inv.handover.snapshot_json.get('delivered_by', {}).get('national_id') if inv.side == 'delivered_by' else inv.handover.snapshot_json.get('received_by', {}).get('national_id')) or '1111111111'
            accept_handover(
                inv, phone=inv.mobile, national_id=nid,
                ack_checkboxes=['a'], otp_already_verified=True,
            )
        handover.refresh_from_db()
        self.assertEqual(handover.status, 'finalized')
        self.assertTrue(handover.is_locked)

    def test_handover_only_after_finalize(self):
        c = create_contract(self.user, CONTRACT_TYPE_SALE, deal_id=self.deal.pk)
        from contracts.services.handover import HandoverError
        with self.assertRaises(HandoverError):
            create_handover(self.user, c.pk)

    def test_parse_skips_empty_keys_and_equipment(self):
        from django.http import QueryDict
        from contracts.services.handover_parse import parse_handover_step

        c = create_contract(self.user, CONTRACT_TYPE_SALE, deal_id=self.deal.pk)
        c.status = 'finalized'
        c.save(update_fields=['status'])
        handover = create_handover(self.user, c.pk)
        keys = QueryDict(mutable=True)
        keys.update({
            'key_0_type': 'کلید واحد',
            'key_0_count': '2',
            'key_1_type': 'کلید انباری',
            'key_1_count': '0',
        })
        parsed = parse_handover_step(keys, 'keys', handover)
        self.assertEqual(parsed['keys'], [{'type': 'کلید واحد', 'count': 2, 'notes': ''}])

        eq = QueryDict(mutable=True)
        eq.update({
            'eq_0_name': 'پکیج',
            'eq_0_count': '1',
            'eq_0_status': 'ok',
            'eq_1_name': '',
            'eq_1_count': '1',
            'eq_1_status': 'ok',
        })
        parsed_eq = parse_handover_step(eq, 'equipment', handover)
        self.assertEqual(len(parsed_eq['equipment']), 1)
        self.assertEqual(parsed_eq['equipment'][0]['name'], 'پکیج')

    def test_wizard_renders_saved_values_and_mobile_nav(self):
        from contracts.services.handover_wizard import build_handover_wizard_context

        c = create_contract(self.user, CONTRACT_TYPE_SALE, deal_id=self.deal.pk)
        c.status = 'finalized'
        c.save(update_fields=['status'])
        handover = create_handover(self.user, c.pk)
        snap = dict(handover.snapshot_json or {})
        snap['parties'] = [
            {'role': 'seller', 'first_name': 'علی', 'last_name': 'فروشنده', 'mobile': '09121111111', 'national_id': '1111111111'},
            {'role': 'buyer', 'first_name': 'رضا', 'last_name': 'خریدار', 'mobile': '09122222222', 'national_id': '2222222222'},
        ]
        snap['property'] = {'address': 'تهران، نیاوران', 'property_type': 'آپارتمان', 'area': 120}
        handover.snapshot_json = snap
        handover.save(update_fields=['snapshot_json'])
        save_handover_step(handover, 'keys', {
            'keys': [{'type': 'کلید واحد', 'count': 3, 'notes': 'یدک'}],
        })
        save_handover_step(handover, 'meters', {
            'meters': [
                {'utility': 'electricity', 'meter_number': '123', 'reading': '4500', 'notes': ''},
                {'utility': 'water', 'meter_number': '', 'reading': '', 'notes': ''},
                {'utility': 'gas', 'meter_number': '', 'reading': '', 'notes': ''},
            ],
        })
        ctx = build_handover_wizard_context(handover, step='keys')
        self.assertEqual(ctx['step_number'], 2)
        self.assertEqual(ctx['next_step'], 'meters')
        unit_key = next(row for row in ctx['key_rows'] if row['type'] == 'کلید واحد')
        self.assertEqual(unit_key['count'], 3)

        self.client.force_login(self.user)
        url = reverse('workspace:handover_wizard', kwargs={
            'deal_id': self.deal.pk, 'contract_id': c.pk, 'handover_id': handover.pk,
        })
        keys_page = self.client.get(url + '?step=keys')
        self.assertEqual(keys_page.status_code, 200)
        self.assertContains(keys_page, 'کلیدها و دسترسی‌ها')
        self.assertContains(keys_page, 'value="3"')
        self.assertContains(keys_page, 'تأیید و ادامه')

        meters_page = self.client.get(url + '?step=meters')
        self.assertContains(meters_page, '4500')
        self.assertContains(meters_page, 'قرائت کنتور')

        review = self.client.get(url + '?step=review')
        self.assertContains(review, 'ارسال برای تأیید طرفین')
        self.assertContains(review, 'علی فروشنده')
        self.assertContains(review, 'رضا خریدار')
        self.assertContains(review, 'خلاصه تحویل')

