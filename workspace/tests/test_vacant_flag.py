"""تست‌های پرچم تخلیه برای CRM و فایلینگ."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.forms import CRMPropertyForm
from workspace.models import CRMProperty, Dataset, Listing
from workspace.services.features import extract_listing_features
from workspace.services.listing_edit import (
    apply_listing_edit_post,
    apply_vacant_flag_to_data,
    listing_edit_payload,
    listing_is_vacant,
)


class VacantFlagHelpersTests(TestCase):
    def test_listing_is_vacant_from_data(self):
        ds = Dataset(transaction_type='اجاره')
        listing = Listing(dataset=ds, token='v1', title='x', data={'وضعیت سکونت': 'تخلیه'})
        self.assertTrue(listing_is_vacant(listing))
        listing.data = {'وضعیت سکونت': 'در اختیار مستأجر'}
        self.assertFalse(listing_is_vacant(listing))

    def test_apply_vacant_flag_sets_and_clears(self):
        data = {}
        apply_vacant_flag_to_data(data, True)
        self.assertEqual(data.get('وضعیت سکونت'), 'تخلیه')
        apply_vacant_flag_to_data(data, False)
        self.assertNotIn('وضعیت سکونت', data)


class CRMPropertyVacantFormTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='vacant_crm', password='x')

    def test_rent_keeps_vacant(self):
        form = CRMPropertyForm(data={
            'title': 'ملک اجاره',
            'property_type': 'آپارتمان',
            'deal_mode': 'اجاره',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'is_vacant': 'on',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.cleaned_data['is_vacant'])

    def test_sale_clears_vacant(self):
        form = CRMPropertyForm(data={
            'title': 'ملک فروش',
            'property_type': 'آپارتمان',
            'deal_mode': 'فروش',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'is_vacant': 'on',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data['is_vacant'])


class ListingVacantEditTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='vacant_ls', password='x')
        self.ds = Dataset.objects.create(
            user=self.user, name='اجاره', original_filename='a.xlsx',
            file_format='xlsx', transaction_type='اجاره', row_count=1,
        )
        self.listing = Listing.objects.create(
            dataset=self.ds, token='vt1', title='آگهی اجاره',
            deposit=500_000_000, data={},
        )

    def test_payload_and_apply(self):
        payload = listing_edit_payload(self.listing)
        self.assertTrue(payload['is_rent'])
        self.assertFalse(payload['is_vacant'])

        apply_listing_edit_post(self.listing, {'is_vacant': ['0', '1']})
        self.listing.save()
        self.listing.refresh_from_db()
        self.assertTrue(listing_is_vacant(self.listing))
        self.assertTrue(extract_listing_features(self.listing)['is_vacant'])

        apply_listing_edit_post(self.listing, {'is_vacant': ['0']})
        self.listing.save()
        self.listing.refresh_from_db()
        self.assertFalse(listing_is_vacant(self.listing))
