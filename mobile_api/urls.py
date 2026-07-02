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
    path('crm/contacts/export', views.ContactsExportView.as_view(), name='contacts_export'),
    path('crm/contacts/quick-lead', views.QuickLeadView.as_view(), name='quick_lead'),
    path('crm/contacts/<int:contact_id>', views.ContactDetailView.as_view(), name='contact_detail'),
    path('crm/contacts/<int:contact_id>/activities', views.ContactActivitiesView.as_view(), name='contact_activities'),
    path('crm/contacts/<int:contact_id>/notes', views.ContactNotesView.as_view(), name='contact_notes'),
    path('crm/contacts/<int:contact_id>/reminders', views.ContactRemindersView.as_view(), name='contact_reminders'),
    path('crm/contacts/<int:contact_id>/listings', views.ContactListingsLinkView.as_view(), name='contact_listings'),
    path('crm/contacts/<int:contact_id>/documents', views.ContactDocumentsView.as_view(), name='contact_documents'),
    path('crm/contacts/<int:contact_id>/documents/<int:document_id>', views.ContactDocumentDetailView.as_view(), name='contact_document_detail'),
    path('crm/contacts/<int:contact_id>/send-listing', views.ContactSendListingView.as_view(), name='contact_send_listing'),
    path('crm/contacts/<int:contact_id>/matches', views.ContactMatchesView.as_view(), name='contact_matches'),
    path('crm/contacts/<int:contact_id>/suggest', views.ContactSuggestView.as_view(), name='contact_suggest'),
    path('crm/today', views.TodayView.as_view(), name='today'),
    path('crm/today/actions', views.TodayTaskActionView.as_view(), name='today_actions'),
    path('crm/reminders/<int:reminder_id>', views.ReminderDetailView.as_view(), name='reminder_detail'),

    path('crm/deals/pipeline', views.DealPipelineView.as_view(), name='deals_pipeline'),
    path('crm/deals/stages', views.DealStagesView.as_view(), name='deals_stages'),
    path('crm/deals', views.DealsListView.as_view(), name='deals'),
    path('crm/deals/<int:deal_id>', views.DealDetailView.as_view(), name='deal_detail'),
    path('crm/deals/<int:deal_id>/stage', views.DealStageView.as_view(), name='deal_stage'),
    path('crm/properties', views.PropertiesListView.as_view(), name='properties'),
    path('crm/properties/export', views.PropertiesExportView.as_view(), name='properties_export'),
    path('crm/properties/<int:property_id>', views.PropertyDetailView.as_view(), name='property_detail'),
    path('crm/properties/<int:property_id>/public-share', views.PropertyPublicShareView.as_view(), name='property_public_share'),
    path('crm/properties/<int:property_id>/status', views.PropertyStatusView.as_view(), name='property_status'),
    path('crm/properties/<int:property_id>/contacts', views.PropertyContactsView.as_view(), name='property_contacts'),
    path('crm/properties/<int:property_id>/documents', views.PropertyDocumentsView.as_view(), name='property_documents'),
    path('crm/properties/<int:property_id>/documents/<int:document_id>', views.PropertyDocumentDetailView.as_view(), name='property_document_detail'),

    path('filing/datasets', views.DatasetsListView.as_view(), name='datasets'),
    path('filing/datasets/<uuid:dataset_id>', views.DatasetDetailView.as_view(), name='dataset_detail'),
    path('filing/datasets/<uuid:dataset_id>/export', views.DatasetExportView.as_view(), name='dataset_export'),
    path('filing/datasets/<uuid:dataset_id>/listings', views.DatasetListingsView.as_view(), name='dataset_listings'),
    path('filing/datasets/<uuid:dataset_id>/insights', views.DatasetInsightsView.as_view(), name='dataset_insights'),
    path('filing/datasets/<uuid:dataset_id>/map', views.DatasetMapView.as_view(), name='dataset_map'),
    path('filing/search', views.FilingSearchView.as_view(), name='filing_search'),
    path('filing/listings/<str:token>', views.ListingDetailView.as_view(), name='listing_detail'),
    path('filing/listings/<str:token>/public-share', views.ListingPublicShareView.as_view(), name='listing_public_share'),

    path('extractions/limits', views.ExtractionLimitsView.as_view(), name='extraction_limits'),
    path('extractions/upload', views.ExtractionUploadView.as_view(), name='extraction_upload'),
    path('extractions/schedules', views.ExtractionSchedulesListView.as_view(), name='extraction_schedules'),
    path('extractions/schedules/due', views.ExtractionSchedulesDueView.as_view(), name='extraction_schedules_due'),
    path('extractions/schedules/<int:schedule_id>', views.ExtractionScheduleDetailView.as_view(), name='extraction_schedule_detail'),
    path('extractions/schedules/<int:schedule_id>/toggle', views.ExtractionScheduleToggleView.as_view(), name='extraction_schedule_toggle'),
    path('extractions/schedules/<int:schedule_id>/runs', views.ExtractionScheduleRunsView.as_view(), name='extraction_schedule_runs'),
    path('extractions/schedules/<int:schedule_id>/runs/start', views.ExtractionScheduleRunStartView.as_view(), name='extraction_schedule_run_start'),
    path('extractions/runs/<int:run_id>/fail', views.ExtractionScheduleRunFailView.as_view(), name='extraction_schedule_run_fail'),
]
