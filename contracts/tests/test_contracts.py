"""تست‌های قرارداد دیجیتال."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from contracts.constants import CONTRACT_TYPE_LEASE
from contracts.services.tokens import hash_token
from contracts.services.hashing import compute_content_hash
from contracts.services.lifecycle import (
    ContractError,
    create_contract,
    prepare_for_send,
    save_wizard_step,
)
from contracts.services.otp_service import hash_otp_code
from contracts.services.scope import contract_for_user, contracts_qs
from workspace.models import CRMDeal, CRMProperty, Customer

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

    def test_create_contract_prefills_data(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
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
        c = create_contract(self.user, deal.pk, CONTRACT_TYPE_LEASE)
        party = c.current_version.parties.filter(role='tenant').first()
        self.assertIsNotNone(party)
        self.assertEqual(party.company_national_id, '10123456789')
        self.assertEqual(party.national_id, '')

    def test_permission_scope(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        self.assertIsNotNone(contract_for_user(self.user, c.pk))
        self.assertIsNone(contract_for_user(self.other, c.pk))

    def test_content_hash_changes(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
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

    def test_idor_manage_view(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
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

    def test_lease_validation_requires_witnesses(self):
        c = create_contract(self.user, self.deal.pk, CONTRACT_TYPE_LEASE)
        wizard = dict(c.wizard_data)
        wizard['financial'] = {
            'monthly_rent': 10000000, 'deposit': 100000000,
            'lease_start': '1404/01/01', 'lease_end': '1405/01/01',
        }
        wizard['witnesses'] = []
        c.wizard_data = wizard
        c.save()
        with self.assertRaises(ContractError):
            prepare_for_send(c, user=self.user)


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
