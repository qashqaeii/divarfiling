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
