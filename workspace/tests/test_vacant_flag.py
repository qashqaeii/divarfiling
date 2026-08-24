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

    def test_sale_keeps_vacant(self):
        form = CRMPropertyForm(data={
            'title': 'ملک فروش',
            'property_type': 'آپارتمان',
            'deal_mode': 'فروش',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'is_vacant': 'on',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(form.cleaned_data['is_vacant'])
        self.assertEqual(form.cleaned_data['tenant_name'], '')

    def test_sale_keeps_tenant_when_not_vacant(self):
        form = CRMPropertyForm(data={
            'title': 'ملک فروش',
            'property_type': 'آپارتمان',
            'deal_mode': 'فروش',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'tenant_name': 'سارا',
            'tenant_phone': '09121112233',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.cleaned_data['is_vacant'])
        self.assertEqual(form.cleaned_data['tenant_name'], 'سارا')
        self.assertEqual(form.cleaned_data['tenant_phone'], '09121112233')


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

    def test_tenant_fields_optional_when_not_vacant(self):
        apply_listing_edit_post(self.listing, {
            'is_vacant': ['0'],
            'tenant_name': 'علی رضایی',
            'tenant_phone': '09121234567',
        })
        self.listing.save()
        self.listing.refresh_from_db()
        payload = listing_edit_payload(self.listing)
        self.assertFalse(payload['is_vacant'])
        self.assertEqual(payload['tenant_name'], 'علی رضایی')
        self.assertEqual(payload['tenant_phone'], '09121234567')

        apply_listing_edit_post(self.listing, {
            'is_vacant': ['0', '1'],
            'tenant_name': 'باید پاک شود',
            'tenant_phone': '09120000000',
        })
        self.listing.save()
        self.listing.refresh_from_db()
        payload = listing_edit_payload(self.listing)
        self.assertTrue(payload['is_vacant'])
        self.assertEqual(payload['tenant_name'], '')
        self.assertEqual(payload['tenant_phone'], '')

    def test_vacancy_date_optional_jalali(self):
        from workspace.services.jalali_input import to_persian_digits

        apply_listing_edit_post(self.listing, {
            'is_vacant': ['0'],
            'vacancy_date': '1405/04/27',
        })
        self.listing.save()
        self.listing.refresh_from_db()
        payload = listing_edit_payload(self.listing)
        self.assertEqual(payload['vacancy_date'], to_persian_digits('1405/04/27'))
        self.assertEqual(self.listing.data.get('تاریخ تخلیه'), to_persian_digits('1405/04/27'))

        apply_listing_edit_post(self.listing, {
            'is_vacant': ['0', '1'],
            'vacancy_date': '1405/04/27',
        })
        self.listing.save()
        self.listing.refresh_from_db()
        payload = listing_edit_payload(self.listing)
        self.assertTrue(payload['is_vacant'])
        self.assertEqual(payload['vacancy_date'], to_persian_digits('1405/04/27'))

        apply_listing_edit_post(self.listing, {'vacancy_date': ''})
        self.listing.save()
        self.listing.refresh_from_db()
        payload = listing_edit_payload(self.listing)
        self.assertEqual(payload['vacancy_date'], '')
        self.assertNotIn('تاریخ تخلیه', self.listing.data or {})

    def test_vacancy_date_json_edit(self):
        from workspace.services.jalali_input import to_persian_digits
        from workspace.services.listing_edit import apply_listing_edit_json

        apply_listing_edit_json(self.listing, {'vacancy_date': '1405/04/27'})
        self.listing.save()
        self.listing.refresh_from_db()
        self.assertEqual(
            listing_edit_payload(self.listing)['vacancy_date'],
            to_persian_digits('1405/04/27'),
        )

    def test_vacancy_date_not_in_extra_profile_group(self):
        from workspace.services.jalali_input import to_persian_digits
        from workspace.services.listing_features import build_listing_feature_profile

        self.listing.data = {
            **(self.listing.data or {}),
            'تاریخ تخلیه': to_persian_digits('1405/06/09'),
            'vacancy_date': to_persian_digits('1405/06/09'),
        }
        self.listing.save()
        profile = build_listing_feature_profile(self.listing)
        all_items = [item for g in profile['groups'] for item in g['items']]
        all_keys = {item['key'] for item in all_items}
        self.assertNotIn('vacancy_date', all_keys)
        lifestyle = next(g for g in profile['groups'] if g['id'] == 'lifestyle')
        vac_item = next(i for i in lifestyle['items'] if i['label'] == 'تاریخ تخلیه')
        self.assertEqual(vac_item['value'], to_persian_digits('1405/06/09'))
