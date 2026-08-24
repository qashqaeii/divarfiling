"""تست فیلدهای اختیاری مخاطب و مهلت اجاره شمسی."""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.forms import CustomerForm
from workspace.models import Customer
from workspace.services.jalali_input import format_jalali_date, parse_jalali_date_string

User = get_user_model()


class ContactOptionalFieldsFormTests(TestCase):
    def _base_data(self, **extra):
        data = {
            'name': 'متقاضی نمونه',
            'phone': '09121112222',
            'customer_type': 'متقاضی اجاره',
            'status': 'جدید',
            'priority': 'متوسط',
        }
        data.update(extra)
        return data

    def test_optional_fields_use_placeholder(self):
        form = CustomerForm()
        for name in ('email', 'city', 'district', 'job', 'company_name', 'national_id'):
            self.assertEqual(form.fields[name].widget.attrs.get('placeholder'), 'اختیاری')

    def test_optional_identity_fields_can_stay_empty(self):
        form = CustomerForm(self._base_data())
        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save(commit=False)
        customer.user = User.objects.create_user(username='09121112223', phone='09121112223', password='x')
        customer.save()
        self.assertEqual(customer.email, '')
        self.assertEqual(customer.city, '')
        self.assertEqual(customer.district, '')
        self.assertEqual(customer.job, '')
        self.assertEqual(customer.company_name, '')
        self.assertEqual(customer.national_id, '')
        self.assertIsNone(customer.lease_deadline)

    def test_lease_deadline_saves_jalali_date(self):
        form = CustomerForm(self._base_data(
            email='a@b.com',
            city='تهران',
            district='ونک',
            job='پزشک',
            company_name='شرکت نمونه',
            national_id='0012345678',
            lease_deadline='۱۴۰۵/۰۴/۲۷',
        ))
        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save(commit=False)
        customer.user = User.objects.create_user(username='09121112224', phone='09121112224', password='x')
        customer.save()
        expected = parse_jalali_date_string('1405/04/27')
        self.assertEqual(customer.lease_deadline, expected)
        self.assertEqual(customer.job, 'پزشک')
        self.assertEqual(customer.company_name, 'شرکت نمونه')
        self.assertEqual(customer.national_id, '0012345678')

    def test_lease_deadline_initial_is_jalali(self):
        user = User.objects.create_user(username='09121112225', phone='09121112225', password='x')
        customer = Customer.objects.create(
            user=user,
            name='مستاجر فعلی',
            phone='09121112225',
            customer_type='متقاضی اجاره',
            lease_deadline=date(2026, 7, 18),
        )
        form = CustomerForm(instance=customer)
        self.assertEqual(form.initial.get('lease_deadline'), format_jalali_date(date(2026, 7, 18)))
