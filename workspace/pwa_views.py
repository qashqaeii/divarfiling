"""PWA endpoints for workspace — manifest + service worker (scope=/workspace/)."""
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.templatetags.static import static
from django.views import View

# Bump when SW caching strategy changes (also mirrored in sw.js CACHE_VERSION).
PWA_SW_VERSION = 'ws-pwa-v1'


def _abs_static(request, path: str) -> str:
    rel = static(path)
    return request.build_absolute_uri(rel)


class WorkspaceWebManifestView(View):
    """Serve Web App Manifest with correct Content-Type (no auth required)."""

    http_method_names = ['get', 'head', 'options']

    def get(self, request):
        icon_192 = _abs_static(request, 'workspace/pwa/icons/icon-192.png')
        icon_512 = _abs_static(request, 'workspace/pwa/icons/icon-512.png')
        mask_192 = _abs_static(request, 'workspace/pwa/icons/icon-maskable-192.png')
        mask_512 = _abs_static(request, 'workspace/pwa/icons/icon-maskable-512.png')

        payload = {
            'id': '/workspace/',
            'name': 'فایلینگ دیوار | میزکار',
            'short_name': 'فایلینگ دیوار',
            'description': 'میزکار هوشمند مدیریت املاک، مشتریان و فایل‌ها',
            'lang': 'fa',
            'dir': 'rtl',
            'start_url': '/workspace/?utm_source=pwa',
            'scope': '/workspace/',
            'display': 'standalone',
            'display_override': ['standalone', 'minimal-ui', 'browser'],
            'orientation': 'any',
            'background_color': '#F8FAFC',
            'theme_color': '#7C3AED',
            'categories': ['business', 'productivity'],
            'prefer_related_applications': False,
            'launch_handler': {
                'client_mode': ['navigate-existing', 'auto'],
            },
            'handle_links': 'preferred',
            'icons': [
                {
                    'src': icon_192,
                    'sizes': '192x192',
                    'type': 'image/png',
                    'purpose': 'any',
                },
                {
                    'src': icon_512,
                    'sizes': '512x512',
                    'type': 'image/png',
                    'purpose': 'any',
                },
                {
                    'src': mask_192,
                    'sizes': '192x192',
                    'type': 'image/png',
                    'purpose': 'maskable',
                },
                {
                    'src': mask_512,
                    'sizes': '512x512',
                    'type': 'image/png',
                    'purpose': 'maskable',
                },
            ],
        }
        response = JsonResponse(
            payload,
            json_dumps_params={'ensure_ascii': False, 'indent': 2},
        )
        # Override default application/json for installability tooling.
        response['Content-Type'] = 'application/manifest+json; charset=utf-8'
        response['Cache-Control'] = 'public, max-age=3600'
        return response


class WorkspaceServiceWorkerView(View):
    """Serve SW from /workspace/sw.js so default scope is /workspace/ only."""

    http_method_names = ['get', 'head', 'options']

    def get(self, request):
        sw_path = Path(settings.BASE_DIR) / 'static' / 'workspace' / 'pwa' / 'sw.js'
        if not sw_path.is_file():
            return HttpResponse('/* service worker missing */', status=404, content_type='application/javascript')

        content = sw_path.read_text(encoding='utf-8')
        # Inject absolute offline asset URL without baking host into the static file.
        offline_url = static('workspace/pwa/offline.html')
        content = content.replace('__WS_PWA_OFFLINE_URL__', offline_url)
        content = content.replace('__WS_PWA_CACHE_VERSION__', PWA_SW_VERSION)

        response = HttpResponse(content, content_type='application/javascript; charset=utf-8')
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Service-Worker-Allowed'] = '/workspace/'
        return response
