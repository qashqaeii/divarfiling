"""تست‌های مستاجر فعلی روی ملک اجاره."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.forms import CRMPropertyForm
from workspace.models import CRMProperty, Customer, PropertyContact
from workspace.services.crm import upsert_property_tenant


class TenantFormCleanTests(TestCase):
    def test_vacant_clears_tenant_fields(self):
        form = CRMPropertyForm(data={
            'title': 'ملک اجاره',
            'property_type': 'آپارتمان',
            'deal_mode': 'اجاره',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'is_vacant': 'on',
            'tenant_name': 'علی رضایی',
            'tenant_phone': '09121234567',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['tenant_name'], '')
        self.assertEqual(form.cleaned_data['tenant_phone'], '')

    def test_occupied_keeps_tenant_fields(self):
        form = CRMPropertyForm(data={
            'title': 'ملک اجاره',
            'property_type': 'آپارتمان',
            'deal_mode': 'اجاره',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'tenant_name': 'علی رضایی',
            'tenant_phone': '09121234567',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['tenant_name'], 'علی رضایی')
        self.assertTrue(form.cleaned_data['tenant_phone'])


class UpsertPropertyTenantTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='tenant_crm', password='x')
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان اجاره',
            property_type='آپارتمان',
            deal_mode='اجاره',
            is_vacant=False,
        )

    def test_creates_customer_and_link(self):
        customer = upsert_property_tenant(
            self.user,
            phone='09121112233',
            name='سارا محمدی',
            crm_property=self.prop,
        )
        self.assertIsNotNone(customer)
        self.assertEqual(customer.customer_type, 'مستاجر')
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.tenant_name, 'سارا محمدی')
        link = PropertyContact.objects.get(property=self.prop, role='مستاجر')
        self.assertEqual(link.customer_id, customer.pk)
        self.assertTrue(link.is_primary)

    def test_vacant_removes_tenant_link(self):
        upsert_property_tenant(
            self.user,
            phone='09121112233',
            name='سارا محمدی',
            crm_property=self.prop,
        )
        self.assertEqual(PropertyContact.objects.filter(property=self.prop, role='مستاجر').count(), 1)

        self.prop.is_vacant = True
        self.prop.save(update_fields=['is_vacant', 'updated_at'])
        upsert_property_tenant(
            self.user,
            phone='',
            name='',
            crm_property=self.prop,
        )
        self.assertEqual(PropertyContact.objects.filter(property=self.prop, role='مستاجر').count(), 0)
        self.assertEqual(Customer.objects.filter(user=self.user, customer_type='مستاجر').count(), 1)


class MobilePropertyTenantSyncTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='mobile_tenant', password='x')
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='ملک موبایل',
            property_type='آپارتمان',
            deal_mode='اجاره',
            is_vacant=False,
        )

    def test_update_property_from_mobile_creates_tenant_contact(self):
        from mobile_api.services.properties_service import update_property_from_mobile

        updated = update_property_from_mobile(
            self.user,
            self.prop.pk,
            {
                'tenant_name': 'رضا کریمی',
                'tenant_phone': '09123334455',
                'is_vacant': False,
            },
        )
        self.assertIsNotNone(updated)
        link = PropertyContact.objects.get(property=self.prop, role='مستاجر')
        self.assertEqual(link.customer.name, 'رضا کریمی')
        self.assertEqual(link.customer.phone, '09123334455')
        self.assertEqual(link.customer.customer_type, 'مستاجر')
        self.assertTrue(link.is_primary)
