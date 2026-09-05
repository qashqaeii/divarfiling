"""تست‌های Phase 2 — hardening و business-critical paths."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from contracts.constants import (
    CONTRACT_STATUS_DRAFT,
    CONTRACT_STATUS_FINALIZED,
    CONTRACT_STATUS_READY,
    CONTRACT_STATUS_SENT,
    CONTRACT_TYPE_LEASE,
    CONTRACT_TYPE_SALE,
    VERIFICATION_MISMATCH_MSG,
)
from contracts.models import Contract, ContractAcceptance, ContractInvitation, ContractVersion
from contracts.services.hashing import build_version_snapshot, compute_content_hash
from contracts.services.lifecycle import (
    ContractError,
    create_contract,
    create_new_version,
    finalize_contract,
    prepare_for_send,
    save_wizard_step,
)
from contracts.services.state_machine import InvalidStateTransition, transition_contract
from contracts.services.tokens import generate_bearer_token, hash_token, lookup_invitation
from contracts.services.version_copy import copy_version_entities, version_display_snapshot
from workspace.models import CRMDeal, CRMProperty, Customer

User = get_user_model()


def _lease_wizard_data():
    return {
        'parties': [
            {'role': 'landlord', 'first_name': 'علی', 'last_name': 'الف', 'mobile': '09121111111', 'national_id': '1111111111'},
            {'role': 'tenant', 'first_name': 'رضا', 'last_name': 'ب', 'mobile': '09122222222', 'national_id': '2222222222'},
        ],
        'property': {'address': 'تهران', 'area': 100},
        'financial': {
            'lease_start': '1404/01/01', 'lease_end': '1405/01/01',
            'deposit': 500000000, 'monthly_rent': 15000000, 'rent_payment_day': 1,
        },
        'witnesses': [
            {'witness_number': 1, 'first_name': 'ش1', 'last_name': 'ش', 'mobile': '09123333333', 'national_id': '3333333333'},
            {'witness_number': 2, 'first_name': 'ش2', 'last_name': 'ش', 'mobile': '09124444444', 'national_id': '4444444444'},
        ],
        'selected_clauses': [{'is_custom': True, 'title': 'بند تست', 'body_text': 'متن تست'}],
    }


class ContractTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u1', phone='09120000001', password='x')
        self.other = User.objects.create_user(username='u2', phone='09120000002', password='x')
        self.customer = Customer.objects.create(user=self.user, name='مشتری', phone='09125555555')
        self.prop = CRMProperty.objects.create(
            user=self.user, title='ملک', address='تهران',
            deposit=500000000, monthly_rent=15000000,
        )
        self.deal = CRMDeal.objects.create(
            user=self.user, customer=self.customer, property=self.prop,
            title='معامله', deal_kind='rent',
        )


class HashingTests(ContractTestBase):
    def test_same_content_same_hash(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        for k, v in _lease_wizard_data().items():
            save_wizard_step(c, k if k != 'selected_clauses' else 'clauses', v, user=self.user)
        v = c.current_version
        h1 = compute_content_hash(v)
        h2 = compute_content_hash(v)
        self.assertEqual(h1, h2)

    def test_price_change_changes_hash(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        data = _lease_wizard_data()
        save_wizard_step(c, 'financial', data['financial'], user=self.user)
        h1 = compute_content_hash(c.current_version)
        data['financial']['monthly_rent'] = 20000000
        save_wizard_step(c, 'financial', data['financial'], user=self.user)
        h2 = compute_content_hash(c.current_version)
        self.assertNotEqual(h1, h2)

    def test_party_change_changes_hash(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        save_wizard_step(c, 'parties', _lease_wizard_data()['parties'], user=self.user)
        h1 = compute_content_hash(c.current_version)
        parties = _lease_wizard_data()['parties']
        parties[0]['first_name'] = 'محمد'
        save_wizard_step(c, 'parties', parties, user=self.user)
        self.assertNotEqual(h1, compute_content_hash(c.current_version))


class VersionSnapshotTests(ContractTestBase):
    def test_v1_unchanged_after_v2(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        wd = _lease_wizard_data()
        for step in ('parties', 'property', 'financial', 'witnesses'):
            save_wizard_step(c, step, wd[step], user=self.user)
        save_wizard_step(c, 'clauses', wd['selected_clauses'], user=self.user)
        v1 = c.current_version
        prepare_for_send(c, user=self.user)
        v1.refresh_from_db()
        snap_v1 = dict(v1.snapshot_json)
        hash_v1 = v1.content_hash

        v2 = create_new_version(c, user=self.user)
        self.assertNotEqual(v2.pk, v1.pk)
        parties = wd['parties'] + [
            {'role': 'landlord', 'first_name': 'جدید', 'last_name': 'فروشنده', 'mobile': '09126666666'},
        ]
        save_wizard_step(c, 'parties', parties, user=self.user)

        v1.refresh_from_db()
        self.assertEqual(v1.content_hash, hash_v1)
        self.assertEqual(len(v1.snapshot_json.get('parties', [])), len(snap_v1.get('parties', [])))

    def test_published_version_uses_snapshot_json(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        wd = _lease_wizard_data()
        for step in ('parties', 'property', 'financial', 'witnesses', 'clauses'):
            save_wizard_step(c, step, wd.get(step) or wd['selected_clauses'], user=self.user)
        prepare_for_send(c, user=self.user)
        v = c.current_version
        original_parties = len(v.snapshot_json['parties'])
        v.parties.all().delete()
        display = version_display_snapshot(v)
        self.assertEqual(len(display['parties']), original_parties)


class StateMachineTests(ContractTestBase):
    def test_invalid_transition_blocked(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        with self.assertRaises(InvalidStateTransition):
            transition_contract(c, CONTRACT_STATUS_FINALIZED)

    def test_cancelled_cannot_send(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        transition_contract(c, 'cancelled')
        with self.assertRaises(ContractError):
            prepare_for_send(c, user=self.user)


class TokenSecurityTests(ContractTestBase):
    def test_token_stored_as_hash(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        self.assertTrue(c.verification_token_hash)
        self.assertEqual(len(c.verification_token_hash), 64)

    def test_invitation_lookup_requires_raw(self):
        raw, th = generate_bearer_token()
        wd = _lease_wizard_data()
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        for step in ('parties', 'property', 'financial', 'witnesses', 'clauses'):
            save_wizard_step(c, step, wd.get(step) or wd['selected_clauses'], user=self.user)
        prepare_for_send(c, user=self.user)
        v = c.current_version
        inv = ContractInvitation.objects.create(
            contract=c, version=v, token_hash=th,
            mobile='09121111111', expires_at=timezone.now() + timedelta(days=1),
        )
        self.assertIsNotNone(lookup_invitation(raw))
        self.assertIsNone(lookup_invitation('wrong-token'))


class PendingClausesTests(ContractTestBase):
    def test_production_includes_active_pending(self):
        from contracts.models import ContractClauseDefinition
        from contracts.services.clauses import get_applicable_clauses
        ContractClauseDefinition.objects.create(
            code='TEST_PENDING', title='t', category='c', contract_type='lease',
            body_template='x', review_status='review_pending', is_active=True,
        )
        with self.settings(DEBUG=False, LEGAL_REVIEW_PREVIEW=False):
            clauses = get_applicable_clauses('lease', user=self.user)
            codes = [c.code for c in clauses]
            self.assertIn('TEST_PENDING', codes)


class IDORTests(ContractTestBase):
    def test_other_user_cannot_access_wizard(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        client = Client()
        client.force_login(self.other)
        url = reverse('workspace:contract_wizard', kwargs={'deal_id': self.deal.pk, 'contract_id': c.pk})
        self.assertEqual(client.get(url).status_code, 404)


class AcceptanceHashTests(ContractTestBase):
    def test_acceptance_stores_content_hash(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        wd = _lease_wizard_data()
        for step in ('parties', 'property', 'financial', 'witnesses', 'clauses'):
            save_wizard_step(c, step, wd.get(step) or wd['selected_clauses'], user=self.user)
        prepare_for_send(c, user=self.user)
        v = c.current_version
        acc = ContractAcceptance.objects.create(
            contract=c, version=v, content_hash=v.content_hash,
            accepted_content_hash=v.content_hash,
            mobile='09121111111', otp_verified_at=timezone.now(),
        )
        self.assertTrue(acc.is_hash_valid())


class ImmutableVersionTests(ContractTestBase):
    def test_cannot_edit_after_publish(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        wd = _lease_wizard_data()
        for step in ('parties', 'property', 'financial', 'witnesses', 'clauses'):
            save_wizard_step(c, step, wd.get(step) or wd['selected_clauses'], user=self.user)
        prepare_for_send(c, user=self.user)
        with self.assertRaises(Exception):
            save_wizard_step(c, 'parties', [], user=self.user)


class PrivacyTests(TestCase):
    def test_mismatch_message_is_generic(self):
        self.assertIn('مطابقت', VERIFICATION_MISMATCH_MSG)
        self.assertNotIn('کد ملی صحیح', VERIFICATION_MISMATCH_MSG)


class LegalRuleTests(ContractTestBase):
    def test_future_rule_excluded(self):
        from contracts.models import ContractLegalRule
        from contracts.services.clauses import get_active_legal_rules
        future = timezone.localdate() + timedelta(days=30)
        ContractLegalRule.objects.create(
            code='FUTURE_RULE', name='آینده', contract_type='lease',
            rule_type='warning', status='active',
            effective_from=future, warning_message='x',
        )
        codes = [r.code for r in get_active_legal_rules('lease')]
        self.assertNotIn('FUTURE_RULE', codes)

    def test_expired_rule_excluded(self):
        from contracts.models import ContractLegalRule
        from contracts.services.clauses import get_active_legal_rules
        past = timezone.localdate() - timedelta(days=60)
        ContractLegalRule.objects.create(
            code='EXPIRED_RULE', name='منقضی', contract_type='lease',
            rule_type='warning', status='active',
            effective_to=past, warning_message='x',
        )
        codes = [r.code for r in get_active_legal_rules('lease')]
        self.assertNotIn('EXPIRED_RULE', codes)


class LeaseE2ETests(ContractTestBase):
    @patch('contracts.services.invitations.send_simple_sms')
    @patch('contracts.services.pdf.generate_contract_pdf')
    def test_lease_full_flow(self, mock_pdf, mock_sms):
        from contracts.constants import CONTRACT_STATUS_FINALIZED
        from contracts.services.acceptance import accept_contract
        from contracts.services.invitations import send_invitations

        mock_sms.return_value = type('R', (), {'message_id': '1'})()
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        wd = _lease_wizard_data()
        for step in ('parties', 'property', 'financial', 'witnesses', 'clauses'):
            save_wizard_step(c, step, wd.get(step) or wd['selected_clauses'], user=self.user)
        prepare_for_send(c, user=self.user)
        send_invitations(c, user=self.user, request=None)

        ack = ['not_official', 'internal_id']
        for inv in ContractInvitation.objects.filter(contract=c, is_revoked=False):
            accept_contract(
                inv, phone=inv.mobile,
                national_id=inv.party.national_id if inv.party_id else inv.witness.national_id,
                ack_checkboxes=ack, otp_already_verified=True,
            )

        c.refresh_from_db()
        self.assertEqual(c.status, CONTRACT_STATUS_FINALIZED)
        self.assertTrue(c.finalized_at)
        mock_pdf.assert_called()


class FinalizeIdempotencyTests(ContractTestBase):
    def test_accept_with_drawn_signature_bytesio(self):
        import io

        from contracts.services.acceptance import accept_contract
        from contracts.services.invitations import send_invitations

        with patch('contracts.services.invitations.send_simple_sms'), \
             patch('contracts.services.pdf.generate_contract_pdf'):
            c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
            wd = _lease_wizard_data()
            for step in ('parties', 'property', 'financial', 'witnesses', 'clauses'):
                save_wizard_step(c, step, wd.get(step) or wd['selected_clauses'], user=self.user)
            prepare_for_send(c, user=self.user)
            send_invitations(c, user=self.user)
            inv = ContractInvitation.objects.filter(contract=c, is_revoked=False).first()
            sig = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'0' * 32)
            sig.name = 'signature.png'
            acceptance = accept_contract(
                inv,
                phone=inv.mobile,
                national_id=inv.party.national_id if inv.party_id else inv.witness.national_id,
                ack_checkboxes=['a'],
                signature_image=sig,
                otp_already_verified=True,
            )
            self.assertTrue(acceptance.signature.image)

    def test_double_finalize_is_idempotent(self):
        from contracts.constants import CONTRACT_STATUS_FINALIZED
        from contracts.services.acceptance import accept_contract
        from contracts.services.invitations import send_invitations

        with patch('contracts.services.invitations.send_simple_sms'), \
             patch('contracts.services.pdf.generate_contract_pdf'):
            c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
            wd = _lease_wizard_data()
            for step in ('parties', 'property', 'financial', 'witnesses', 'clauses'):
                save_wizard_step(c, step, wd.get(step) or wd['selected_clauses'], user=self.user)
            prepare_for_send(c, user=self.user)
            send_invitations(c, user=self.user)
            for inv in ContractInvitation.objects.filter(contract=c):
                accept_contract(
                    inv, phone=inv.mobile,
                    national_id=inv.party.national_id if inv.party_id else inv.witness.national_id,
                    ack_checkboxes=['not_official'], otp_already_verified=True,
                )
            c.refresh_from_db()
            v = c.current_version
            v.refresh_from_db()
            hash_before = v.content_hash
            self.assertEqual(c.status, CONTRACT_STATUS_FINALIZED)
            finalize_contract(c)
            v.refresh_from_db()
            self.assertEqual(v.content_hash, hash_before)


class AuditSanitizationTests(TestCase):
    def test_sensitive_metadata_stripped(self):
        from contracts.services.audit import log_audit_event, _sanitize_metadata
        cleaned = _sanitize_metadata({'token': 'secret', 'invitation_id': 5})
        self.assertNotIn('token', cleaned)
        self.assertEqual(cleaned['invitation_id'], 5)

    def test_audit_event_persian_labels(self):
        from contracts.services.audit import audit_event_label
        self.assertEqual(audit_event_label('PARTY_ACCEPTED'), 'تأیید قرارداد توسط طرف')
        self.assertEqual(audit_event_label('CONTRACT_UPDATED'), 'به‌روزرسانی قرارداد')
        self.assertNotIn('CONTRACT_', audit_event_label('SMS_SENT'))
