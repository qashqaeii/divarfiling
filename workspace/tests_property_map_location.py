"""تست نقشه و به‌روزرسانی مختصات فایل شخصی CRM."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import CRMAgency, CRMAgencyMember, CRMProperty, CRMResourceShare
from workspace.services.listing_map import (
    build_crm_property_map_context,
    parse_map_coordinates,
)
from workspace.services.crm_sharing import share_property

User = get_user_model()


class PropertyMapLocationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='09121111111',
            phone='09121111111',
            password='testpass123',
        )
        self.other = User.objects.create_user(
            username='09122222222',
            phone='09122222222',
            password='testpass123',
        )
        self.agency = CRMAgency.objects.create(name='آژانس تست', owner=self.owner)
        CRMAgencyMember.objects.create(
            agency=self.agency, user=self.owner, role='owner', is_active=True,
        )
        self.other_member = CRMAgencyMember.objects.create(
            agency=self.agency, user=self.other, role='agent', is_active=True,
        )
        self.prop = CRMProperty.objects.create(
            user=self.owner,
            agency=self.agency,
            title='آپارتمان نقشه',
            property_type='آپارتمان',
            deal_mode='فروش',
            city='تهران',
            neighborhood='جردن',
            latitude=35.7575,
            longitude=51.4100,
            sale_price=10_000_000_000,
            area=120,
        )
        self.client = Client()
        self.url = reverse('workspace:crm_property_location', kwargs={'property_id': self.prop.pk})
        self.detail_url = reverse('workspace:crm_property_detail', kwargs={'property_id': self.prop.pk})

    def test_parse_map_coordinates_rejects_outside_iran(self):
        lat, lng, err = parse_map_coordinates(48.8566, 2.3522)
        self.assertIsNone(lat)
        self.assertIsNone(lng)
        self.assertIn('ایران', err)

    def test_parse_map_coordinates_accepts_tehran(self):
        lat, lng, err = parse_map_coordinates(35.7, 51.4)
        self.assertEqual(lat, 35.7)
        self.assertEqual(lng, 51.4)
        self.assertIsNone(err)

    def test_build_map_context_with_coords(self):
        ctx = build_crm_property_map_context(self.prop)
        self.assertTrue(ctx['has_coords'])
        self.assertEqual(ctx['listing_map_marker']['lat'], 35.7575)
        self.assertEqual(ctx['listing_map_marker']['lng'], 51.4100)
        self.assertIsNotNone(ctx['map_navigation'])
        self.assertEqual(ctx['location_accuracy']['kind'], 'exact')

    def test_build_map_context_without_coords(self):
        self.prop.latitude = None
        self.prop.longitude = None
        self.prop.save(update_fields=['latitude', 'longitude'])
        ctx = build_crm_property_map_context(self.prop)
        self.assertFalse(ctx['has_coords'])
        self.assertIsNone(ctx['listing_map_marker']['lat'])
        self.assertIsNone(ctx['map_navigation'])

    def test_location_post_succeeds_for_owner(self):
        self.client.login(username='09121111111', password='testpass123')
        resp = self.client.post(
            self.url,
            data=json.dumps({'latitude': 35.7219, 'longitude': 51.3347}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertAlmostEqual(data['latitude'], 35.7219)
        self.assertAlmostEqual(data['longitude'], 51.3347)
        self.assertIn('google_url', data['map_navigation'])
        self.prop.refresh_from_db()
        self.assertAlmostEqual(self.prop.latitude, 35.7219)
        self.assertAlmostEqual(self.prop.longitude, 51.3347)

    def test_location_post_rejects_invalid_coords(self):
        self.client.login(username='09121111111', password='testpass123')
        resp = self.client.post(
            self.url,
            data=json.dumps({'latitude': 0, 'longitude': 0}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.json()['ok'])

    def test_location_post_forbidden_for_other_user(self):
        self.client.login(username='09122222222', password='testpass123')
        resp = self.client.post(
            self.url,
            data=json.dumps({'latitude': 35.7, 'longitude': 51.4}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_location_post_forbidden_for_confidential_recipient(self):
        share_property(
            self.owner,
            self.prop,
            self.other_member.pk,
            share_mode=CRMResourceShare.SHARE_MODE_CONFIDENTIAL,
        )
        self.client.login(username='09122222222', password='testpass123')
        resp = self.client.post(
            self.url,
            data=json.dumps({'latitude': 35.7, 'longitude': 51.4}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_detail_context_includes_map_marker(self):
        self.client.login(username='09121111111', password='testpass123')
        resp = self.client.get(self.detail_url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['show_property_map'])
        self.assertTrue(resp.context['can_edit_map_location'])
        self.assertTrue(resp.context['property_map_has_coords'])
        marker = resp.context['listing_map_marker']
        self.assertEqual(marker['lat'], 35.7575)
        self.assertEqual(marker['lng'], 51.4100)
        self.assertContains(resp, 'crmPropLocationMap')
        self.assertContains(resp, 'crm-prop-map-marker')

    def test_detail_masks_map_for_confidential_share(self):
        share_property(
            self.owner,
            self.prop,
            self.other_member.pk,
            share_mode=CRMResourceShare.SHARE_MODE_CONFIDENTIAL,
        )
        self.client.login(username='09122222222', password='testpass123')
        resp = self.client.get(self.detail_url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['mask_sensitive'])
        self.assertFalse(resp.context['show_property_map'])
        self.assertTrue(resp.context['property_map_locked'])
        self.assertContains(resp, 'موقعیت دقیق محرمانه است')
