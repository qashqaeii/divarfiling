"""تست اشتراک عمومی فایل شخصی CRM."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import CRMProperty, CRMPropertyPublicShare
from workspace.services.property_public_share import (
    build_public_property_context,
    get_or_create_property_share,
)

User = get_user_model()


class PropertyPublicShareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09129876543',
            phone='09129876543',
            password='testpass123',
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='ویلای ۲۰۰ متری',
            deal_mode='فروش',
            property_type='ویلا',
            city='تهران',
            neighborhood='نیاوران',
            sale_price=12_000_000_000,
            area=200,
            rooms='4',
            notes='یادداشت محرمانه',
            address='خیابان تست ۱۲',
        )
        self.client = Client()

    def test_get_or_create_share_is_idempotent(self):
        s1 = get_or_create_property_share(self.user, self.prop)
        s2 = get_or_create_property_share(self.user, self.prop)
        self.assertEqual(s1.pk, s2.pk)
        self.assertTrue(s1.share_token)

    def test_build_context_hides_notes_by_default(self):
        share = get_or_create_property_share(self.user, self.prop)
        ctx = build_public_property_context(share)
        self.assertEqual(ctx['dossier_badge'], 'فایل شخصی')
        self.assertNotIn('یادداشت محرمانه', ctx['description_text'])

    def test_highlights_do_not_duplicate_core_amenities(self):
        self.prop.has_parking = True
        self.prop.has_storage = True
        self.prop.has_elevator = True
        self.prop.property_type = 'آپارتمان'
        self.prop.save(update_fields=['has_parking', 'has_storage', 'has_elevator', 'property_type'])
        share = get_or_create_property_share(self.user, self.prop)
        ctx = build_public_property_context(share)
        core_labels = [
            item['label']
            for item in ctx['feature_profile']['core']
            if item.get('known') and item.get('state') == 'yes'
        ]
        self.assertEqual(set(core_labels), {'پارکینگ', 'انباری', 'آسانسور'})
        self.assertEqual(ctx['feature_highlights'], ['آپارتمان'])

    def test_amenities_text_overrides_false_core_flags(self):
        self.prop.amenities = 'آسانسور، پارکینگ، انباری، لابی'
        self.prop.has_parking = False
        self.prop.has_storage = False
        self.prop.has_elevator = False
        self.prop.save(update_fields=[
            'amenities', 'has_parking', 'has_storage', 'has_elevator',
        ])
        share = get_or_create_property_share(self.user, self.prop)
        ctx = build_public_property_context(share)
        core = {item['label']: item['state'] for item in ctx['feature_profile']['core']}
        self.assertEqual(core['آسانسور'], 'yes')
        self.assertEqual(core['پارکینگ'], 'yes')
        self.assertEqual(core['انباری'], 'yes')
        extra_labels = [
            item['label']
            for group in ctx['feature_profile']['groups']
            for item in group['items']
        ]
        self.assertEqual(extra_labels, ['لابی'])
        self.assertEqual(ctx['feature_profile']['source_label'], 'ثبت‌شده در فایل شخصی')

    def test_amenities_show_real_values_not_just_bool(self):
        self.prop.amenities = (
            'آسانسور، پارکینگ، '
            'تعداد واحد در طبقه: ۲، '
            'تعداد پارکینگ: ۱، '
            'جنس کف: سرامیک، '
            'بالکن ندارد، '
            'لابی'
        )
        self.prop.has_elevator = False
        self.prop.has_parking = False
        self.prop.has_storage = False
        self.prop.save(update_fields=[
            'amenities', 'has_elevator', 'has_parking', 'has_storage',
        ])
        share = get_or_create_property_share(self.user, self.prop)
        ctx = build_public_property_context(share)
        core = {item['label']: item['value'] for item in ctx['feature_profile']['core']}
        self.assertEqual(core['آسانسور'], 'دارد')
        self.assertEqual(core['پارکینگ'], 'دارد')
        by_label = {
            item['label']: item
            for group in ctx['feature_profile']['groups']
            for item in group['items']
        }
        self.assertEqual(by_label['تعداد واحد در طبقه']['value'], '۲')
        self.assertEqual(by_label['تعداد واحد در طبقه']['state'], 'neutral')
        self.assertEqual(by_label['تعداد پارکینگ']['value'], '۱')
        self.assertEqual(by_label['جنس کف']['value'], 'سرامیک')
        self.assertEqual(by_label['بالکن']['value'], 'ندارد')
        self.assertEqual(by_label['لابی']['value'], 'دارد')
        self.assertNotEqual(by_label['تعداد واحد در طبقه']['value'], 'دارد')

        from workspace.services.property_public_share import build_property_amenity_dossier_items
        dossier = build_property_amenity_dossier_items(self.prop)
        by_d = {i['label']: i for i in dossier}
        self.assertEqual(by_d['آسانسور']['emoji'], '⬆️')
        self.assertEqual(by_d['پارکینگ']['state'], 'yes')
        self.assertEqual(by_d['پارکینگ']['tip'], 'پارکینگ: دارد')
        self.assertEqual(by_d['تعداد واحد در طبقه']['value'], '۲')
        self.assertEqual(by_d['تعداد واحد در طبقه']['emoji'], '🚪')
        self.assertEqual(by_d['تعداد واحد در طبقه']['tip'], 'تعداد واحد در طبقه: ۲')
        self.assertEqual(by_d['جنس کف']['value'], 'سرامیک')
        self.assertEqual(by_d['بالکن']['state'], 'no')
        self.assertTrue(by_d['آسانسور']['is_core'])
        self.assertFalse(by_d['لابی']['is_core'])

        url = reverse('listing_public:property_view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'تعداد واحد در طبقه')
        self.assertContains(resp, '۲')
        self.assertContains(resp, 'سرامیک')

    def test_build_context_shows_notes_when_enabled(self):
        share = CRMPropertyPublicShare.objects.create(
            share_token='proptoken123',
            property=self.prop,
            created_by=self.user,
            show_internal_notes=True,
        )
        ctx = build_public_property_context(share)
        self.assertIn('یادداشت محرمانه', ctx['description_text'])

    def test_public_page_renders(self):
        share = CRMPropertyPublicShare.objects.create(
            share_token='proptoken456',
            property=self.prop,
            created_by=self.user,
        )
        url = reverse('listing_public:property_view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ویلای ۲۰۰ متری')
        self.assertContains(resp, 'فایل شخصی')
        self.assertContains(resp, '09129876543')

    def test_public_page_shows_navigation_when_coords_exist(self):
        self.prop.latitude = 35.781
        self.prop.longitude = 51.412
        self.prop.save(update_fields=['latitude', 'longitude'])
        share = CRMPropertyPublicShare.objects.create(
            share_token='proptokenmap',
            property=self.prop,
            created_by=self.user,
        )
        url = reverse('listing_public:property_view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'مسیریابی')
        self.assertContains(resp, 'google.com/maps/dir')
        self.assertContains(resp, 'neshan.org/maps/routing')

    def test_inactive_share_returns_410(self):
        share = CRMPropertyPublicShare.objects.create(
            share_token='proptoken789',
            property=self.prop,
            created_by=self.user,
            is_active=False,
        )
        url = reverse('listing_public:property_view', kwargs={'share_token': share.share_token})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 410)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_share_manage_json(self, _mock_license):
        self.client.login(username='09129876543', password='testpass123')
        url = reverse('workspace:crm_property_public_share', kwargs={'property_id': self.prop.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertIn('share_url', data)
        self.assertIn('/p/f/', data['share_url'])

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_share_manage_can_deactivate(self, _mock_license):
        self.client.login(username='09129876543', password='testpass123')
        url = reverse('workspace:crm_property_public_share', kwargs={'property_id': self.prop.pk})
        resp = self.client.post(url, {
            'consultant_name': '',
            'consultant_phone': '',
            'welcome_message': '',
        })
        self.assertEqual(resp.status_code, 302)
        share = CRMPropertyPublicShare.objects.get(property=self.prop, created_by=self.user)
        self.assertFalse(share.is_active)
