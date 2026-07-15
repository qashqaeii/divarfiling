"""URLهای AI workspace."""
from django.urls import path

from ai_workspace import views

app_name = 'ai_workspace'

urlpatterns = [
    path('quota/', views.AIQuotaView.as_view(), name='quota'),
    path(
        'listings/<uuid:dataset_id>/<int:listing_id>/summary/',
        views.ListingSummaryView.as_view(),
        name='listing_summary',
    ),
    path(
        'crm/properties/<int:property_id>/summary/',
        views.PropertySummaryView.as_view(),
        name='property_summary',
    ),
    path(
        'crm/contacts/<int:customer_id>/message/',
        views.CRMMessageView.as_view(),
        name='crm_message',
    ),
    path('datasets/upload-brief/', views.UploadBriefView.as_view(), name='upload_brief'),
]
