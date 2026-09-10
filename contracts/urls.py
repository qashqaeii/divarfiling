"""URLهای قرارداد."""
from django.urls import path

from contracts import handover_public_views, handover_views, public_views, views

app_name = 'contracts'

public_urlpatterns = [
    path('c/accept/<str:token>/', public_views.PublicAcceptView.as_view(), name='public_accept'),
    path('contracts/verify/<str:token>/', public_views.PublicVerifyView.as_view(), name='public_verify'),
    path('c/view/<str:token>/', public_views.PublicFinalViewView.as_view(), name='public_view'),
    path('c/view/<str:token>/pdf/', public_views.PublicFinalPdfView.as_view(), name='public_view_pdf'),
    path('c/view/<str:token>/handover/pdf/', public_views.PublicHandoverPdfView.as_view(), name='public_handover_pdf'),
    path('c/view/<str:token>/attachment/<int:attachment_id>/', public_views.PublicContractAttachmentView.as_view(), name='public_view_attachment'),
    path('c/handover/<str:token>/', handover_public_views.PublicHandoverAcceptView.as_view(), name='public_handover_accept'),
    path('c/handover/<str:token>/pdf/', handover_public_views.PublicHandoverInvitationPdfView.as_view(), name='public_handover_invitation_pdf'),
]

# مسیرهای کاننیکال (بدون deal_id در URL)
standalone_urlpatterns = [
    path('crm/contracts/', views.ContractsDashboardView.as_view(), name='contracts_dashboard'),
    path('crm/contracts/api/deals/', views.DealSearchApiView.as_view(), name='contract_deal_search'),
    path('crm/contracts/create/', views.ContractCreateStandaloneView.as_view(), name='contract_create_standalone'),
    path(
        'crm/contracts/<int:contract_id>/wizard/',
        views.ContractWizardView.as_view(),
        name='contract_wizard_standalone',
    ),
    path(
        'crm/contracts/<int:contract_id>/',
        views.ContractManageView.as_view(),
        name='contract_manage_standalone',
    ),
    path(
        'crm/contracts/<int:contract_id>/pdf/',
        views.ContractPdfDownloadView.as_view(),
        name='contract_pdf_standalone',
    ),
    path(
        'crm/contracts/<int:contract_id>/pdf/preview/',
        views.ContractPdfPreviewView.as_view(),
        name='contract_pdf_preview_standalone',
    ),
    path(
        'crm/contracts/<int:contract_id>/handover/create/',
        handover_views.HandoverCreateView.as_view(),
        name='handover_create_standalone',
    ),
    path(
        'crm/contracts/<int:contract_id>/handover/<int:handover_id>/wizard/',
        handover_views.HandoverWizardView.as_view(),
        name='handover_wizard_standalone',
    ),
    path(
        'crm/contracts/<int:contract_id>/handover/<int:handover_id>/pdf/',
        handover_views.HandoverPdfDownloadView.as_view(),
        name='handover_pdf_standalone',
    ),
]

# مسیرهای سازگار با گذشته (deal در URL)
legacy_deal_urlpatterns = [
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
        'crm/deals/<int:deal_id>/contracts/<int:contract_id>/pdf/preview/',
        views.ContractPdfPreviewView.as_view(),
        name='contract_pdf_preview',
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
]

workspace_urlpatterns = standalone_urlpatterns + legacy_deal_urlpatterns
urlpatterns = public_urlpatterns + workspace_urlpatterns
