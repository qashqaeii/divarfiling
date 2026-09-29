"""تست فیلد جنسیت مخاطب — backward compatible."""
from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pandas as pd
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from ai_workspace.providers.base import ProviderResult
from ai_workspace.services.nl_command.service import confirm_command, parse_command
from ai_workspace.services.nl_command.state import load_state
from mobile_api.services.crm_service import create_customer_from_nl
from workspace.forms import CustomerForm
from workspace.models import Customer
from workspace.services.contact_gender import normalize_contact_gender_import
from workspace.services.crm import customers_to_export_rows
from workspace.services.crm_import import import_contacts_from_file

User = get_user_model()


class ContactGenderModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='genderuser', password='test')

    def test_legacy_contact_has_null_gender(self):
        c = Customer.objects.create(
            user=self.user,
            name='قدیمی',
            phone='09120001111',
            customer_type='سرنخ',
            status='جدید',
        )
        c.refresh_from_db()
        self.assertIsNone(c.gender)

    def test_create_without_gender(self):
        form = CustomerForm({
            'name': 'بدون جنسیت',
            'phone': '09122223333',
            'customer_type': 'سرنخ',
            'status': 'جدید',
            'priority': 'متوسط',
            'gender': '',
        }, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.user = self.user
        customer = form.save()
        self.assertIsNone(customer.gender)

    def test_create_female_male(self):
        cases = (
            ('female', '09121111001'),
            ('male', '09121111002'),
        )
        for value, phone in cases:
            form = CustomerForm({
                'name': f'تست {value}',
                'phone': phone,
                'customer_type': 'خریدار',
                'status': 'جدید',
                'priority': 'متوسط',
                'gender': value,
            }, user=self.user)
            self.assertTrue(form.is_valid(), form.errors)
            form.instance.user = self.user
            self.assertEqual(form.save().gender, value)

    def test_legal_entity_clears_gender(self):
        form = CustomerForm({
            'name': 'شرکت الف',
            'phone': '09124445566',
            'customer_type': 'اشخاص حقوقی',
            'status': 'جدید',
            'priority': 'متوسط',
            'gender': 'male',
            'is_legal_entity': True,
            'company_name': 'الف',
        }, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.instance.user = self.user
        customer = form.save()
        self.assertIsNone(customer.gender)


class ContactGenderImportExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='importuser', password='test')

    def test_import_without_gender_column(self):
        df = pd.DataFrame([{
            'نام': 'Import بدون جنسیت',
            'تلفن': '09126667788',
        }])
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine='openpyxl')
        buf.seek(0)
        created, skipped, errors = import_contacts_from_file(
            self.user,
            SimpleUploadedFile('c.xlsx', buf.read(), content_type='application/vnd.ms-excel'),
        )
        self.assertEqual(errors, [])
        self.assertEqual(created, 1)
        self.assertIsNone(Customer.objects.get(name='Import بدون جنسیت').gender)

    def test_import_with_gender_aliases(self):
        df = pd.DataFrame([
            {'نام': 'خانم الف', 'تلفن': '09127770001', 'جنسیت': 'خانم'},
            {'نام': 'آقا ب', 'تلفن': '09127770002', 'جنسیت': 'male'},
            {'نام': 'نامشخص', 'تلفن': '09127770003', 'جنسیت': 'نامعلوم'},
        ])
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine='openpyxl')
        buf.seek(0)
        created, _, _ = import_contacts_from_file(
            self.user,
            SimpleUploadedFile('c.xlsx', buf.read(), content_type='application/vnd.ms-excel'),
        )
        self.assertEqual(created, 3)
        self.assertEqual(Customer.objects.get(name='خانم الف').gender, 'female')
        self.assertEqual(Customer.objects.get(name='آقا ب').gender, 'male')
        self.assertIsNone(Customer.objects.get(name='نامشخص').gender)

    def test_export_includes_gender_column(self):
        Customer.objects.create(
            user=self.user,
            name='Export',
            phone='09128889999',
            customer_type='سرنخ',
            status='جدید',
            gender='female',
        )
        rows = customers_to_export_rows(Customer.objects.filter(user=self.user))
        self.assertEqual(rows[0]['جنسیت'], 'خانم')


class ContactGenderApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09129998877', password='test')
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.customer = Customer.objects.create(
            user=self.user,
            name='API قدیمی',
            phone='09129998877',
            customer_type='خریدار',
            status='جدید',
        )

    def test_get_legacy_contact_null_gender(self):
        resp = self.client.get(f'/api/mobile/v1/crm/contacts/{self.customer.pk}')
        self.assertEqual(resp.status_code, 200)
        contact = resp.json()['data']['contact']
        self.assertIn('gender', contact)
        self.assertIsNone(contact['gender'])

    def test_patch_gender_and_invalid(self):
        ok = self.client.patch(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}',
            {'gender': 'female'},
            format='json',
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()['data']['gender'], 'female')
        bad = self.client.patch(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}',
            {'gender': 'other'},
            format='json',
        )
        self.assertEqual(bad.status_code, 400)

    def test_patch_without_gender_field_unchanged(self):
        self.customer.gender = 'male'
        self.customer.save(update_fields=['gender'])
        resp = self.client.patch(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}',
            {'job': 'مهندس'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.gender, 'male')
        self.assertEqual(self.customer.job, 'مهندس')


@override_settings(AI_ENABLED=True)
class ContactGenderNlTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='nluser', password='test', is_staff=True)

    def _patch_chain(self, payload: str):
        provider = MagicMock()
        provider.complete.return_value = ProviderResult(
            text=payload,
            provider='arvan',
            model='test',
            input_tokens=5,
            output_tokens=20,
            latency_ms=50,
            is_fallback=False,
        )
        return patch('ai_workspace.services.gateway.get_http_provider_chain', return_value=[provider])

    def test_create_contact_with_explicit_gender(self):
        payload = json.dumps({
            'intent': 'create_contact',
            'confidence': 0.9,
            'data': {
                'name': 'نسترن احمدی',
                'customer_type': 'خریدار',
                'profile': {'gender': 'female', 'job': None, 'is_legal_entity': None, 'company_name': None},
                'contact': {'phone': '09121234567', 'phone_alt': None, 'email': None},
            },
            'missing_fields': [],
            'ambiguous_fields': [],
            'requires_confirmation': True,
        }, ensure_ascii=False)
        with self._patch_chain(payload):
            parsed = parse_command(self.user, text='خانم نسترن احمدی 09121234567')
        self.assertEqual(parsed['intent'], 'create_contact')
        state = load_state(self.user.pk, parsed['command_id'])
        self.assertEqual(state['validated']['gender'], 'female')
        out = confirm_command(self.user, parsed['command_id'])
        self.assertTrue(out['ok'])
        customer = Customer.objects.get(name='نسترن احمدی')
        self.assertEqual(customer.gender, 'female')

    def test_create_customer_from_nl_without_gender(self):
        customer = create_customer_from_nl(self.user, {
            'name': 'علی',
            'phone': '09123334444',
            'customer_type': 'خریدار',
        })
        self.assertIsNone(customer.gender)


class ContactGenderHelperTests(TestCase):
    def test_normalize_import(self):
        self.assertEqual(normalize_contact_gender_import('آقا'), 'male')
        self.assertIsNone(normalize_contact_gender_import('invalid'))
