"""URLهای API موبایل — /api/mobile/v1/"""
from django.urls import path

from mobile_api import views

app_name = 'mobile_api'

urlpatterns = [
    path('auth/login', views.LoginView.as_view(), name='login'),
    path('auth/refresh', views.RefreshView.as_view(), name='refresh'),
    path('auth/logout', views.LogoutView.as_view(), name='logout'),

    path('devices/register', views.DeviceRegisterView.as_view(), name='device_register'),
    path('devices/me', views.DevicePatchView.as_view(), name='device_patch'),

    path('license/status', views.LicenseStatusView.as_view(), name='license_status'),

    path('settings/profile', views.ProfileView.as_view(), name='profile'),
    path('settings/notifications', views.NotificationPrefsView.as_view(), name='notifications'),

    path('sync', views.SyncPullView.as_view(), name='sync_pull'),
    path('sync/push', views.SyncPushView.as_view(), name='sync_push'),

    path('crm/contacts', views.ContactsListView.as_view(), name='contacts'),
    path('crm/contacts/<int:contact_id>', views.ContactDetailView.as_view(), name='contact_detail'),
    path('crm/contacts/quick-lead', views.QuickLeadView.as_view(), name='quick_lead'),
    path('crm/today', views.TodayView.as_view(), name='today'),

    path('filing/datasets', views.DatasetsListView.as_view(), name='datasets'),
    path('filing/datasets/<uuid:dataset_id>/listings', views.DatasetListingsView.as_view(), name='dataset_listings'),
    path('filing/listings/<str:token>', views.ListingDetailView.as_view(), name='listing_detail'),

    path('extractions/limits', views.ExtractionLimitsView.as_view(), name='extraction_limits'),
    path('extractions/upload', views.ExtractionUploadView.as_view(), name='extraction_upload'),
]
