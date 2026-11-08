"""Tests for workspace PWA manifest and service worker endpoints."""
from django.test import SimpleTestCase, override_settings
from django.urls import reverse


@override_settings(ROOT_URLCONF='divar_shop.urls')
class WorkspacePwaEndpointsTests(SimpleTestCase):
    def test_manifest_content_type_and_scope(self):
        url = reverse('workspace:web_manifest')
        self.assertEqual(url, '/workspace/manifest.webmanifest')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('application/manifest+json', response['Content-Type'])
        data = response.json()
        self.assertEqual(data['id'], '/workspace/')
        self.assertEqual(data['scope'], '/workspace/')
        self.assertEqual(data['start_url'], '/workspace/?utm_source=pwa')
        self.assertEqual(data['display'], 'standalone')
        self.assertEqual(data['lang'], 'fa')
        self.assertEqual(data['dir'], 'rtl')
        self.assertEqual(data['theme_color'], '#7C3AED')
        self.assertEqual(data['background_color'], '#F8FAFC')
        self.assertEqual(data.get('handle_links'), 'preferred')
        self.assertIn('launch_handler', data)
        purposes = {icon.get('purpose') for icon in data['icons']}
        self.assertIn('any', purposes)
        self.assertIn('maskable', purposes)
        for icon in data['icons']:
            self.assertIn('/static/workspace/pwa/icons/', icon['src'])

    def test_service_worker_scope_headers_and_network_only_policy(self):
        url = reverse('workspace:service_worker')
        self.assertEqual(url, '/workspace/sw.js')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('javascript', response['Content-Type'])
        self.assertEqual(response['Service-Worker-Allowed'], '/workspace/')
        self.assertIn('no-cache', response['Cache-Control'])
        body = response.content.decode('utf-8')
        self.assertIn("CACHE_VERSION = 'ws-pwa-v1'", body)
        self.assertIn('/static/workspace/pwa/offline.html', body)
        self.assertIn('isWorkspaceNavigation', body)
        self.assertIn('OFFLINE_CACHE', body)
        # Security: no runtime caching of workspace HTML/API — only offline shell.
        self.assertNotIn('cache.put(request', body)
        self.assertNotIn('__WS_PWA_CACHE_VERSION__', body)
        self.assertNotIn('__WS_PWA_OFFLINE_URL__', body)

    def test_manifest_and_sw_do_not_require_login(self):
        """Installability tooling must fetch these without a session."""
        self.assertEqual(self.client.get(reverse('workspace:web_manifest')).status_code, 200)
        self.assertEqual(self.client.get(reverse('workspace:service_worker')).status_code, 200)
