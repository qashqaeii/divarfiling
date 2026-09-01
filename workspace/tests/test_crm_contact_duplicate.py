"""جلوگیری از ثبت تکراری مخاطب بر اساس نام و شماره."""
import io

from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.forms import CustomerForm, QuickLeadForm
from workspace.models import Customer
from workspace.services.crm_merge import find_duplicate_contact
from workspace.services.crm_import import import_contacts_from_file
from mobile_api.services.crm_service import create_quick_lead, update_contact

User = get_user_model()


class CRMContactDuplicateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dupuser', password='test')
        self.existing = Customer.objects.create(
            user=self.user,
            name='علی رضایی',
            phone='09121234567',
            customer_type='سرنخ',
            status='جدید',
        )

    def test_find_duplicate_contact_matches_name_and_phone(self):
        dup = find_duplicate_contact(self.user, 'علی رضایی', '09121234567')
        self.assertEqual(dup, self.existing)

    def test_find_duplicate_contact_ignores_different_name(self):
        dup = find_duplicate_contact(self.user, 'محمد احمدی', '09121234567')
        self.assertIsNone(dup)

    def test_find_duplicate_contact_ignores_different_phone(self):
        dup = find_duplicate_contact(self.user, 'علی رضایی', '09129876543')
        self.assertIsNone(dup)

    def test_find_duplicate_contact_normalizes_phone(self):
        dup = find_duplicate_contact(self.user, 'علی رضایی', '+98 912 123 4567')
        self.assertEqual(dup, self.existing)

    def test_find_duplicate_contact_excludes_self_on_update(self):
        dup = find_duplicate_contact(
            self.user,
            self.existing.name,
            self.existing.phone,
            exclude_pk=self.existing.pk,
        )
        self.assertIsNone(dup)

    def test_customer_form_blocks_duplicate_create(self):
        form = CustomerForm({
            'name': 'علی رضایی',
            'phone': '09121234567',
            'customer_type': 'سرنخ',
            'status': 'جدید',
            'priority': 'متوسط',
        }, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('قبلاً در مخاطبین ثبت شده', str(form.errors))

    def test_quick_lead_form_blocks_duplicate(self):
        form = QuickLeadForm({
            'name': 'علی رضایی',
            'phone': '09121234567',
            'source': '',
        }, user=self.user)
        self.assertFalse(form.is_valid())

    def test_create_quick_lead_raises_on_duplicate(self):
        with self.assertRaises(ValueError) as ctx:
            create_quick_lead(self.user, {'name': 'علی رضایی', 'phone': '09121234567'})
        self.assertIn('قبلاً', str(ctx.exception))

    def test_update_contact_blocks_duplicate_phone_and_name(self):
        other = Customer.objects.create(
            user=self.user,
            name='سارا محمدی',
            phone='09131112222',
            customer_type='سرنخ',
            status='جدید',
        )
        with self.assertRaises(ValueError):
            update_contact(self.user, other.pk, {
                'name': 'علی رضایی',
                'phone': '09121234567',
            })

    def test_import_skips_name_phone_duplicate(self):
        class DummyUpload(io.BytesIO):
            name = 'contacts.csv'

        csv_content = (
            'نام,تلفن\n'
            'علی رضایی,09121234567\n'
            'جدید,09129998888\n'
        ).encode('utf-8-sig')
        created, skipped, errors = import_contacts_from_file(
            self.user,
            DummyUpload(csv_content),
        )
        self.assertEqual(created, 1)
        self.assertEqual(skipped, 1)
        self.assertEqual(errors, [])
