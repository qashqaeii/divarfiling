"""Tests for CRM property feature_data and create-time images."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from workspace.forms import CRMPropertyForm
from workspace.models import CRMProperty
from workspace.services.property_features import CRM_FEATURE_FORM_KEYS

User = get_user_model()


class CRMPropertyFeatureDataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='featprop', password='x')
        self.client = Client()
        self.client.login(username='featprop', password='x')

    def test_form_saves_feature_data_from_feat_fields(self):
        form = CRMPropertyForm(data={
            'title': 'آپارتمان تست',
            'property_type': 'آپارتمان',
            'deal_mode': 'فروش',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'feat__جنس کف': 'پارکت',
            'feat__گرمایش': 'پکیج',
            'feat__تعداد واحد در طبقه': '۴',
            'feat__تعداد کل طبقات ساختمان': '۱۲',  # skip — should not persist
        })
        self.assertTrue(form.is_valid(), form.errors)
        prop = form.save(commit=False)
        prop.user = self.user
        prop.save()
        prop.refresh_from_db()
        self.assertEqual(prop.feature_data.get('جنس کف'), 'پارکت')
        self.assertEqual(prop.feature_data.get('گرمایش'), 'پکیج')
        self.assertEqual(prop.feature_data.get('تعداد واحد در طبقه'), '۴')
        self.assertNotIn('تعداد کل طبقات ساختمان', prop.feature_data)
        for key in ('جنس کف', 'گرمایش', 'تعداد واحد در طبقه'):
            self.assertIn(key, CRM_FEATURE_FORM_KEYS)

    def test_create_view_with_feature_and_image_url(self):
        url = reverse('workspace:crm_property_create')
        resp = self.client.post(url, {
            'title': 'ملک با عکس',
            'property_type': 'آپارتمان',
            'deal_mode': 'فروش',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'feat__جنس کابینت': 'ام‌دی‌اف',
            'feat__نمای ساختمان': 'سنگ',
            'property_images_json': '["https://example.com/a.jpg"]',
        })
        self.assertEqual(resp.status_code, 302)
        prop = CRMProperty.objects.get(user=self.user, title='ملک با عکس')
        self.assertEqual(prop.feature_data.get('جنس کابینت'), 'ام‌دی‌اف')
        self.assertEqual(prop.feature_data.get('نمای ساختمان'), 'سنگ')
        self.assertEqual(prop.images, ['https://example.com/a.jpg'])

    def test_create_view_with_uploaded_file(self):
        # minimal valid jpeg header bytes
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
        self.assertIn('سرمایش', labels)
        self.assertIn('جنس کف', labels)
        self.assertTrue(profile.get('has_details'))
