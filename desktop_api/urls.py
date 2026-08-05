"""URLهای API دسکتاپ — /api/desktop/v1/"""
from django.urls import path

from desktop_api import views

app_name = 'desktop_api'

urlpatterns = [
    path('auth/login', views.LoginView.as_view(), name='login'),
    path('auth/refresh', views.RefreshView.as_view(), name='refresh'),
    path('auth/logout', views.LogoutView.as_view(), name='logout'),
    path('licenses/eligible', views.EligibleLicensesView.as_view(), name='licenses_eligible'),
    path('licenses/bind', views.BindLicenseView.as_view(), name='licenses_bind'),
    path('licenses/validate-session', views.ValidateSessionView.as_view(), name='validate_session'),
]
