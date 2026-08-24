"""Tests for CRM property feature_data and create-time images."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from workspace.forms import CRMPropertyForm
from workspace.models import CRMProperty
from workspace.services.property_features import (
    CRM_FEATURE_FORM_KEYS,
    parse_feature_data_from_post,
    resolve_feature_profile,
    sync_total_floors_from_feature_data,
)

User = get_user_model()


class FeatureProfileResolveTests(TestCase):
    def test_resolve_by_deal_and_type(self):
        self.assertEqual(resolve_feature_profile('رهن و اجاره', 'آپارتمان'), 'rent')
        self.assertEqual(resolve_feature_profile('اجاره', 'ویلا'), 'rent')
        self.assertEqual(resolve_feature_profile('فروش', 'آپارتمان'), 'sale')
        self.assertEqual(resolve_feature_profile('پیش‌فروش', 'آپارتمان'), 'sale')
        self.assertEqual(resolve_feature_profile('فروش', 'اداری'), 'commercial')
        self.assertEqual(resolve_feature_profile('رهن و اجاره', 'مغازه'), 'commercial')


class CRMPropertyFeatureDataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='featprop', password='x')
        self.client = Client()
        self.client.login(username='featprop', password='x')

    def test_form_saves_sale_feature_chips_and_floors(self):
        form = CRMPropertyForm(data={
            'title': 'آپارتمان تست',
            'property_type': 'آپارتمان',
            'deal_mode': 'فروش',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'feat_profile': 'sale',
            'feat__جنس کف': 'پارکت',
            'feat__گرمایش': 'شوفاژ',
            'feat__تعداد واحد در طبقه': '4',
            'feat__تعداد کل طبقات ساختمان': '12',
            'feat__نوع سند': 'تک‌برگ',
            'feat__بالکن': 'دارد',
        })
        self.assertTrue(form.is_valid(), form.errors)
        prop = form.save(commit=False)
        prop.user = self.user
        prop.save()
        prop.refresh_from_db()
        self.assertEqual(prop.feature_data.get('جنس کف'), 'پارکت')
        self.assertEqual(prop.feature_data.get('گرمایش'), 'شوفاژ')
        self.assertEqual(prop.feature_data.get('تعداد واحد در طبقه'), '4')
        self.assertEqual(prop.feature_data.get('تعداد کل طبقات ساختمان'), '12')
        self.assertEqual(prop.feature_data.get('نوع سند'), 'تک‌برگ')
        self.assertEqual(prop.feature_data.get('بالکن'), 'دارد')
        self.assertEqual(prop.total_floors, 12)
        self.assertIn('بالکن', prop.amenities or '')
        for key in ('جنس کف', 'گرمایش', 'تعداد واحد در طبقه', 'نوع سند'):
            self.assertIn(key, CRM_FEATURE_FORM_KEYS)

    def test_rent_profile_toggles_default_off(self):
        form = CRMPropertyForm(data={
            'title': 'اجاره تست',
            'property_type': 'آپارتمان',
            'deal_mode': 'رهن و اجاره',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'feat_profile': 'rent',
            'feat__مناسب برای': 'خانواده',
            'feat__مبله': 'دارد',
            # unchecked toggles omitted → ندارد
        })
        self.assertTrue(form.is_valid(), form.errors)
        prop = form.save(commit=False)
        prop.user = self.user
        prop.save()
        prop.refresh_from_db()
        self.assertEqual(prop.feature_data.get('مناسب برای'), 'خانواده')
        self.assertEqual(prop.feature_data.get('مبله'), 'دارد')
        self.assertEqual(prop.feature_data.get('بالکن'), 'ندارد')
        self.assertEqual(prop.feature_data.get('استخر'), 'ندارد')
        self.assertNotIn('نوع سند', prop.feature_data)

    def test_commercial_profile_fields(self):
        form = CRMPropertyForm(data={
            'title': 'دفتر تست',
            'property_type': 'اداری',
            'deal_mode': 'فروش',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'feat_profile': 'commercial',
            'feat__نوع کاربری ملک': 'پزشکی',
            'feat__وضعیت سند': 'آزاد',
            'feat__اتاق مدیریت': 'دارد',
            'feat__تعداد خط تلفن': '3',
            'feat__جنس کف': 'سرامیک',  # outside commercial profile — ignored
        })
        self.assertTrue(form.is_valid(), form.errors)
        prop = form.save(commit=False)
        prop.user = self.user
        prop.save()
        prop.refresh_from_db()
        self.assertEqual(prop.feature_data.get('نوع کاربری ملک'), 'پزشکی')
        self.assertEqual(prop.feature_data.get('وضعیت سند'), 'آزاد')
        self.assertEqual(prop.feature_data.get('اتاق مدیریت'), 'دارد')
        self.assertEqual(prop.feature_data.get('تعداد خط تلفن'), '3')
        self.assertNotIn('جنس کف', prop.feature_data)

    def test_parse_keeps_other_profile_keys_on_switch(self):
        existing = {'نوع سند': 'تک‌برگ', 'جنس کف': 'سرامیک'}
        data = {
            'feat_profile': 'rent',
            'feat__مناسب برای': 'مجرد',
            'feat__بالکن': 'دارد',
        }
        out = parse_feature_data_from_post(
            data, deal_mode='اجاره', property_type='آپارتمان', existing=existing,
        )
        self.assertEqual(out.get('مناسب برای'), 'مجرد')
        self.assertEqual(out.get('بالکن'), 'دارد')
        # sale-only key preserved when switching to rent
        self.assertEqual(out.get('نوع سند'), 'تک‌برگ')

    def test_sync_total_floors(self):
        self.assertEqual(sync_total_floors_from_feature_data({'تعداد کل طبقات ساختمان': '8'}), 8)
        self.assertIsNone(sync_total_floors_from_feature_data({}))

    def test_amenity_groups_hide_feature_managed_duplicates(self):
        from workspace.services.property_features import FEATURE_MANAGED_AMENITY_LABELS

        prop = CRMProperty.objects.create(
            user=self.user,
            title='بدون تکرار',
            deal_mode='فروش',
            property_type='آپارتمان',
            amenities='استخر، پارکینگ، بالکن',
            has_parking=True,
        )
        form = CRMPropertyForm(instance=prop)
        labels = {
            item['label']
            for group in form.amenity_checkbox_groups()
            for item in group['items']
        }
        self.assertIn('پارکینگ', labels)
        self.assertIn('روف گاردن', labels)
        for managed in FEATURE_MANAGED_AMENITY_LABELS:
            self.assertNotIn(managed, labels)
        # سوییچ ویژگی از امکانات قدیمی seed شده
        ctx = form.feature_form_context()
        rent_or_sale_items = {
            item['key']: item
            for group in ctx['groups']
            for item in group['items']
        }
        self.assertTrue(rent_or_sale_items.get('استخر', {}).get('checked'))
        self.assertTrue(rent_or_sale_items.get('بالکن', {}).get('checked'))

    def test_vacancy_date_jalali_normalized(self):
        from workspace.services.jalali_input import to_persian_digits
        from workspace.services.property_features import normalize_feature_date_value

        # ISO (legacy html date) → شمسی
        self.assertEqual(
            normalize_feature_date_value('2026-07-18'),
            to_persian_digits('1405/04/27'),
        )
        form = CRMPropertyForm(data={
            'title': 'اجاره تاریخ',
            'property_type': 'آپارتمان',
            'deal_mode': 'رهن و اجاره',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'feat_profile': 'rent',
            'feat__تاریخ تخلیه': '1405/04/27',
        })
        self.assertTrue(form.is_valid(), form.errors)
        prop = form.save(commit=False)
        prop.user = self.user
        prop.save()
        prop.refresh_from_db()
        self.assertEqual(
            prop.feature_data.get('تاریخ تخلیه'),
            to_persian_digits('1405/04/27'),
        )

    def test_occupancy_vacancy_date_on_sale_property(self):
        from workspace.services.jalali_input import to_persian_digits

        form = CRMPropertyForm(data={
            'title': 'فروش با تاریخ تخلیه',
            'property_type': 'آپارتمان',
            'deal_mode': 'فروش',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'feat_profile': 'sale',
            'feat__تاریخ تخلیه': '1405/06/09',
        })
        self.assertTrue(form.is_valid(), form.errors)
        prop = form.save(commit=False)
        prop.user = self.user
        prop.save()
        prop.refresh_from_db()
        self.assertEqual(
            prop.feature_data.get('تاریخ تخلیه'),
            to_persian_digits('1405/06/09'),
        )
        groups = form.feature_form_groups()
        rent_terms_items = [
            item['key']
            for profile in form.feature_form_context()['all_profiles']
            for group in profile['groups']
            if group['id'] == 'rent_terms'
            for item in group['items']
        ]
        self.assertNotIn('تاریخ تخلیه', rent_terms_items)

    def test_create_view_with_feature_and_image_url(self):
        url = reverse('workspace:crm_property_create')
        resp = self.client.post(url, {
            'title': 'ملک با عکس',
            'property_type': 'آپارتمان',
            'deal_mode': 'فروش',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'feat_profile': 'sale',
            'feat__جنس کابینت': 'MDF',
            'feat__نمای ساختمان': 'سنگ',
            'property_images_json': '["https://example.com/a.jpg"]',
        })
        self.assertEqual(resp.status_code, 302)
        prop = CRMProperty.objects.get(user=self.user, title='ملک با عکس')
        self.assertEqual(prop.feature_data.get('جنس کابینت'), 'MDF')
        self.assertEqual(prop.feature_data.get('نمای ساختمان'), 'سنگ')
        self.assertEqual(prop.images, ['https://example.com/a.jpg'])

    def test_create_view_with_uploaded_file(self):
        jpeg = SimpleUploadedFile(
            't.jpg',
            b'\xff\xd8\xff\xe0' + b'\x00' * 200,
            content_type='image/jpeg',
        )
        url = reverse('workspace:crm_property_create')
        resp = self.client.post(url, {
            'title': 'ملک آپلود',
            'property_type': 'آپارتمان',
            'deal_mode': 'فروش',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'property_image_files': jpeg,
        })
        self.assertEqual(resp.status_code, 302)
        prop = CRMProperty.objects.get(user=self.user, title='ملک آپلود')
        self.assertTrue(prop.images)
        self.assertTrue(str(prop.images[0]).startswith('/media/') or 'http' in str(prop.images[0]))

    def test_property_feature_profile_includes_feature_data(self):
        from workspace.services.property_public_share import _property_feature_profile

        prop = CRMProperty.objects.create(
            user=self.user,
            title='پرونده',
            feature_data={'سرمایش': 'اسپلیت', 'جنس کف': 'سرامیک'},
        )
        profile = _property_feature_profile(self.user, prop, {})
        labels = {
            item['label']
            for group in profile.get('groups') or []
            for item in group.get('items') or []
        }
        self.assertIn('سیستم سرمایش', labels)
        self.assertIn('جنس کف', labels)
        self.assertTrue(profile.get('has_details'))
