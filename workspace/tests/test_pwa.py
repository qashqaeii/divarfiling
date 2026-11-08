"""Tests for workspace PWA manifest, service worker, and install-suggest UX."""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

User = get_user_model()


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


class WorkspacePwaInstallSuggestAssetTests(SimpleTestCase):
    def test_policy_and_client_contract(self):
        base = Path(settings.BASE_DIR)
        policy = (base / 'static' / 'workspace' / 'js' / 'pwa-install-policy.js').read_text(encoding='utf-8')
        client_js = (base / 'static' / 'workspace' / 'js' / 'pwa.js').read_text(encoding='utf-8')

        self.assertIn('DISMISS_DAYS = 7', policy)
        self.assertIn('shouldAutoSuggest', policy)
        self.assertIn('ws-pwa-suggest-dismiss-until', policy)
        self.assertIn('ws-pwa-installed', policy)

        self.assertIn('beforeinstallprompt', client_js)
        self.assertIn('promptEvent.prompt()', client_js)
        self.assertIn('modal-pwa-install', client_js)
        self.assertIn('data-ws-pwa-suggest-install', client_js)
        self.assertIn('data-ws-pwa-suggest-dismiss', client_js)
        self.assertIn('scheduleAutoSuggest', client_js)
        self.assertIn('hasBlockingUi', client_js)
        self.assertIn('appinstalled', client_js)
        # Never auto-call the system prompt without a click path.
        self.assertNotRegex(client_js, r'beforeinstallprompt[\s\S]{0,400}\.prompt\(')


@override_settings(ROOT_URLCONF='divar_shop.urls')
class WorkspacePwaInstallSuggestMarkupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09129990011',
            phone='09129990011',
            password='pass12345',
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_workspace_shell_includes_suggest_modal_and_scripts(self):
        resp = self.client.get(reverse('workspace:home'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="modal-pwa-install"')
        self.assertContains(resp, 'میزکار فایلینگ دیوار، همیشه در دسترس')
        self.assertContains(
            resp,
            'میزکارت رو مثل یک اپلیکیشن مستقل روی گوشی نصب کن و سریع‌تر به فایل‌ها، مشتری‌ها و کارهات دسترسی داشته باش.',
        )
        self.assertContains(resp, 'نصب اپلیکیشن')
        self.assertContains(resp, 'فعلاً نه')
        self.assertContains(resp, 'data-ws-pwa-suggest-install')
        self.assertContains(resp, 'data-ws-pwa-suggest-dismiss')
        self.assertContains(resp, 'workspace/js/pwa-install-policy.js')
        self.assertContains(resp, 'workspace/js/pwa.js')
        self.assertContains(resp, 'workspace/css/pwa.css')
