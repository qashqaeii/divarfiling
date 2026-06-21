"""URLهای workspace."""
from django.urls import path

from workspace import crm_views, views

app_name = 'workspace'

urlpatterns = [
    path('', views.WorkspaceHomeView.as_view(), name='home'),
    path('api/onboarding/complete/', views.OnboardingCompleteView.as_view(), name='onboarding_complete'),

    # Datasets
    path('datasets/', views.DatasetListView.as_view(), name='dataset_list'),
    path('datasets/upload/', views.DatasetUploadView.as_view(), name='dataset_upload'),
    path('datasets/upload/bulk/', views.DatasetBulkUploadView.as_view(), name='dataset_bulk_upload'),
    path('datasets/<uuid:dataset_id>/', views.DatasetDetailView.as_view(), name='dataset_detail'),
    path('datasets/bulk-delete/', views.DatasetBulkDeleteView.as_view(), name='dataset_bulk_delete'),
    path('datasets/<uuid:dataset_id>/delete/', views.DatasetDeleteView.as_view(), name='dataset_delete'),
    path('datasets/<uuid:dataset_id>/rename/', views.DatasetRenameView.as_view(), name='dataset_rename'),
    path('datasets/<uuid:dataset_id>/export/', views.DatasetExportView.as_view(), name='dataset_export'),
    path('datasets/<uuid:dataset_id>/analyze/', views.DatasetAnalyzeView.as_view(), name='dataset_analyze'),
    path('datasets/<uuid:dataset_id>/map/', views.DatasetMapView.as_view(), name='dataset_map'),

    # Listings
    path('datasets/<uuid:dataset_id>/listings/<int:listing_id>/', views.ListingDetailView.as_view(), name='listing_detail'),
    path('datasets/<uuid:dataset_id>/listings/<int:listing_id>/edit/', views.ListingUpdateView.as_view(), name='listing_edit'),
    path('datasets/<uuid:dataset_id>/listings/<int:listing_id>/delete/', views.ListingDeleteView.as_view(), name='listing_delete'),
    path('datasets/<uuid:dataset_id>/listings/<int:listing_id>/favorite/', views.ListingFavoriteToggleView.as_view(), name='listing_favorite_toggle'),
    path('datasets/<uuid:dataset_id>/listings/<int:listing_id>/personal/', views.ListingAddToPersonalFilesView.as_view(), name='listing_add_personal'),
    path('datasets/<uuid:dataset_id>/delete-consultants/', views.DeleteConsultantsView.as_view(), name='dataset_delete_consultants'),
    path('datasets/<uuid:dataset_id>/listings/<int:listing_id>/benchmark/', views.BenchmarkAPIView.as_view(), name='listing_benchmark'),

    # Tools & Compare
    path('tools/', views.ToolsView.as_view(), name='tools'),
    path('compare/', views.CompareView.as_view(), name='compare'),

    # CRM
    path('crm/', crm_views.CRMDashboardView.as_view(), name='crm_dashboard'),
    path('crm/team/', crm_views.CRMTeamView.as_view(), name='crm_team'),
    path('crm/team/assign/<int:customer_id>/', crm_views.CRMTeamAssignView.as_view(), name='crm_team_assign'),
    path('crm/team/transfer/<int:customer_id>/', crm_views.CRMTeamTransferView.as_view(), name='crm_team_transfer'),
    path('crm/team/share-property/<int:property_id>/', crm_views.CRMPropertyShareView.as_view(), name='crm_property_share'),
    path('crm/shares/<int:share_id>/revoke/', crm_views.CRMShareRevokeView.as_view(), name='crm_share_revoke'),
    path('crm/deals/<int:deal_id>/commission/', crm_views.CRMDealCommissionSplitView.as_view(), name='crm_deal_commission'),
    path('crm/sync/export/', crm_views.CRMSyncExportView.as_view(), name='crm_sync_export'),
    path('crm/sync/import/', crm_views.CRMSyncImportView.as_view(), name='crm_sync_import'),
    path('crm/api/leads/', crm_views.CRMInboundLeadAPIView.as_view(), name='crm_api_leads'),
    path('crm/today/', crm_views.CRMTodayView.as_view(), name='crm_today'),
    path('crm/search/', crm_views.CRMGlobalSearchView.as_view(), name='crm_search'),
    path('crm/contacts/', crm_views.CustomerListView.as_view(), name='crm_contacts'),
    path('crm/contacts/quick/', crm_views.CustomerQuickCreateView.as_view(), name='crm_quick_lead'),
    path('crm/contacts/<int:customer_id>/status/', crm_views.CustomerStatusUpdateView.as_view(), name='crm_contact_status'),
    path('crm/contacts/<int:customer_id>/panel/', crm_views.CustomerPanelView.as_view(), name='crm_contact_panel'),
    path('crm/contacts/new/', crm_views.CustomerCreateView.as_view(), name='crm_create'),
    path('crm/contacts/<int:customer_id>/', crm_views.CustomerDetailView.as_view(), name='crm_detail'),
    path('crm/contacts/<int:customer_id>/edit/', crm_views.CustomerUpdateView.as_view(), name='crm_edit'),
    path('crm/contacts/<int:customer_id>/delete/', crm_views.CustomerDeleteView.as_view(), name='crm_delete'),
    path('crm/contacts/export/', crm_views.CustomerExportView.as_view(), name='crm_export'),
    path('crm/contacts/import/', crm_views.CustomerImportView.as_view(), name='crm_import'),
    path('crm/contacts/import/template/', crm_views.CustomerImportTemplateView.as_view(), name='crm_import_template'),
    path('crm/contacts/bulk/', crm_views.CustomerBulkActionView.as_view(), name='crm_bulk'),
    path('crm/contacts/merge/', crm_views.CustomerMergeView.as_view(), name='crm_merge'),
    path('crm/deals/', crm_views.CRMDealListView.as_view(), name='crm_deals'),
    path('crm/deals/stages/', crm_views.CRMDealStagesView.as_view(), name='crm_deal_stages'),
    path('crm/deals/new/', crm_views.CRMDealCreateView.as_view(), name='crm_deal_create'),
    path('crm/deals/<int:deal_id>/', crm_views.CRMDealDetailView.as_view(), name='crm_deal_detail'),
    path('crm/deals/<int:deal_id>/edit/', crm_views.CRMDealUpdateView.as_view(), name='crm_deal_edit'),
    path('crm/deals/<int:deal_id>/stage/', crm_views.CRMDealStageUpdateView.as_view(), name='crm_deal_stage'),
    path('crm/deals/<int:deal_id>/checklist/', crm_views.CRMDealChecklistView.as_view(), name='crm_deal_checklist'),
    path('crm/properties/', crm_views.CRMPropertyListView.as_view(), name='crm_properties'),
    path('crm/properties/export/', crm_views.CRMPropertyExportView.as_view(), name='crm_properties_export'),  # خروجی Excel/CSV
    path('crm/properties/new/', crm_views.CRMPropertyCreateView.as_view(), name='crm_property_create'),
    path('crm/properties/<int:property_id>/', crm_views.CRMPropertyDetailView.as_view(), name='crm_property_detail'),
    path('crm/properties/<int:property_id>/edit/', crm_views.CRMPropertyUpdateView.as_view(), name='crm_property_edit'),
    path('crm/properties/<int:property_id>/status/', crm_views.CRMPropertyStatusUpdateView.as_view(), name='crm_property_status'),
    path('crm/properties/pipeline-order/', crm_views.CRMPropertyPipelineOrderView.as_view(), name='crm_property_pipeline_order'),
    path('crm/properties/<int:property_id>/delete/', crm_views.CRMPropertyDeleteView.as_view(), name='crm_property_delete'),
    path('crm/filters/', crm_views.CRMSavedFilterListView.as_view(), name='crm_filters'),
    path('crm/filters/save/', crm_views.CRMSavedFilterCreateView.as_view(), name='crm_filter_save'),
    path('crm/filters/<int:filter_id>/delete/', crm_views.CRMSavedFilterDeleteView.as_view(), name='crm_filter_delete'),
    path('crm/filters/<int:filter_id>/pin/', crm_views.CRMSavedFilterPinView.as_view(), name='crm_filter_pin'),
    path('crm/reminders/', crm_views.CRMReminderListView.as_view(), name='crm_reminders'),
    path('crm/reminders/<int:reminder_id>/toggle/', crm_views.CRMReminderToggleView.as_view(), name='crm_reminder_toggle'),
    path('crm/templates/', crm_views.CRMTemplatesView.as_view(), name='crm_templates'),
    path('crm/automation/', crm_views.CRMAutomationView.as_view(), name='crm_automation'),
    path('crm/calendar/', crm_views.CRMCalendarView.as_view(), name='crm_calendar'),
    path('crm/notifications/due/', crm_views.CRMNotificationsView.as_view(), name='crm_notifications'),
    path('crm/contacts/<int:customer_id>/message-preview/', crm_views.CRMMessagePreviewView.as_view(), name='crm_message_preview'),
    # سازگاری
    path('crm/list/', crm_views.CustomerListView.as_view(), name='crm_list'),
    path('crm/<int:customer_id>/', crm_views.CustomerDetailView.as_view(), name='crm_detail_legacy'),

    # Reminders
    path('reminders/', views.ReminderListView.as_view(), name='reminder_list'),
    path('reminders/new/', views.ReminderCreateView.as_view(), name='reminder_create'),
    path('reminders/<int:reminder_id>/toggle/', views.ReminderToggleView.as_view(), name='reminder_toggle'),

    # Settings & Help
    path('settings/', views.WorkspaceSettingsView.as_view(), name='settings'),
    path('help/', views.HelpView.as_view(), name='help'),
    path('docs/api/', views.ApiDocsView.as_view(), name='docs_api'),
    path('docs/api/crm-key/', views.CrmApiKeyRevealView.as_view(), name='docs_api_crm_key'),
    path('upgrade/', views.BotUpgradeView.as_view(), name='upgrade'),
]
