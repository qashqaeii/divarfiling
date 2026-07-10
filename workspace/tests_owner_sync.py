"""تست همگام‌سازی مالک ملک با مخاطبین CRM."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import (
    CRMProperty, Customer, CustomerListing, Dataset, Listing, PropertyContact,
)
from workspace.services.crm import (
    add_listing_to_personal_files,
    find_customer_by_phone,
    upsert_property_owner,
)
from workspace.services.listing_edit import owner_name_from_listing, owner_phone_from_listing

User = get_user_model()


class UpsertPropertyOwnerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09120001122', password='test')
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='تست مالک',
            original_filename='t.xlsx',
            file_format='xlsx',
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='tok-owner-1',
            title='آپارتمان تست',
            price=5_000_000_000,
            area=80,
            data={},
        )

    def test_upsert_creates_contact_and_listing_link(self):
        customer = upsert_property_owner(
            self.user,
            phone='09121234567',
            name='علی رضایی',
            listing=self.listing,
            source='دیوار',
        )
        self.assertIsNotNone(customer)
        self.assertEqual(customer.name, 'علی رضایی')
        self.assertEqual(customer.phone, '09121234567')
        self.assertEqual(customer.customer_type, 'مالک')
        self.assertEqual(owner_phone_from_listing(self.listing), '09121234567')
        self.assertEqual(owner_name_from_listing(self.listing), 'علی رضایی')
        self.assertTrue(
            CustomerListing.objects.filter(
                customer=customer, token='tok-owner-1', role='مالک',
            ).exists()
        )

    def test_upsert_reuses_existing_contact_by_phone(self):
        existing = Customer.objects.create(
            user=self.user,
            name='مالک قبلی',
            phone='09129876543',
            customer_type='سرنخ',
        )
        customer = upsert_property_owner(
            self.user,
            phone='09129876543',
            name='مالک به‌روز',
            listing=self.listing,
        )
        self.assertEqual(customer.pk, existing.pk)
        existing.refresh_from_db()
        self.assertEqual(existing.name, 'مالک به‌روز')
        self.assertEqual(existing.customer_type, 'مالک')
        self.assertEqual(Customer.objects.filter(user=self.user).count(), 1)

    def test_upsert_on_property_links_property_contact(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='فایل شخصی',
            deal_mode='فروش',
        )
        customer = upsert_property_owner(
            self.user,
            phone='09121112233',
            name='سارا محمدی',
            crm_property=prop,
        )
        prop.refresh_from_db()
        self.assertEqual(prop.phone, '09121112233')
        self.assertEqual(prop.owner_name, 'سارا محمدی')
        link = PropertyContact.objects.get(customer=customer, property=prop, role='مالک')
        self.assertTrue(link.is_primary)

    def test_convert_listing_to_personal_syncs_owner(self):
        self.listing.data = {'شماره تماس': '09123334455', 'نام مالک': 'رضا کریمی'}
        self.listing.save(update_fields=['data'])
        prop, created = add_listing_to_personal_files(self.user, self.listing)
        self.assertTrue(created)
        self.assertEqual(prop.phone, '09123334455')
        self.assertEqual(prop.owner_name, 'رضا کریمی')
        customer = find_customer_by_phone(self.user, '09123334455')
        self.assertIsNotNone(customer)
        self.assertTrue(
            PropertyContact.objects.filter(
                customer=customer, property=prop, role='مالک',
            ).exists()
        )

    def test_empty_phone_clears_fields_without_contact(self):
        upsert_property_owner(
            self.user,
            phone='09125556677',
            name='موقت',
            listing=self.listing,
        )
        before = Customer.objects.filter(user=self.user).count()
        result = upsert_property_owner(
            self.user,
            phone='',
            name='',
            listing=self.listing,
        )
        self.assertIsNone(result)
        self.assertEqual(owner_phone_from_listing(self.listing), '')
        self.assertEqual(Customer.objects.filter(user=self.user).count(), before)

    def test_second_edit_does_not_duplicate_owner(self):
        first = upsert_property_owner(
            self.user,
            phone='09121234567',
            name='علی رضایی',
            listing=self.listing,
        )
        second = upsert_property_owner(
            self.user,
            phone='09121234567',
            name='علی رضایی ویرایش',
            listing=self.listing,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Customer.objects.filter(user=self.user).count(), 1)
        self.assertEqual(
            CustomerListing.objects.filter(token='tok-owner-1', role='مالک').count(),
            1,
        )
        second.refresh_from_db()
        self.assertEqual(second.name, 'علی رضایی ویرایش')

    def test_second_edit_with_persian_digits_reuses_owner(self):
        first = upsert_property_owner(
            self.user,
            phone='09129876543',
            name='سارا',
            listing=self.listing,
        )
        second = upsert_property_owner(
            self.user,
            phone='۰۹۱۲۹۸۷۶۵۴۳',
            name='سارا محمدی',
            listing=self.listing,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Customer.objects.filter(user=self.user).count(), 1)

    def test_second_edit_on_property_does_not_duplicate_link(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='فایل شخصی',
            deal_mode='فروش',
        )
        first = upsert_property_owner(
            self.user,
            phone='09121112233',
            name='مالک یک',
            crm_property=prop,
        )
        second = upsert_property_owner(
            self.user,
            phone='09121112233',
            name='مالک یک به‌روز',
            crm_property=prop,
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            PropertyContact.objects.filter(property=prop, role='مالک').count(),
            1,
        )
        self.assertEqual(Customer.objects.filter(user=self.user).count(), 1)

    def test_edit_owner_phone_updates_same_contact_in_place(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='فایل شخصی ۲',
            deal_mode='فروش',
        )
        first = upsert_property_owner(
            self.user,
            phone='09120001111',
            name='مالک',
            crm_property=prop,
        )
        second = upsert_property_owner(
            self.user,
            phone='09120002222',
            name='مالک',
            crm_property=prop,
        )
        self.assertEqual(first.pk, second.pk)
        second.refresh_from_db()
        self.assertEqual(second.phone, '09120002222')
        self.assertEqual(Customer.objects.filter(user=self.user).count(), 1)
        self.assertEqual(
            PropertyContact.objects.filter(property=prop, role='مالک').count(),
            1,
        )
