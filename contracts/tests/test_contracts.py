"""تست‌های قرارداد دیجیتال."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from contracts.constants import CONTRACT_TYPE_LEASE, CONTRACT_TYPE_SALE
from accounts.services.otp import hash_otp_code
from contracts.services.tokens import hash_token
from contracts.services.hashing import compute_content_hash
from contracts.tests.helpers import grant_bot_license
from contracts.models import Contract
from contracts.services.lifecycle import (
    ContractError,
    create_contract,
    delete_draft_contract,
    prepare_for_send,
    save_wizard_step,
    validate_contract_ready,
)
from contracts.services.masking import mask_phone
from contracts.services.otp_service import CONTRACT_OTP_SMS_PURPOSE, request_contract_otp
from contracts.services.scope import contract_for_user, contracts_qs
from contracts.services.wizard_parse import parse_wizard_step
from workspace.models import CRMDeal, CRMProperty, Customer
from workspace.services.crm_deals import get_property_deal_parties_context, infer_recommended_contract_type

User = get_user_model()


class ContractModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u1', phone='09121111111', password='x')
        self.other = User.objects.create_user(username='u2', phone='09122222222', password='x')
        self.customer = Customer.objects.create(user=self.user, name='علی رضایی', phone='09123333333')
        self.prop = CRMProperty.objects.create(
            user=self.user, title='ملک تست', address='تهران',
            deposit=500000000, monthly_rent=15000000,
        )
        self.deal = CRMDeal.objects.create(
            user=self.user, customer=self.customer, property=self.prop,
            title='معامله تست', deal_kind='rent',
        )
        grant_bot_license(self.user)

    def test_create_contract_prefills_data(self):
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        self.assertTrue(c.internal_number.startswith('DF-RNT-'))
        self.assertEqual(c.deal_id, self.deal.pk)
        self.assertTrue(c.wizard_data.get('parties'))
        self.assertTrue(c.current_version_id)

    def test_create_contract_with_legal_entity_customer(self):
        legal_customer = Customer.objects.create(
            user=self.user,
            name='شرکت نمونه',
            phone='09129999999',
            is_legal_entity=True,
            company_name='شرکت نمونه',
            national_id='10123456789',
        )
        deal = CRMDeal.objects.create(
            user=self.user, customer=legal_customer, property=self.prop,
            title='معامله حقوقی', deal_kind='rent',
        )
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=deal.pk)
        party = c.current_version.parties.filter(role='tenant').first()
        self.assertIsNotNone(party)
        self.assertEqual(party.company_national_id, '10123456789')
        self.assertEqual(party.national_id, '')

    def test_permission_scope(self):
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        self.assertIsNotNone(contract_for_user(self.user, c.pk))
        self.assertIsNone(contract_for_user(self.other, c.pk))

    def test_content_hash_changes(self):
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        v = c.current_version
        h1 = compute_content_hash(v)
        save_wizard_step(c, 'financial', {'monthly_rent': 20000000, 'deposit': 500000000,
                                          'lease_start': '1404/01/01', 'lease_end': '1405/01/01'})
        v.refresh_from_db()
        h2 = compute_content_hash(v)
        self.assertNotEqual(h1, h2)


class ContractSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u1', phone='09121111111', password='x')
        self.other = User.objects.create_user(username='u2', phone='09122222222', password='x')
        self.customer = Customer.objects.create(user=self.user, name='مشتری', phone='09124444444')
        self.deal = CRMDeal.objects.create(user=self.user, customer=self.customer, title='دیل')
        grant_bot_license(self.user)

    def test_idor_manage_view(self):
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        client = Client()
        client.force_login(self.other)
        url = reverse('workspace:contract_manage', kwargs={'deal_id': self.deal.pk, 'contract_id': c.pk})
        resp = client.get(url)
        self.assertEqual(resp.status_code, 404)


class ContractVersioningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u1', phone='09121111111', password='x')
        self.customer = Customer.objects.create(user=self.user, name='مشتری', phone='09125555555')
        self.prop = CRMProperty.objects.create(
            user=self.user, title='ملک', deposit=100, monthly_rent=10,
        )
        self.deal = CRMDeal.objects.create(
            user=self.user, customer=self.customer, property=self.prop, title='دیل', deal_kind='rent',
        )
        grant_bot_license(self.user)

    def test_lease_send_without_witnesses(self):
        c = create_contract(self.user, CONTRACT_TYPE_LEASE, deal_id=self.deal.pk)
        wizard = dict(c.wizard_data)
        wizard['financial'] = {
            'monthly_rent': 10000000, 'deposit': 100000000,
            'lease_start': '1404/01/01', 'lease_end': '1405/01/01',
        }
        wizard['witnesses'] = []
        c.wizard_data = wizard
        c.save()
        save_wizard_step(c, 'parties', wizard['parties'], user=self.user)
        save_wizard_step(c, 'property', wizard.get('property') or {}, user=self.user)
        save_wizard_step(c, 'financial', wizard['financial'], user=self.user)
        errors = validate_contract_ready(c, c.current_version)
        self.assertNotIn('دو شاهد', ' '.join(errors))


class ContractOTPTests(TestCase):
    def test_otp_hash_storage(self):
        from contracts.models import Contract, ContractOTP, ContractVersion, ContractInvitation
        user = User.objects.create_user(username='u3', phone='09126666666', password='x')
        customer = Customer.objects.create(user=user, name='c', phone='09127777777')
        deal = CRMDeal.objects.create(user=user, customer=customer, title='d')
        contract = Contract.objects.create(
            user=user, deal=deal, contract_type='lease', internal_number='DF-RNT-1405-000001',
            verification_token_hash=hash_token('test-verify'),
        )
        version = ContractVersion.objects.create(contract=contract, version_number=1)
        inv = ContractInvitation.objects.create(
            contract=contract, version=version, mobile='09127777777',
            token_hash=hash_token('inv-token'),
            expires_at=timezone.now() + timedelta(days=1),
        )
        code = '123456'
        h = hash_otp_code(code, '09127777777', 'contract_acceptance')
        otp = ContractOTP.objects.create(
            invitation=inv, phone='09127777777', code_hash=h,
            expires_at=timezone.now() + timedelta(minutes=2),
        )
        self.assertNotIn('123456', otp.code_hash)
        self.assertEqual(len(otp.code_hash), 64)

    @override_settings(
        SMS_PROVIDER='console',
        FARAZSMS_PATTERNS={'contract_otp': 'qwcrSwFnxo'},
        FARAZSMS_OTP_ATTR='code',
    )
    @patch('contracts.services.otp_service.send_pattern_sms')
    def test_contract_otp_sent_via_pattern(self, mock_send):
        from contracts.models import Contract, ContractInvitation, ContractVersion

        mock_send.return_value = type('R', (), {'message_id': '1', 'provider': 'console'})()
        user = User.objects.create_user(username='u3b', phone='09126666661', password='x')
        customer = Customer.objects.create(user=user, name='c', phone='09127777771')
        deal = CRMDeal.objects.create(user=user, customer=customer, title='d')
        contract = Contract.objects.create(
            user=user, deal=deal, contract_type='lease', internal_number='DF-RNT-1405-000099',
            verification_token_hash=hash_token('test-verify-2'),
        )
        version = ContractVersion.objects.create(contract=contract, version_number=1)
        inv = ContractInvitation.objects.create(
            contract=contract, version=version, mobile='09127777771',
            token_hash=hash_token('inv-token-2'),
            expires_at=timezone.now() + timedelta(days=1),
        )
        request_contract_otp(inv, '09127777771')
        mock_send.assert_called_once()
        phone, = mock_send.call_args.args
        self.assertEqual(phone, '09127777771')
        self.assertEqual(mock_send.call_args.kwargs['purpose'], CONTRACT_OTP_SMS_PURPOSE)
        self.assertIn('code', mock_send.call_args.kwargs['attributes'])
        self.assertEqual(len(mock_send.call_args.kwargs['attributes']['code']), 6)


class ContractWizardUXTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u4', phone='09128888888', password='x')
        self.customer = Customer.objects.create(user=self.user, name='سعیدی', phone='09181232256')
        self.prop = CRMProperty.objects.create(
            user=self.user, title='ملک فروش', deal_mode='فروش', sale_price=100,
        )
        self.deal = CRMDeal.objects.create(
            user=self.user, customer=self.customer, property=self.prop,
            title='فروش ملک', deal_kind='sale',
        )
        grant_bot_license(self.user)

    def test_wizard_shows_full_phone_in_workspace(self):
        c = create_contract(self.user, CONTRACT_TYPE_SALE, deal_id=self.deal.pk)
        self.client.force_login(self.user)
        url = reverse('workspace:contract_wizard', kwargs={'deal_id': self.deal.pk, 'contract_id': c.pk})
        resp = self.client.get(url + '?step=parties')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '09181232256')
        self.assertNotContains(resp, '0918***2256')

    def test_public_mask_phone_unchanged(self):
        self.assertEqual(mask_phone('09181232256'), '0918***2256')

    def test_recommended_contract_type_for_sale_deal(self):
        self.assertEqual(infer_recommended_contract_type(self.deal), 'sale')

    def test_toman_words_teens_and_compound(self):
        from contracts.services.money import _toman_words
        words = _toman_words(125_215_151)
        self.assertIn('پانزده', words)
        self.assertNotIn('ده و پنج', words)
        self.assertTrue(words.endswith('تومان'))

    def test_toman_words_billion_scale(self):
        from contracts.services.money import _toman_words
        words = _toman_words(10_000_000_000)
        self.assertIn('میلیارد', words)
        self.assertTrue(words.endswith('تومان'))

    def test_wizard_property_select_parsing(self):
        c = create_contract(self.user, CONTRACT_TYPE_SALE, deal_id=self.deal.pk)
        data = parse_wizard_step({
            'prop_unit_direction': 'شمالی',
            'prop_facade_type': 'سنگ',
            'prop_floor_type': 'سرامیک',
            'prop_kitchen_type': 'اپن',
            'prop_heating': 'بخاری',
            'prop_cooling': 'اسپلیت',
            'prop_has_elevator': 'on',
        }, 'property', 'sale')
        self.assertEqual(data['unit_direction'], 'شمالی')
        self.assertEqual(data['facade_type'], 'سنگ')
        self.assertEqual(data['heating_system'], 'بخاری')
        self.assertTrue(data['has_elevator'])


class ContractWizardPickerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='picker_u', phone='09129990001', password='x')
        self.other = User.objects.create_user(username='picker_o', phone='09129990002', password='x')
        self.customer = Customer.objects.create(
            user=self.user, name='علی رضایی', phone='09121112233', national_id='1234567890',
        )
        self.prop = CRMProperty.objects.create(
            user=self.user, title='آپارتمان ونک', address='خیابان ولیعصر', area=95,
            neighborhood='ونک', city='تهران', has_parking=True,
        )
        Customer.objects.create(user=self.other, name='مخاطب دیگر', phone='09120000099')
        CRMProperty.objects.create(user=self.other, title='ملک دیگران', address='مخفی')
        grant_bot_license(self.user)

    def test_customer_search_scoped_to_user(self):
        self.client.force_login(self.user)
        url = reverse('workspace:contract_wizard_customer_search')
        resp = self.client.get(url, {'q': 'علی'})
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.json()['results']]
        self.assertIn(self.customer.pk, ids)
        self.assertNotIn(Customer.objects.get(user=self.other).pk, ids)

    def test_property_payload_mapping(self):
        from contracts.services.wizard_sources import wizard_property_payload

        payload = wizard_property_payload(self.user, self.prop.pk)
        self.assertIsNotNone(payload)
        self.assertEqual(payload['crm_property_id'], self.prop.pk)
        self.assertEqual(payload['address'], 'خیابان ولیعصر')
        self.assertTrue(payload['has_parking'])

    def test_wizard_persists_customer_id_in_parties(self):
        c = create_contract(self.user, CONTRACT_TYPE_LEASE)
        parties = parse_wizard_step({
            'party_0_role': 'landlord',
            'party_0_customer_id': str(self.customer.pk),
            'party_0_person_type': 'natural',
            'party_0_first_name': 'علی',
            'party_0_last_name': 'رضایی',
            'party_0_mobile': '09121112233',
            'party_1_role': 'tenant',
            'party_1_person_type': 'natural',
            'party_1_first_name': 'م',
            'party_1_last_name': 'م',
            'party_1_mobile': '09123334444',
        }, 'parties', 'lease')
        self.assertEqual(parties[0].get('customer_id'), self.customer.pk)

    def test_standalone_wizard_shows_picker_ui(self):
        c = create_contract(self.user, CONTRACT_TYPE_LEASE)
        self.client.force_login(self.user)
        url = reverse('workspace:contract_wizard_standalone', kwargs={'contract_id': c.pk})
        resp = self.client.get(url + '?step=parties')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'انتخاب از مخاطبین')
        self.assertContains(resp, 'data-enable-pickers="1"')
        self.assertContains(resp, 'data-ct-picker-search')
        self.assertContains(resp, 'data-crm-field-voice')
        self.assertContains(resp, 'data-crm-field-voice-mic')
        self.assertContains(resp, 'data-crm-field-voice-silence-ms="1000"')
        self.assertContains(resp, 'id="ct-wizard-form"')
        self.assertContains(resp, 'autocomplete="off"')
        self.assertContains(resp, 'party_0_last_name')
        self.assertContains(resp, 'autocomplete="family-name"')

    def test_customer_search_pagination_metadata(self):
        for i in range(25):
            Customer.objects.create(user=self.user, name=f'مخاطب {i:02d}', phone=f'0912000{i:04d}')
        self.client.force_login(self.user)
        url = reverse('workspace:contract_wizard_customer_search')
        first = self.client.get(url, {'limit': 10, 'offset': 0})
        self.assertEqual(first.status_code, 200)
        data = first.json()
        self.assertTrue(data['has_more'])
        self.assertEqual(len(data['results']), 10)
        self.assertEqual(data['next_offset'], 10)
        second = self.client.get(url, {'limit': 10, 'offset': data['next_offset']})
        self.assertEqual(len(second.json()['results']), 10)


class ContractDeleteDraftTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='del_u', phone='09129870001', password='x')
        grant_bot_license(self.user)

    def test_delete_draft_via_post(self):
        contract = create_contract(self.user, CONTRACT_TYPE_LEASE)
        self.client.force_login(self.user)
        url = reverse('workspace:contract_delete_draft_standalone', kwargs={'contract_id': contract.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIsNone(contract_for_user(self.user, contract.pk))

    def test_delete_draft_rejects_non_draft(self):
        contract = create_contract(self.user, CONTRACT_TYPE_SALE)
        Contract.objects.filter(pk=contract.pk).update(status='ready')
        self.client.force_login(self.user)
        url = reverse('workspace:contract_delete_draft_standalone', kwargs={'contract_id': contract.pk})
        self.client.post(url)
        self.assertIsNotNone(contract_for_user(self.user, contract.pk))

    def test_delete_draft_service_checks_status(self):
        contract = create_contract(self.user, CONTRACT_TYPE_LEASE)
        Contract.objects.filter(pk=contract.pk).update(status='ready')
        contract.refresh_from_db()
        with self.assertRaises(ContractError):
            delete_draft_contract(contract, user=self.user)

    def test_delete_cancelled_contract(self):
        contract = create_contract(self.user, CONTRACT_TYPE_LEASE)
        Contract.objects.filter(pk=contract.pk).update(status='cancelled')
        self.client.force_login(self.user)
        url = reverse('workspace:contract_delete_draft_standalone', kwargs={'contract_id': contract.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIsNone(contract_for_user(self.user, contract.pk))


class FinalViewContextTests(TestCase):
    def test_build_final_view_includes_document_when_verified(self):
        from contracts.models import Contract, ContractParty, ContractVersion
        from contracts.services.final_view_context import build_final_view_context

        user = User.objects.create_user(username='fv1', phone='09120000001', password='x')
        customer = Customer.objects.create(user=user, name='c', phone='09120000002')
        deal = CRMDeal.objects.create(user=user, customer=customer, title='d')
        contract = Contract.objects.create(
            user=user, deal=deal, contract_type='sale', internal_number='DF-SAL-1405-000010',
            verification_token_hash=hash_token('fv-verify'),
            status='finalized',
        )
        version = ContractVersion.objects.create(contract=contract, version_number=1, is_published=True)
        ContractParty.objects.create(
            contract=contract, version=version, role='seller',
            first_name='علی', last_name='احمدی', mobile='09121111111',
        )
        ContractParty.objects.create(
            contract=contract, version=version, role='buyer',
            first_name='رضا', last_name='کریمی', mobile='09122222222',
        )
        ctx_locked = build_final_view_context(contract, verified=False)
        self.assertEqual(ctx_locked['document_sections'], [])
        ctx = build_final_view_context(contract, verified=True)
        self.assertTrue(ctx['document_sections'])
        self.assertEqual(ctx['contract_meta']['internal_number'], contract.internal_number)
