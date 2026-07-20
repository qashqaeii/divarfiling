"""Tests for CRM property nearby POIs (Overpass/OSM on-demand)."""
from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from workspace.models import CRMAgency, CRMAgencyMember, CRMProperty
from workspace.services.nearby_pois import (
    PAYLOAD_VERSION,
    NearbyPoiError,
    build_overpass_query,
    estimate_walk_label,
    fetch_and_save_nearby_pois,
    format_distance_label,
    group_nearby_items,
    haversine_m,
    resolve_nearby_items,
    stored_nearby_pois_valid,
)

User = get_user_model()


def _sample_elements():
    return [
        {
            'type': 'node', 'lat': 35.7580, 'lon': 51.4105,
            'tags': {'railway': 'station', 'station': 'subway', 'name': 'ونک'},
        },
        {
            'type': 'node', 'lat': 35.7590, 'lon': 51.4110,
            'tags': {'highway': 'bus_stop', 'name': 'ایستگاه اتوبوس ونک'},
        },
        {
            'type': 'node', 'lat': 35.7595, 'lon': 51.4115,
            'tags': {'amenity': 'place_of_worship', 'religion': 'muslim', 'name': 'مسجد ونک'},
        },
        {
            'type': 'node', 'lat': 35.7600, 'lon': 51.4120,
            'tags': {'leisure': 'park', 'name': 'پارک ملت'},
        },
        {
            'type': 'node', 'lat': 35.7610, 'lon': 51.4130,
            'tags': {'amenity': 'hospital', 'name': 'بیمارستان پارس'},
        },
        {
            'type': 'node', 'lat': 35.7620, 'lon': 51.4140,
            'tags': {'amenity': 'school', 'name': 'دبستان سلام'},
        },
        {
            'type': 'node', 'lat': 35.7630, 'lon': 51.4150,
            'tags': {'shop': 'supermarket', 'name': 'هایپرمی'},
        },
        {
            'type': 'node', 'lat': 35.7640, 'lon': 51.4160,
            'tags': {'amenity': 'pharmacy', 'name': 'داروخانه دکتر رضایی'},
        },
    ]


class NearbyPoisServiceTests(TestCase):
    def test_haversine_and_distance_label(self):
        dist = haversine_m(35.7575, 51.4100, 35.7580, 51.4105)
        self.assertGreater(dist, 50)
        self.assertLess(dist, 200)
        self.assertIn('متر', format_distance_label(420))
        self.assertIn('کیلومتر', format_distance_label(1250))
        self.assertIn('پیاده', estimate_walk_label(400))

    def test_build_overpass_query_contains_categories(self):
        q = build_overpass_query(35.7, 51.4, radius_m=3000)
        self.assertIn('amenity"="hospital"', q)
        self.assertIn('highway"="bus_stop"', q)
        self.assertIn('place_of_worship"', q)
        self.assertIn('building"="mosque"', q)
        self.assertIn('highway"="motorway"', q)
        self.assertIn('amenity"="fuel"', q)
        self.assertIn('amenity"="parking"', q)
        self.assertIn('way["highway"](around:120,35.7,51.4);', q)
        self.assertIn('around:3000,35.7,51.4', q)

    def test_resolve_v3_transport_and_daily_categories(self):
        elements = [
            {
                'type': 'way', 'center': {'lat': 35.7578, 'lon': 51.4102},
                'tags': {'highway': 'motorway', 'name': 'آزادراه همت'},
            },
            {
                'type': 'way', 'center': {'lat': 35.7576, 'lon': 51.4101},
                'tags': {'highway': 'primary', 'name': 'ولیعصر'},
            },
            {
                'type': 'node', 'lat': 35.7582, 'lon': 51.4103,
                'tags': {'amenity': 'fuel', 'name': 'پمپ بنزین ونک'},
            },
            {
                'type': 'node', 'lat': 35.7583, 'lon': 51.4104,
                'tags': {'amenity': 'parking', 'name': 'پارکینگ عمومی'},
            },
            {
                'type': 'node', 'lat': 35.7584, 'lon': 51.4105,
                'tags': {'amenity': 'parking', 'access': 'private', 'name': 'پارکینگ خصوصی'},
            },
            {
                'type': 'node', 'lat': 35.7585, 'lon': 51.4106,
                'tags': {'amenity': 'clinic', 'name': 'کلینیک سلامت'},
            },
        ]
        items = resolve_nearby_items(35.7575, 51.4100, elements, radius_m=5000)
        by_key = {item.key: item for item in items}
        self.assertTrue(by_key['motorway'].found)
        self.assertTrue(by_key['main_road'].found)
        self.assertTrue(by_key['fuel'].found)
        self.assertTrue(by_key['parking'].found)
        self.assertEqual(by_key['parking'].name, 'پارکینگ عمومی')
        self.assertTrue(by_key['clinic'].found)
        self.assertFalse(by_key['hospital'].found)

    def test_street_type_uses_small_radius_and_width(self):
        elements = [
            {
                'type': 'way', 'center': {'lat': 35.75752, 'lon': 51.41002},
                'tags': {'highway': 'residential', 'width': '8'},
            },
            {
                'type': 'way', 'center': {'lat': 35.7590, 'lon': 51.4110},
                'tags': {'highway': 'primary', 'lanes': '4'},
            },
        ]
        items = resolve_nearby_items(35.7575, 51.4100, elements, radius_m=5000)
        street = next(i for i in items if i.key == 'street_type')
        self.assertTrue(street.found)
        self.assertIn('کوچه مسکونی', street.name)
        self.assertIn('عرض', street.name)
        self.assertEqual(street.distance_label, 'جلوی ملک')

    def test_old_payload_version_invalid(self):
        prop = CRMProperty(
            latitude=35.7575,
            longitude=51.4100,
            nearby_pois={
                'version': 2,
                'coords': {'lat': 35.7575, 'lng': 51.4100},
                'radius_m': 3000,
                'items': [{'key': 'metro', 'found': True}],
            },
        )
        self.assertFalse(stored_nearby_pois_valid(prop))

    def test_old_payload_version_one_invalid(self):
        prop = CRMProperty(
            latitude=35.7575,
            longitude=51.4100,
            nearby_pois={
                'version': 1,
                'coords': {'lat': 35.7575, 'lng': 51.4100},
                'radius_m': 3000,
                'items': [{'key': 'metro', 'found': True}],
            },
        )
        self.assertFalse(stored_nearby_pois_valid(prop))

    def test_resolve_nearby_items_picks_nearest(self):
        items = resolve_nearby_items(35.7575, 51.4100, _sample_elements(), radius_m=5000)
        by_key = {item.key: item for item in items}
        self.assertTrue(by_key['metro'].found)
        self.assertEqual(by_key['metro'].name, 'ونک')
        self.assertTrue(by_key['mosque'].found)
        self.assertEqual(by_key['mosque'].name, 'مسجد ونک')
        self.assertTrue(by_key['pharmacy'].found)
        self.assertTrue(by_key['metro'].walk_label)

    def test_group_nearby_items_structure(self):
        items = resolve_nearby_items(35.7575, 51.4100, _sample_elements(), radius_m=5000)
        groups = group_nearby_items([i.as_dict() for i in items])
        self.assertTrue(any(g['key'] == 'religion' for g in groups))
        self.assertTrue(any(g['key'] == 'transport' for g in groups))

    def test_stored_cache_invalid_when_coords_change(self):
        prop = CRMProperty(
            latitude=35.7575,
            longitude=51.4100,
            nearby_pois={
                'version': PAYLOAD_VERSION,
                'coords': {'lat': 35.7575, 'lng': 51.4100},
                'radius_m': 3000,
                'items': [{'key': 'metro', 'found': True}],
            },
        )
        self.assertTrue(stored_nearby_pois_valid(prop))
        prop.longitude = 51.4200
        self.assertFalse(stored_nearby_pois_valid(prop))

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_fetch_and_save_persists_payload(self, mock_fetch):
        mock_fetch.return_value = _sample_elements()
        user = User.objects.create_user(username='09123334444', phone='09123334444', password='x')
        prop = CRMProperty.objects.create(
            user=user,
            title='تست',
            latitude=35.7575,
            longitude=51.4100,
        )
        cache.clear()
        result = fetch_and_save_nearby_pois(prop, user)
        prop.refresh_from_db()
        self.assertTrue(result['ok'])
        self.assertFalse(result['cached'])
        self.assertGreater(result['found_count'], 0)
        self.assertTrue(result['groups'])
        self.assertTrue(result['highlights'])
        self.assertTrue(stored_nearby_pois_valid(prop))
        self.assertEqual(prop.nearby_pois.get('version'), PAYLOAD_VERSION)

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_fetch_uses_cache_without_api(self, mock_fetch):
        user = User.objects.create_user(username='09124445555', phone='09124445555', password='x')
        prop = CRMProperty.objects.create(
            user=user,
            title='کش',
            latitude=35.7575,
            longitude=51.4100,
            nearby_pois={
                'version': PAYLOAD_VERSION,
                'coords': {'lat': 35.7575, 'lng': 51.4100},
                'radius_m': 3000,
                'fetched_at': '2026-07-20T09:00:00+00:00',
                'fetched_at_label': '۱۴۰۴/۰۴/۲۹ ۰۹:۰۰',
                'items': [{'key': 'metro', 'label': 'مترو', 'group': 'transport', 'found': True, 'distance_label': '۱۰۰ متر'}],
                'found_count': 1,
                'groups': [],
                'highlights': [],
            },
        )
        result = fetch_and_save_nearby_pois(prop, user)
        self.assertTrue(result['cached'])
        mock_fetch.assert_not_called()

    def test_no_coords_raises(self):
        user = User.objects.create_user(username='09125556666', phone='09125556666', password='x')
        prop = CRMProperty.objects.create(user=user, title='بدون مختصات')
        with self.assertRaises(NearbyPoiError) as ctx:
            fetch_and_save_nearby_pois(prop, user)
        self.assertEqual(ctx.exception.code, 'no_coords')


@override_settings(
    NEARBY_POI_USER_DAILY_LIMIT=1,
    NEARBY_POI_GLOBAL_DAILY_LIMIT=100,
)
class NearbyPoisRateLimitTests(TestCase):
    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_user_daily_limit(self, mock_fetch):
        mock_fetch.return_value = _sample_elements()
        user = User.objects.create_user(username='09126667777', phone='09126667777', password='x')
        prop = CRMProperty.objects.create(
            user=user,
            title='لیمیت',
            latitude=35.7575,
            longitude=51.4100,
        )
        cache.clear()
        fetch_and_save_nearby_pois(prop, user, force_refresh=True)
        prop.nearby_pois = {}
        prop.save(update_fields=['nearby_pois'])
        with self.assertRaises(NearbyPoiError) as ctx:
            fetch_and_save_nearby_pois(prop, user, force_refresh=True)
        self.assertEqual(ctx.exception.code, 'user_limit')


class CRMPropertyNearbyPoisViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(
            username='09121111111', phone='09121111111', password='testpass123',
        )
        self.agency = CRMAgency.objects.create(name='آژانس', owner=self.owner)
        CRMAgencyMember.objects.create(
            agency=self.agency, user=self.owner, role='owner', is_active=True,
        )
        self.prop = CRMProperty.objects.create(
            user=self.owner,
            agency=self.agency,
            title='آپارتمان',
            latitude=35.7575,
            longitude=51.4100,
        )
        self.client = Client()
        self.client.login(username='09121111111', password='testpass123')
        self.url = reverse('workspace:crm_property_nearby_pois', kwargs={'property_id': self.prop.pk})
        self.detail_url = reverse('workspace:crm_property_detail', kwargs={'property_id': self.prop.pk})

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_post_fetch_success(self, mock_fetch):
        mock_fetch.return_value = _sample_elements()
        resp = self.client.post(
            self.url,
            data=json.dumps({'refresh': False}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertGreater(len(data['items']), 10)
        self.assertTrue(data['groups'])
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.nearby_pois.get('items'))

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_post_cached_second_call(self, mock_fetch):
        mock_fetch.return_value = _sample_elements()
        self.client.post(self.url, data='{}', content_type='application/json')
        resp = self.client.post(self.url, data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['cached'])
        self.assertEqual(mock_fetch.call_count, 1)

    def test_post_without_coords(self):
        self.prop.latitude = None
        self.prop.longitude = None
        self.prop.save(update_fields=['latitude', 'longitude'])
        resp = self.client.post(self.url, data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['code'], 'no_coords')

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_service_busy_message(self, mock_fetch):
        mock_fetch.side_effect = NearbyPoiError(
            'service_busy',
            'سرویس نقشه الان شلوغ است. لطفاً چند دقیقه بعد دوباره تلاش کنید.',
            status=503,
        )
        resp = self.client.post(
            self.url,
            data=json.dumps({'refresh': True}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(resp.json()['code'], 'service_busy')

    def test_detail_page_renders_nearby_panel(self):
        resp = self.client.get(self.detail_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'crm-nearby-pois')
        self.assertContains(resp, 'امکانات و دسترسی‌ها')
        self.assertContains(resp, 'crm-property-nearby-pois.js')

    def test_location_update_clears_nearby_pois(self):
        self.prop.nearby_pois = {
            'version': PAYLOAD_VERSION,
            'coords': {'lat': 35.7575, 'lng': 51.4100},
            'items': [{'key': 'metro', 'found': True}],
        }
        self.prop.save(update_fields=['nearby_pois'])
        loc_url = reverse('workspace:crm_property_location', kwargs={'property_id': self.prop.pk})
        resp = self.client.post(
            loc_url,
            data=json.dumps({'latitude': 35.7600, 'longitude': 51.4200}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.prop.refresh_from_db()
        self.assertEqual(self.prop.nearby_pois, {})

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_stored_data_shown_on_detail(self, mock_fetch):
        mock_fetch.return_value = _sample_elements()
        self.client.post(self.url, data='{}', content_type='application/json')
        resp = self.client.get(self.detail_url)
        self.assertContains(resp, 'crm-nearby-pois-initial')
        self.assertContains(resp, 'found_count')
