"""
URLهای مربوط به حساب کاربری
"""
from django.contrib.auth import views as auth_views
from django.urls import path

from . import otp_views, views
from .admin_views import AdminDashboardView, AdminExportView, AdminSystemSummaryView

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('login/otp/', otp_views.OtpLoginStartView.as_view(), name='otp_login'),
    path('login/otp/verify/', otp_views.OtpLoginVerifyView.as_view(), name='otp_login_verify'),
    path('login/otp/resend/', otp_views.OtpLoginResendView.as_view(), name='otp_login_resend'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('register/', otp_views.OtpRegisterStartView.as_view(), name='register'),
    path('register/verify/', otp_views.OtpRegisterVerifyView.as_view(), name='otp_register_verify'),
    path('register/resend/', otp_views.OtpRegisterResendView.as_view(), name='otp_register_resend'),
    path('register/set-password/', otp_views.OtpRegisterPasswordView.as_view(), name='otp_register_password'),
    path('register/with-password/', views.RegisterView.as_view(), name='register_password'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('dashboard/claim-license/', views.ClaimLicenseView.as_view(), name='claim_license'),
    path('dashboard/licenses/register-device/', views.RegisterDeviceSlotView.as_view(), name='license_register_device'),
    path('dashboard/licenses/update-device/', views.UpdateDeviceSlotView.as_view(), name='license_update_device'),
    path('dashboard/licenses/assign-seat/', views.AssignSeatView.as_view(), name='license_assign_seat'),
    path('dashboard/licenses/revoke-seat/', views.RevokeSeatView.as_view(), name='license_revoke_seat'),
    path('dashboard/licenses/remove-device/', views.RemoveDeviceSlotView.as_view(), name='license_remove_device'),
    path('admin-panel/', AdminDashboardView.as_view(), name='admin_panel'),
    path('admin-panel/export/<str:export_key>/', AdminExportView.as_view(), name='admin_panel_export'),
    path('admin-panel/system-summary.json', AdminSystemSummaryView.as_view(), name='admin_panel_system_summary'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset.html',
            email_template_name='accounts/password_reset_email.html',
            subject_template_name='accounts/password_reset_subject.txt',
            success_url='/accounts/password-reset/done/',
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url='/accounts/reset/done/',
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'),
        name='password_reset_complete',
    ),
    path('api/update-user-info/', views.UpdateUserInfoView.as_view(), name='update_user_info'),
    path('api/update-profile/', views.UpdateProfileView.as_view(), name='update_profile'),
]
