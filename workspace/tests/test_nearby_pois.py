"""Tests for CRM property nearby POIs (Overpass/OSM on-demand)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from workspace.models import CRMAgency, CRMAgencyMember, CRMProperty
from workspace.services.nearby_pois import (
    ACCESSIBILITY_STATUS_FAILED,
    ACCESSIBILITY_STATUS_PENDING,
    ACCESSIBILITY_STATUS_READY,
    ACCESSIBILITY_STATUS_UNAVAILABLE,
    PAYLOAD_VERSION,
    NearbyPoiError,
    TOOL_DEFAULT_RADIUS_M,
    build_accessibility_customer_copy,
    build_accessibility_report_copy,
    build_overpass_query,
    estimate_walk_label,
    fetch_and_save_nearby_pois,
    fetch_nearby_accessibility_for_tools,
    format_distance_label,
    get_property_accessibility_status,
    group_nearby_items,
    haversine_m,
    listing_location_metadata,
    property_accessibility_radius_km,
    nearby_pois_page_context,
    refresh_property_accessibilities,
    resolve_nearby_catalog,
    resolve_nearby_items,
    resolve_property_location,
    schedule_property_accessibilities,
    stored_nearby_pois_valid,
    validate_tool_radius_m,
)
from workspace.services.property_accessibility_jobs import (
    process_property_accessibility_jobs,
    reconcile_stale_pending_accessibilities,
)

User = get_user_model()


def _drain_accessibility_jobs():
    process_property_accessibility_jobs(limit=50)


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

    @override_settings(
        NEARBY_POI_OVERPASS_URLS=(
            'https://example.invalid/a',
            'https://example.invalid/b',
        ),
        NEARBY_POI_FORCE_IPV4=False,
    )
    @patch('workspace.services.nearby_pois._post_overpass')
    def test_overpass_tries_next_url_after_http_503(self, mock_post):
        from workspace.services.nearby_pois import fetch_overpass_elements
        busy = MagicMock()
        busy.status_code = 503
        ok = MagicMock()
        ok.status_code = 200
        ok.json.return_value = {'elements': _sample_elements()}
        mock_post.side_effect = [busy, ok]
        elements = fetch_overpass_elements(35.7, 51.4)
        self.assertEqual(len(elements), len(_sample_elements()))
        self.assertEqual(mock_post.call_count, 2)

    @override_settings(
        NEARBY_POI_OVERPASS_URLS=(
            'https://example.invalid/a',
            'https://example.invalid/b',
        ),
        NEARBY_POI_FORCE_IPV4=False,
    )
    @patch('workspace.services.nearby_pois._post_overpass')
    def test_overpass_tries_next_url_after_empty_elements(self, mock_post):
        from workspace.services.nearby_pois import fetch_overpass_elements
        empty = MagicMock()
        empty.status_code = 200
        empty.json.return_value = {'elements': []}
        ok = MagicMock()
        ok.status_code = 200
        ok.json.return_value = {'elements': _sample_elements()}
        mock_post.side_effect = [empty, ok]
        elements = fetch_overpass_elements(35.7, 51.4)
        self.assertEqual(len(elements), len(_sample_elements()))
        self.assertEqual(mock_post.call_count, 2)

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
        transport = next(g for g in groups if g['key'] == 'transport')
        self.assertEqual(transport.get('icon'), 'fa-route')

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
        self.assertEqual(data.get('status'), ACCESSIBILITY_STATUS_READY)
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.nearby_pois.get('items'))
        self.assertEqual(get_property_accessibility_status(self.prop), ACCESSIBILITY_STATUS_READY)

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_post_cached_second_call(self, mock_fetch):
        mock_fetch.return_value = _sample_elements()
        self.client.post(self.url, data='{}', content_type='application/json')
        resp = self.client.post(self.url, data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['cached'])
        mock_fetch.assert_called_once()

    def test_post_without_coords(self):
        self.prop.latitude = None
        self.prop.longitude = None
        self.prop.save(update_fields=['latitude', 'longitude'])
        resp = self.client.post(self.url, data='{}', content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json().get('code'), 'no_coords')

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_service_busy_marks_failed_after_job(self, mock_fetch):
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
        self.prop.refresh_from_db()
        self.assertEqual(get_property_accessibility_status(self.prop), ACCESSIBILITY_STATUS_FAILED)

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_service_unavailable_includes_browser_fallback(self, mock_fetch):
        mock_fetch.side_effect = NearbyPoiError(
            'service_unavailable',
            'سرویس نقشه از سمت سرور در دسترس نیست.',
            status=503,
        )
        resp = self.client.post(
            self.url,
            data=json.dumps({'refresh': True}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 503)
        self.assertIn('fallback', resp.json())
        resp = self.client.get(self.url)
        data = resp.json()
        self.assertEqual(data.get('status'), ACCESSIBILITY_STATUS_FAILED)
        self.assertIn('fallback', data)
        self.assertIn('query', data['fallback'])

    def test_post_client_elements_saves_payload(self):
        resp = self.client.post(
            self.url,
            data=json.dumps({'refresh': True, 'elements': _sample_elements()}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertGreater(data['found_count'], 0)
        self.prop.refresh_from_db()
        self.assertTrue(self.prop.nearby_pois.get('items'))

    def test_post_invalid_elements_rejected(self):
        resp = self.client.post(
            self.url,
            data=json.dumps({'refresh': True, 'elements': {'bad': True}}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['code'], 'invalid_elements')

    def test_detail_page_renders_nearby_panel(self):
        resp = self.client.get(self.detail_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'crm-nearby-pois')
        self.assertContains(resp, 'امکانات و دسترسی‌ها')
        self.assertContains(resp, 'crm-property-nearby-pois.js')

    def test_location_update_clears_stored_pois(self):
        self.prop.nearby_pois = {
            'version': PAYLOAD_VERSION,
            'status': ACCESSIBILITY_STATUS_READY,
            'coords': {'lat': 35.7575, 'lng': 51.4100},
            'radius_m': 3000,
            'items': [{'key': 'metro', 'found': True, 'label': 'مترو', 'group': 'transport'}],
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
    def test_repair_restores_display_after_coords_metadata_drift(self, mock_fetch):
        mock_fetch.return_value = _sample_elements()
        self.client.post(self.url, data='{}', content_type='application/json')
        self.prop.refresh_from_db()
        data = dict(self.prop.nearby_pois or {})
        self.assertTrue(data.get('items'))
        data['radius_m'] = 5000
        data['coords'] = {
            'lat': round(float(self.prop.latitude), 4),
            'lng': round(float(self.prop.longitude), 4),
        }
        self.prop.nearby_pois = data
        self.prop.save(update_fields=['nearby_pois'])
        ctx = nearby_pois_page_context(self.prop)
        self.assertTrue(ctx['has_stored'])
        self.assertIsNotNone(ctx['initial_payload'])
        self.assertGreater(int(ctx['initial_payload'].get('found_count') or 0), 0)

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_stored_data_shown_on_detail(self, mock_fetch):
        mock_fetch.return_value = _sample_elements()
        self.client.post(self.url, data='{}', content_type='application/json')
        resp = self.client.get(self.detail_url)
        self.assertContains(resp, 'crm-nearby-pois-initial')
        self.assertContains(resp, 'found_count')


class NearbyAccessToolsTests(TestCase):
    def test_validate_tool_radius_snaps(self):
        self.assertEqual(validate_tool_radius_m(1000), 1000)
        self.assertEqual(validate_tool_radius_m('1500'), 1000)
        self.assertEqual(validate_tool_radius_m('bad'), TOOL_DEFAULT_RADIUS_M)

    def test_resolve_nearby_catalog_counts_and_nearest(self):
        categories, markers = resolve_nearby_catalog(
            35.7575, 51.4100, _sample_elements(), radius_m=5000,
        )
        by_key = {c['key']: c for c in categories}
        self.assertGreater(by_key['metro']['count'], 0)
        self.assertTrue(by_key['metro']['nearest'])
        self.assertGreater(by_key['park']['count'], 0)
        self.assertTrue(markers)
        self.assertEqual(markers[0]['key'], 'metro')

    def test_build_copy_outputs_plain_text(self):
        categories, markers = resolve_nearby_catalog(
            35.7575, 51.4100, _sample_elements(), radius_m=1000,
        )
        from django.utils import timezone
        from workspace.services.nearby_pois import _build_tool_payload

        payload = _build_tool_payload(
            35.7575, 51.4100, categories, markers,
            radius_m=1000, fetched_at=timezone.now(),
        )
        report = build_accessibility_report_copy(payload)
        customer = build_accessibility_customer_copy(payload)
        self.assertIn('دسترسی‌های اطراف ملک', report)
        self.assertNotIn('<', report)
        self.assertIn('مترو', customer)

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_fetch_nearby_accessibility_for_tools_no_db(self, mock_fetch):
        mock_fetch.return_value = _sample_elements()
        user = User.objects.create_user(username='09128889999', phone='09128889999', password='x')
        cache.clear()
        result = fetch_nearby_accessibility_for_tools(user, 35.7575, 51.4100, 1000)
        self.assertTrue(result['ok'])
        self.assertGreater(result['categories_found'], 0)
        self.assertIn('report_copy', result)
        self.assertIn('customer_copy', result)
        self.assertFalse(result['cached'])

        result2 = fetch_nearby_accessibility_for_tools(user, 35.7575, 51.4100, 1000)
        self.assertTrue(result2['cached'])
        self.assertEqual(mock_fetch.call_count, 1)


class ToolsNearbyAccessibilityViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='09127778888', phone='09127778888', password='testpass123',
        )
        self.client = Client()
        self.client.login(username='09127778888', password='testpass123')
        self.url = reverse('workspace:tools_nearby_accessibility')
        self._license_patcher = patch('workspace.mixins.has_active_bot_license', return_value=True)
        self._license_patcher.start()

    def tearDown(self):
        self._license_patcher.stop()

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_post_success(self, mock_fetch):
        mock_fetch.return_value = _sample_elements()
        resp = self.client.post(
            self.url,
            data=json.dumps({
                'latitude': 35.7575,
                'longitude': 51.4100,
                'radius_m': 1000,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertGreater(len(data['categories']), 10)
        self.assertIn('markers', data)

    def test_post_invalid_coords(self):
        resp = self.client.post(
            self.url,
            data=json.dumps({'latitude': 'x', 'longitude': 51.4}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_post_client_elements(self, mock_fetch):
        resp = self.client.post(
            self.url,
            data=json.dumps({
                'latitude': 35.7575,
                'longitude': 51.4100,
                'radius_m': 2000,
                'elements': _sample_elements(),
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['ok'])
        mock_fetch.assert_not_called()


class PropertyAccessibilitiesAutomationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='09129990001', phone='09129990001', password='testpass123',
        )
        self.other = User.objects.create_user(
            username='09129990002', phone='09129990002', password='testpass123',
        )
        self.client = Client()
        self.client.login(username='09129990001', password='testpass123')

    def _run_scheduled(self):
        _drain_accessibility_jobs()

    def test_manual_create_with_location_does_not_auto_fetch(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='ملک دستی',
            latitude=35.7575,
            longitude=51.4100,
        )
        self.assertFalse(stored_nearby_pois_valid(prop))
        self.assertEqual(get_property_accessibility_status(prop), '')

    def test_manual_create_with_approximate_location_not_auto_fetched(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='تقریبی',
            latitude=35.7575,
            longitude=51.4100,
            feature_data={'_location_precision': 'approximate', '_location_source': 'listing_coordinates'},
        )
        self.assertFalse(stored_nearby_pois_valid(prop))

    def test_manual_create_without_location_skips_external_generation(self):
        with self.captureOnCommitCallbacks(execute=True):
            schedule_property_accessibilities(
                CRMProperty.objects.create(user=self.user, title='بدون موقعیت').pk,
                self.user.pk,
            )
        prop = CRMProperty.objects.get(title='بدون موقعیت')
        self.assertEqual(get_property_accessibility_status(prop), ACCESSIBILITY_STATUS_UNAVAILABLE)

    def test_listing_personalize_does_not_auto_fetch_pois(self):
        from workspace.models import Dataset, Listing
        from workspace.services.crm import add_listing_to_personal_files

        dataset = Dataset.objects.create(user=self.user, name='ds', is_active=True)
        listing = Listing.objects.create(
            dataset=dataset,
            token='tok-auto-poi',
            title='آگهی',
            latitude=35.7575,
            longitude=51.4100,
            data={'نوع مختصات': 'FUZZY', 'در شعاع (متر)': 400},
        )
        prop, created = add_listing_to_personal_files(self.user, listing)
        self.assertTrue(created)
        prop.refresh_from_db()
        self.assertFalse(stored_nearby_pois_valid(prop))
        self.assertEqual(prop.feature_data.get('_location_precision'), 'approximate')

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_provider_failure_keeps_property_and_marks_failed(self, mock_fetch):
        mock_fetch.side_effect = NearbyPoiError('service_busy', 'شلوغ', status=503)
        prop = CRMProperty.objects.create(
            user=self.user,
            title='خطا',
            latitude=35.7575,
            longitude=51.4100,
        )
        url = reverse('workspace:crm_property_nearby_pois', kwargs={'property_id': prop.pk})
        resp = self.client.post(url, data=json.dumps({'refresh': True}), content_type='application/json')
        self.assertEqual(resp.status_code, 503)
        prop.refresh_from_db()
        self.assertEqual(get_property_accessibility_status(prop), ACCESSIBILITY_STATUS_FAILED)
        self.assertTrue(CRMProperty.objects.filter(pk=prop.pk).exists())

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_location_change_clears_stored_pois(self, mock_fetch):
        mock_fetch.return_value = _sample_elements()
        prop = CRMProperty.objects.create(
            user=self.user,
            title='جابجایی',
            latitude=35.7575,
            longitude=51.4100,
            nearby_pois={
                'version': PAYLOAD_VERSION,
                'status': ACCESSIBILITY_STATUS_READY,
                'coords': {'lat': 35.7575, 'lng': 51.4100},
                'radius_m': 3000,
                'items': [{'key': 'metro', 'found': True, 'label': 'مترو', 'group': 'transport'}],
            },
        )
        loc_url = reverse('workspace:crm_property_location', kwargs={'property_id': prop.pk})
        self.client.post(
            loc_url,
            data=json.dumps({'latitude': 35.7600, 'longitude': 51.4200}),
            content_type='application/json',
        )
        prop.refresh_from_db()
        self.assertFalse(stored_nearby_pois_valid(prop))
        mock_fetch.assert_not_called()
        self.assertEqual(prop.feature_data.get('_location_precision'), 'exact')

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_price_change_does_not_regenerate(self, mock_fetch):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='قیمت',
            latitude=35.7575,
            longitude=51.4100,
            sale_price=1000,
            nearby_pois={
                'version': PAYLOAD_VERSION,
                'status': ACCESSIBILITY_STATUS_READY,
                'coords': {'lat': 35.7575, 'lng': 51.4100},
                'radius_m': 3000,
                'items': [{'key': 'metro', 'found': True, 'label': 'مترو', 'group': 'transport'}],
            },
        )
        prop.sale_price = 2000
        prop.save(update_fields=['sale_price', 'updated_at'])
        mock_fetch.assert_not_called()

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_manual_refresh_uses_same_service(self, mock_fetch):
        mock_fetch.return_value = _sample_elements()
        prop = CRMProperty.objects.create(
            user=self.user,
            title='رفرش',
            latitude=35.7575,
            longitude=51.4100,
        )
        url = reverse('workspace:crm_property_nearby_pois', kwargs={'property_id': prop.pk})
        resp = self.client.post(url, data=json.dumps({'refresh': True}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('status'), ACCESSIBILITY_STATUS_READY)
        prop.refresh_from_db()
        self.assertEqual(get_property_accessibility_status(prop), ACCESSIBILITY_STATUS_READY)
        mock_fetch.assert_called_once()

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_double_manual_post_refreshes_once_per_click(self, mock_fetch):
        mock_fetch.return_value = _sample_elements()
        prop = CRMProperty.objects.create(
            user=self.user,
            title='دوبار',
            latitude=35.7575,
            longitude=51.4100,
        )
        url = reverse('workspace:crm_property_nearby_pois', kwargs={'property_id': prop.pk})
        self.client.post(url, data=json.dumps({'refresh': True}), content_type='application/json')
        self.client.post(url, data='{}', content_type='application/json')
        prop.refresh_from_db()
        self.assertEqual(get_property_accessibility_status(prop), ACCESSIBILITY_STATUS_READY)
        self.assertEqual(mock_fetch.call_count, 1)
        self.assertGreater(len(prop.nearby_pois.get('items') or []), 0)

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_detail_get_does_not_call_external_provider(self, mock_fetch):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='GET',
            latitude=35.7575,
            longitude=51.4100,
        )
        detail_url = reverse('workspace:crm_property_detail', kwargs={'property_id': prop.pk})
        resp = self.client.get(detail_url)
        self.assertEqual(resp.status_code, 200)
        mock_fetch.assert_not_called()

    def test_other_user_cannot_refresh_property(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='IDOR',
            latitude=35.7575,
            longitude=51.4100,
        )
        other_client = Client()
        other_client.login(username='09129990002', password='testpass123')
        url = reverse('workspace:crm_property_nearby_pois', kwargs={'property_id': prop.pk})
        resp = other_client.post(url, data='{}', content_type='application/json')
        self.assertIn(resp.status_code, (403, 404))

    def test_existing_saved_accessibility_data_renders(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='ذخیره‌شده',
            latitude=35.7575,
            longitude=51.4100,
            nearby_pois={
                'version': PAYLOAD_VERSION,
                'status': ACCESSIBILITY_STATUS_READY,
                'coords': {'lat': 35.7575, 'lng': 51.4100},
                'radius_m': 3000,
                'found_count': 2,
                'items': [
                    {'key': 'metro', 'found': True, 'label': 'مترو', 'group': 'transport', 'distance_label': '۱۰۰ متر'},
                ],
                'groups': [],
                'highlights': [],
            },
        )
        detail_url = reverse('workspace:crm_property_detail', kwargs={'property_id': prop.pk})
        resp = self.client.get(detail_url)
        self.assertContains(resp, 'crm-nearby-pois-initial')

    def test_resolve_property_location_exact_manual(self):
        prop = CRMProperty(latitude=35.7575, longitude=51.4100)
        loc = resolve_property_location(prop)
        self.assertTrue(loc['usable'])
        self.assertEqual(loc['precision'], 'exact')
        self.assertEqual(loc['source'], 'manual_pin')

    def test_property_accessibility_radius_km_default(self):
        self.assertEqual(property_accessibility_radius_km(), 3)

    def test_listing_location_metadata_exact(self):
        from workspace.models import Dataset, Listing

        listing = Listing(
            dataset=Dataset(user=self.user, name='x'),
            latitude=35.7,
            longitude=51.4,
            data={'نوع مختصات': 'دقیق'},
        )
        meta = listing_location_metadata(listing)
        self.assertEqual(meta['_location_precision'], 'exact')

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_stale_pending_becomes_retryable(self, mock_fetch):
        from datetime import timedelta

        from django.utils import timezone

        from workspace.models import PropertyAccessibilityJob

        mock_fetch.return_value = _sample_elements()
        old_time = timezone.now() - timedelta(minutes=20)
        prop = CRMProperty.objects.create(
            user=self.user,
            title='stale',
            latitude=35.7575,
            longitude=51.4100,
            nearby_pois={
                'version': PAYLOAD_VERSION,
                'status': ACCESSIBILITY_STATUS_PENDING,
                'generation_id': 'stale-gen',
                'scheduled_at': old_time.isoformat(),
                'radius_m': 3000,
            },
        )
        PropertyAccessibilityJob.objects.create(
            property=prop,
            user=self.user,
            generation_id='stale-gen',
            status='running',
            attempts=1,
            locked_at=old_time,
        )
        reconcile_stale_pending_accessibilities(timeout_minutes=15)
        prop.refresh_from_db()
        self.assertEqual(get_property_accessibility_status(prop), ACCESSIBILITY_STATUS_FAILED)
        url = reverse('workspace:crm_property_nearby_pois', kwargs={'property_id': prop.pk})
        resp = self.client.post(url, data=json.dumps({'refresh': True}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        prop.refresh_from_db()
        self.assertEqual(get_property_accessibility_status(prop), ACCESSIBILITY_STATUS_READY)

    @patch('workspace.services.nearby_pois.fetch_overpass_elements')
    def test_superseded_generation_cannot_overwrite(self, mock_fetch):
        from django.utils import timezone

        from workspace.models import PropertyAccessibilityJob
        from workspace.services.nearby_pois import (
            _build_payload,
            _save_accessibility_payload,
            mark_property_accessibilities_pending,
        )

        mock_fetch.return_value = _sample_elements()
        prop = CRMProperty.objects.create(
            user=self.user,
            title='supersede',
            latitude=35.7575,
            longitude=51.4100,
        )
        location = resolve_property_location(prop)
        old_gen = mark_property_accessibilities_pending(prop, location=location)
        new_gen = mark_property_accessibilities_pending(prop, location=location)
        self.assertNotEqual(old_gen, new_gen)

        items = resolve_nearby_items(35.7575, 51.4100, _sample_elements())
        stale_payload = _build_payload(
            35.7575,
            51.4100,
            items,
            fetched_at=timezone.now(),
            radius_m=3000,
            generation_id=old_gen,
        )
        self.assertFalse(_save_accessibility_payload(prop, stale_payload, generation_id=old_gen))

        PropertyAccessibilityJob.objects.create(
            property=prop,
            user=self.user,
            generation_id=new_gen,
            status='queued',
        )
        self._run_scheduled()
        prop.refresh_from_db()
        self.assertEqual(get_property_accessibility_status(prop), ACCESSIBILITY_STATUS_READY)
        self.assertEqual(prop.nearby_pois.get('generation_id'), new_gen)
