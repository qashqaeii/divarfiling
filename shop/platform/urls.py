"""URL patterns for platform pages."""
from django.urls import path

from shop.platform import views

urlpatterns = [
    path(
        'features/',
        views.PlatformFeaturesView.as_view(),
        name='platform_features_hub',
    ),
    path(
        'features/<path:slug_path>/',
        views.PlatformFeaturesView.as_view(),
        name='platform_features_page',
    ),
    path(
        'solutions/',
        views.PlatformSolutionsView.as_view(),
        name='platform_solutions_hub',
    ),
    path(
        'solutions/<slug:slug>/',
        views.PlatformSolutionsView.as_view(),
        name='platform_solutions_page',
    ),
]
