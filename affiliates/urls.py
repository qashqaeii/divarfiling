"""
URLهای افیلیت
"""
from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.AffiliateRegisterView.as_view(), name='affiliate_register'),
    path('dashboard/', views.AffiliateDashboardView.as_view(), name='affiliate_dashboard'),
    path('withdrawal/', views.WithdrawalCreateView.as_view(), name='affiliate_withdrawal'),
    path('transactions/', views.WalletTransactionListView.as_view(), name='affiliate_transactions'),
]

