"""Tests for extended CRM property specs (postal, land area, frontage, booleans)."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.forms import CRMPropertyForm
from workspace.models import CRMProperty
from workspace.services.property_features import CHOICES_FACADE

User = get_user_model()


class CRMPropertyExtendedFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='extprop', password='x')

    def _base_form_data(self, **extra):
        data = {
            'title': 'ملک تست',
            'property_type': 'ویلا',
            'deal_mode': 'فروش',
            'transaction_status': 'فعال',
            'publish_status': 'پیش‌نویس',
            'feat_profile': 'sale',
        }
        data.update(extra)
        return data

    def test_create_with_extended_fields(self):
        data = self._base_form_data(
            postal_code='۱۲۳۴۵۶۷۸۹۰',
            area='120',
            land_area='350',
            frontage_width='12.5',
            has_wardrobe='on',
            has_two_corner='on',
            has_wallpaper='on',
        )
        data['feat__نمای ساختمان'] = 'سرامیک'
        form = CRMPropertyForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        prop = form.save(commit=False)
        prop.user = self.user
        prop.save()
        prop.refresh_from_db()
        self.assertEqual(prop.postal_code, '1234567890')  # normalized from Persian digits
        self.assertEqual(prop.feature_data.get('کد پستی'), '1234567890')
        self.assertEqual(prop.area, 120.0)
        self.assertEqual(prop.land_area, 350.0)
        self.assertEqual(prop.frontage_width, 12.5)
        self.assertTrue(prop.has_wardrobe)
        self.assertTrue(prop.has_two_corner)
        self.assertTrue(prop.has_wallpaper)
        self.assertEqual(prop.feature_data.get('نمای ساختمان'), 'سرامیک')

    def test_optional_fields_blank(self):
        form = CRMPropertyForm(data=self._base_form_data())
        self.assertTrue(form.is_valid(), form.errors)
        prop = form.save(commit=False)
        prop.user = self.user
        prop.save()
        prop.refresh_from_db()
        self.assertEqual(prop.postal_code, '')
        self.assertIsNone(prop.land_area)
        self.assertFalse(prop.has_knauf)

    def test_frontage_must_be_positive(self):
        form = CRMPropertyForm(data=self._base_form_data(frontage_width='0'))
        self.assertFalse(form.is_valid())
        self.assertIn('frontage_width', form.errors)

    def test_legacy_property_edit_loads_postal_from_feature_data(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='قدیمی',
            feature_data={'کد پستی': '1122334455'},
        )
        form = CRMPropertyForm(instance=prop)
        self.assertEqual(form.initial.get('postal_code'), '1122334455')

    def test_create_and_edit_street_field(self):
        form = CRMPropertyForm(data=self._base_form_data(street='  خ ولیعصر  '))
        self.assertTrue(form.is_valid(), form.errors)
        prop = form.save(commit=False)
        prop.user = self.user
        prop.save()
        prop.refresh_from_db()
        self.assertEqual(prop.feature_data.get('خیابان'), 'خ ولیعصر')
        self.assertEqual(prop.feature_data.get('مکان_خیابان'), 'خ ولیعصر')
        edit = CRMPropertyForm(instance=prop)
        self.assertEqual(edit.initial.get('street'), 'خ ولیعصر')
        clear = CRMPropertyForm(data=self._base_form_data(street=''), instance=prop)
        self.assertTrue(clear.is_valid(), clear.errors)
        cleared = clear.save()
        cleared.refresh_from_db()
        self.assertNotIn('خیابان', cleared.feature_data or {})
        self.assertNotIn('مکان_خیابان', cleared.feature_data or {})

    def test_ceramic_in_facade_choices(self):
        self.assertIn('سرامیک', CHOICES_FACADE)


class CRMPropertyExtendedApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09125556677', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_mobile_create_and_read_extended_fields(self):
        resp = self.client.post(
            '/api/mobile/v1/crm/properties',
            {
                'title': 'ملک API',
                'deal_mode': 'فروش',
                'postal_code': '1987654321',
                'street': 'خ شریعتی',
                'area': 90,
                'land_area': 200,
                'frontage_width': 10,
                'has_two_access': True,
                'has_lighting': True,
                'feature_data': {'نمای ساختمان': 'سرامیک'},
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        prop_id = resp.json()['data']['id']
        detail = self.client.get(f'/api/mobile/v1/crm/properties/{prop_id}')
        self.assertEqual(detail.status_code, 200)
        body = detail.json()['data']['property']
        self.assertEqual(body['postal_code'], '1987654321')
        self.assertEqual(body['street'], 'خ شریعتی')
        self.assertEqual(body['feature_data'].get('خیابان'), 'خ شریعتی')
        self.assertEqual(body['land_area'], 200.0)
        self.assertEqual(body['frontage_width'], 10.0)
        self.assertTrue(body['has_two_access'])
        self.assertTrue(body['has_lighting'])
        self.assertEqual(body['feature_data'].get('نمای ساختمان'), 'سرامیک')

    def test_legacy_property_detail_without_new_fields(self):
        prop = CRMProperty.objects.create(user=self.user, title='بدون فیلد جدید', area=50)
        detail = self.client.get(f'/api/mobile/v1/crm/properties/{prop.pk}')
        self.assertEqual(detail.status_code, 200)
        body = detail.json()['data']['property']
        self.assertEqual(body['area'], 50.0)
        self.assertEqual(body['postal_code'], '')
        self.assertFalse(body['has_wallpaper'])
