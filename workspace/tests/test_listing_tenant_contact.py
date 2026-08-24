"""تست پیوند مستاجر آگهی فایلینگ به مخاطب CRM."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CustomerListing, Dataset, Listing
from workspace.services.crm import upsert_listing_tenant
from workspace.services.listing_edit import apply_listing_edit_post
from workspace.services.listing_features import build_listing_feature_profile


class ListingTenantContactTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='listing_tenant',
            password='x',
            phone='09121110011',
        )
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='تست',
            transaction_type='اجاره',
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='test-token-tenant',
            title='اجاره دوبلکس',
            rent=70_000_000,
            deposit=900_000_000,
        )

    def test_upsert_listing_tenant_creates_contact_link(self):
        apply_listing_edit_post(self.listing, {
            'tenant_name': 'سعیدی پور',
            'tenant_phone': '09166333333',
            'vacancy_date': '1405/07/02',
        })
        self.listing.save()

        customer = upsert_listing_tenant(
            self.user,
            phone='09166333333',
            name='سعیدی پور',
            listing=self.listing,
            is_vacant=False,
        )
        self.assertIsNotNone(customer)
        self.assertEqual(customer.customer_type, 'مستاجر')
        link = CustomerListing.objects.get(customer=customer, token=self.listing.token)
        self.assertEqual(link.role, 'مستاجر')

    def test_tenant_name_english_key_hidden_from_extra_profile(self):
        self.listing.data = {
            'tenant_name': 'سعیدی پور',
            'نام مستاجر': 'سعیدی پور',
            'شماره مستاجر': '09166333333',
            'تاریخ تخلیه': '۱۴۰۵/۰۷/۰۲',
        }
        self.listing.save()
        profile = build_listing_feature_profile(self.listing)
        all_keys = {item['key'] for g in profile['groups'] for item in g['items']}
        self.assertNotIn('tenant_name', all_keys)
        self.assertNotIn('tenant_phone', all_keys)
        lifestyle = next(g for g in profile['groups'] if g['id'] == 'lifestyle')
        labels = {item['label'] for item in lifestyle['items']}
        self.assertIn('نام مستاجر', labels)
        self.assertIn('شماره مستاجر', labels)

    def test_apply_tenant_fields_drops_english_duplicate_keys(self):
        apply_listing_edit_post(self.listing, {
            'tenant_name': 'علی رضایی',
            'tenant_phone': '09121234567',
        })
        data = self.listing.data or {}
        self.assertEqual(data.get('نام مستاجر'), 'علی رضایی')
        self.assertEqual(data.get('شماره مستاجر'), '09121234567')
        self.assertNotIn('tenant_name', data)
        self.assertNotIn('tenant_phone', data)
