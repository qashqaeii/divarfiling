"""
URLهای API لایسنس
"""
from django.urls import path
from . import api_views

urlpatterns = [
    path('licenses/activate/', api_views.ActivateLicenseView.as_view(), name='api_activate_license'),
    path('licenses/validate/', api_views.ValidateLicenseView.as_view(), name='api_validate_license'),
    path('licenses/deactivate/', api_views.DeactivateLicenseView.as_view(), name='api_deactivate_license'),
]

