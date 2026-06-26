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

    path('dashboard', views.DashboardView.as_view(), name='dashboard'),

    path('settings/profile', views.ProfileView.as_view(), name='profile'),
    path('settings/notifications', views.NotificationPrefsView.as_view(), name='notifications'),

    path('notifications', views.NotificationsListView.as_view(), name='notifications_list'),
    path('notifications/unread-count', views.NotificationsUnreadView.as_view(), name='notifications_unread'),
    path('notifications/<int:notification_id>/read', views.NotificationReadView.as_view(), name='notification_read'),

    path('sync', views.SyncPullView.as_view(), name='sync_pull'),
    path('sync/push', views.SyncPushView.as_view(), name='sync_push'),

    path('crm/contacts', views.ContactsListView.as_view(), name='contacts'),
    path('crm/contacts/quick-lead', views.QuickLeadView.as_view(), name='quick_lead'),
    path('crm/contacts/<int:contact_id>', views.ContactDetailView.as_view(), name='contact_detail'),
    path('crm/contacts/<int:contact_id>/activities', views.ContactActivitiesView.as_view(), name='contact_activities'),
    path('crm/contacts/<int:contact_id>/notes', views.ContactNotesView.as_view(), name='contact_notes'),
    path('crm/contacts/<int:contact_id>/reminders', views.ContactRemindersView.as_view(), name='contact_reminders'),
    path('crm/contacts/<int:contact_id>/listings', views.ContactListingsLinkView.as_view(), name='contact_listings'),
    path('crm/today', views.TodayView.as_view(), name='today'),
    path('crm/today/actions', views.TodayTaskActionView.as_view(), name='today_actions'),
    path('crm/reminders/<int:reminder_id>', views.ReminderDetailView.as_view(), name='reminder_detail'),

    path('filing/datasets', views.DatasetsListView.as_view(), name='datasets'),
    path('filing/datasets/<uuid:dataset_id>', views.DatasetDetailView.as_view(), name='dataset_detail'),
    path('filing/datasets/<uuid:dataset_id>/listings', views.DatasetListingsView.as_view(), name='dataset_listings'),
    path('filing/listings/<str:token>', views.ListingDetailView.as_view(), name='listing_detail'),

    path('extractions/limits', views.ExtractionLimitsView.as_view(), name='extraction_limits'),
    path('extractions/upload', views.ExtractionUploadView.as_view(), name='extraction_upload'),
]
