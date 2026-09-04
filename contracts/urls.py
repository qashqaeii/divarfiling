"""URLهای قرارداد."""
from django.urls import path

from contracts import handover_public_views, handover_views, public_views, views

app_name = 'contracts'

public_urlpatterns = [
    path('c/accept/<str:token>/', public_views.PublicAcceptView.as_view(), name='public_accept'),
    path('contracts/verify/<str:token>/', public_views.PublicVerifyView.as_view(), name='public_verify'),
    path('c/view/<str:token>/', public_views.PublicFinalViewView.as_view(), name='public_view'),
    path('c/handover/<str:token>/', handover_public_views.PublicHandoverAcceptView.as_view(), name='public_handover_accept'),
]

workspace_urlpatterns = [
    path(
        'crm/deals/<int:deal_id>/contracts/',
        views.DealContractsSectionView.as_view(),
        name='deal_contracts',
    ),
    path(
        'crm/deals/<int:deal_id>/contracts/create/',
        views.ContractCreateView.as_view(),
        name='contract_create',
    ),
    path(
        'crm/deals/<int:deal_id>/contracts/<int:contract_id>/wizard/',
        views.ContractWizardView.as_view(),
        name='contract_wizard',
    ),
    path(
        'crm/deals/<int:deal_id>/contracts/<int:contract_id>/',
        views.ContractManageView.as_view(),
        name='contract_manage',
    ),
    path(
        'crm/deals/<int:deal_id>/contracts/<int:contract_id>/pdf/',
        views.ContractPdfDownloadView.as_view(),
        name='contract_pdf',
    ),
    path(
        'crm/deals/<int:deal_id>/contracts/<int:contract_id>/attachments/<int:attachment_id>/',
        handover_views.ContractAttachmentDownloadView.as_view(),
        name='contract_attachment_download',
    ),
    path(
        'crm/deals/<int:deal_id>/contracts/<int:contract_id>/attachments/upload/',
        handover_views.ContractAttachmentUploadView.as_view(),
        name='contract_attachment_upload',
    ),
    path(
        'crm/deals/<int:deal_id>/contracts/<int:contract_id>/handover/create/',
        handover_views.HandoverCreateView.as_view(),
        name='handover_create',
    ),
    path(
        'crm/deals/<int:deal_id>/contracts/<int:contract_id>/handover/<int:handover_id>/wizard/',
        handover_views.HandoverWizardView.as_view(),
        name='handover_wizard',
    ),
    path(
        'crm/deals/<int:deal_id>/contracts/<int:contract_id>/handover/<int:handover_id>/pdf/',
        handover_views.HandoverPdfDownloadView.as_view(),
        name='handover_pdf',
    ),
    path('crm/contracts/', views.ContractsDashboardView.as_view(), name='contracts_dashboard'),
]

urlpatterns = public_urlpatterns + workspace_urlpatterns
