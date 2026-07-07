"""
ویوهای افیلیت
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, CreateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Sum, Count
from django.conf import settings
from affiliates.services.referral import build_referral_url, get_referred_users_data
from .models import Affiliate, AffiliateSale, AffiliatePayout, Wallet, WalletTransaction, Withdrawal
from .forms import WithdrawalForm


class AffiliateRegisterView(LoginRequiredMixin, CreateView):
    """ثبت‌نام به عنوان مشاور"""
    model = Affiliate
    fields = []
    template_name = 'affiliates/register.html'
    success_url = reverse_lazy('affiliate_dashboard')
    
    def form_valid(self, form):
        if Affiliate.objects.filter(user=self.request.user).exists():
            messages.warning(self.request, 'شما قبلاً به عنوان مشاور ثبت‌نام کرده‌اید.')
            return redirect('affiliate_dashboard')
        
        affiliate = form.save(commit=False)
        affiliate.user = self.request.user
        affiliate.save()
        
        messages.success(self.request, 'ثبت‌نام شما به عنوان مشاور با موفقیت انجام شد.')
        return super().form_valid(form)


class AffiliateDashboardView(LoginRequiredMixin, TemplateView):
    """داشبورد مشاور"""
    template_name = 'affiliates/dashboard.html'
    
    def dispatch(self, request, *args, **kwargs):
        try:
            self.affiliate = Affiliate.objects.get(user=request.user)
        except Affiliate.DoesNotExist:
            return redirect('affiliate_register')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        affiliate = self.affiliate
        
        # دریافت یا ایجاد کیف پول
        wallet, created = Wallet.objects.get_or_create(user=self.request.user)
        
        # آمار فروش
        total_sales = AffiliateSale.objects.filter(affiliate=affiliate)
        pending_sales = total_sales.filter(status='pending')
        paid_sales = total_sales.filter(status='paid')
        
        total_commission = sum(sale.commission_amount for sale in total_sales)
        pending_commission = sum(sale.commission_amount for sale in pending_sales)
        paid_commission = sum(sale.commission_amount for sale in paid_sales)
        
        # تسویه حساب‌ها
        payouts = AffiliatePayout.objects.filter(affiliate=affiliate).order_by('-created_at')[:10]
        
        referral_url = build_referral_url(self.request, affiliate)
        referred = get_referred_users_data(affiliate)
        
        # آمار کیف پول
        recent_transactions = wallet.transactions.order_by('-created_at')[:10]
        recent_withdrawals = wallet.withdrawals.order_by('-created_at')[:10]
        
        context.update({
            'affiliate': affiliate,
            'wallet': wallet,
            'total_sales_count': total_sales.count(),
            'total_commission': total_commission,
            'pending_commission': pending_commission,
            'paid_commission': paid_commission,
            'recent_sales': total_sales.order_by('-created_at')[:10],
            'payouts': payouts,
            'referral_url': referral_url,
            'recent_transactions': recent_transactions,
            'recent_withdrawals': recent_withdrawals,
            'min_withdrawal': settings.AFFILIATE_MIN_WITHDRAWAL,
            'referred_users_count': referred['total'],
            'referred_users_with_orders': referred['with_orders'],
            'referred_users_without_orders': referred['without_orders'],
            'referred_users': referred['items'],
        })
        
        return context


class WithdrawalCreateView(LoginRequiredMixin, CreateView):
    """درخواست برداشت از کیف پول"""
    model = Withdrawal
    form_class = WithdrawalForm
    template_name = 'affiliates/withdrawal_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        try:
            self.affiliate = Affiliate.objects.get(user=request.user)
        except Affiliate.DoesNotExist:
            messages.error(request, 'شما به عنوان مشاور ثبت‌نام نکرده‌اید.')
            return redirect('affiliate_register')
        
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        self.wallet = wallet
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['wallet'] = self.wallet
        return kwargs
    
    def form_valid(self, form):
        withdrawal = form.save(commit=False)
        withdrawal.wallet = self.wallet
        
        if withdrawal.amount > self.wallet.balance:
            messages.error(self.request, 'موجودی کیف پول شما کافی نیست.')
            return self.form_invalid(form)
        
        withdrawal.save()
        messages.success(self.request, 'درخواست برداشت شما با موفقیت ثبت شد. پس از بررسی، پرداخت انجام خواهد شد.')
        return redirect('affiliate_dashboard')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['wallet'] = self.wallet
        context['min_withdrawal'] = settings.AFFILIATE_MIN_WITHDRAWAL
        return context


class WalletTransactionListView(LoginRequiredMixin, ListView):
    """لیست تراکنش‌های کیف پول"""
    model = WalletTransaction
    template_name = 'affiliates/wallet_transactions.html'
    paginate_by = 20
    context_object_name = 'transactions'
    
    def dispatch(self, request, *args, **kwargs):
        try:
            self.affiliate = Affiliate.objects.get(user=request.user)
        except Affiliate.DoesNotExist:
            messages.error(request, 'شما به عنوان مشاور ثبت‌نام نکرده‌اید.')
            return redirect('affiliate_register')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        wallet, created = Wallet.objects.get_or_create(user=self.request.user)
        return wallet.transactions.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        wallet, created = Wallet.objects.get_or_create(user=self.request.user)
        context['wallet'] = wallet
        return context

