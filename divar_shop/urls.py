"""
URL configuration for divar_shop project.
"""
from django.contrib import admin
from django.contrib.sitemaps.views import index as sitemap_index, sitemap
from django.http import HttpResponsePermanentRedirect
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from divar_shop.robots import robots_txt
from divar_shop.sitemaps import sitemaps
from accounts.lead_acquisition_views import LeadClickRedirectView
from contracts.urls import public_urlpatterns as contract_public_urls


def favicon_redirect(_request):
    return HttpResponsePermanentRedirect(f'{settings.STATIC_URL}logo.ico')


urlpatterns = [
    path('favicon.ico', favicon_redirect, name='favicon'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap_index, {'sitemaps': sitemaps}, name='sitemap_index'),
    path(
        'sitemap-<section>.xml',
        sitemap,
        {'sitemaps': sitemaps},
        name='django.contrib.sitemaps.views.sitemap',
    ),
    path('admin/', admin.site.urls),
    # Wave 4 هنوز منتشر نشده — لینک‌های قدیمی را به لندینگ نرم‌افزار هدایت کن
    path(
        'property-pricing/',
        RedirectView.as_view(url='/real-estate-software/', permanent=False),
        name='property_pricing_placeholder',
    ),
    path('', include('shop.urls')),
    path('accounts/', include('accounts.urls')),
    path(
        's/t/<str:click_token>/',
        LeadClickRedirectView.as_view(),
        name='lead_click_redirect_root',
    ),
    path('api/', include('licenses.api_urls')),
    path('api/mobile/v1/', include('mobile_api.urls')),
    path('api/desktop/v1/', include('desktop_api.urls')),
    path('payment/', include('shop.payment_urls')),
    path('affiliate/', include('affiliates.urls')),
    path('blog/', include('blog.urls')),
    path('api/public-assistant/', include('public_assistant.urls')),
    path('workspace/', include('workspace.urls')),
    path('p/', include('workspace.public_urls')),
] + contract_public_urls

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    from django.core.exceptions import PermissionDenied, SuspiciousOperation
    from django.http import Http404
    from divar_shop.error_views import (
        bad_request, page_not_found, permission_denied, server_error,
    )
    from django.shortcuts import render

    def _preview_503(request):
        return render(request, 'errors/503.html', {
            'path': request.get_full_path(),
            'is_workspace': False,
        }, status=503)

    urlpatterns += [
        path('__preview__/errors/400/', lambda r: bad_request(r, SuspiciousOperation())),
        path('__preview__/errors/403/', lambda r: permission_denied(r, PermissionDenied())),
        path('__preview__/errors/404/', lambda r: page_not_found(r, Http404())),
        path('__preview__/errors/500/', server_error),
        path('__preview__/errors/503/', _preview_503),
    ]

handler400 = 'divar_shop.error_views.bad_request'
handler403 = 'divar_shop.error_views.permission_denied'
handler404 = 'divar_shop.error_views.page_not_found'
handler500 = 'divar_shop.error_views.server_error'
