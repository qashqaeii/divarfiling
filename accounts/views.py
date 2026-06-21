"""
ویوهای مربوط به حساب کاربری
"""
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import TemplateView, CreateView, UpdateView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse
import json
from .models import User, UserProfile
from .forms import RegisterForm, ProfileForm, UserInfoForm, LoginForm
from licenses.dashboard_views import (
    AssignSeatView,
    RegisterDeviceSlotView,
    RemoveDeviceSlotView,
    RevokeSeatView,
    UpdateDeviceSlotView,
)


class LoginView(LoginView):
    template_name = 'accounts/login.html'
    form_class = LoginForm
    redirect_authenticated_user = True
    
    def get_success_url(self):
        # بررسی وجود پارامتر next در URL
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url:
            return next_url
        return reverse_lazy('workspace:home')


class LogoutView(LogoutView):
    next_page = 'home'


class RegisterView(CreateView):
    model = User
    form_class = RegisterForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('workspace:home')
    
    def get_success_url(self):
        # بررسی وجود پارامتر next در URL
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url:
            return next_url
        return reverse_lazy('workspace:home')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        phone = form.cleaned_data.get('phone')
        password = form.cleaned_data.get('password1')
        user = authenticate(username=phone, password=password)
        if user:
            # بررسی کد افیلیت از cookie
            from affiliates.middleware import AffiliateTrackingMiddleware
            from django.conf import settings
            affiliate = AffiliateTrackingMiddleware.get_affiliate_from_request(self.request)
            
            if affiliate:
                user.referred_by = affiliate
                user.save()
            
            login(self.request, user)
            # ایجاد پروفایل
            UserProfile.objects.get_or_create(user=user)
        return response


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from shop.models import Order, Transaction
        from licenses.models import License
        from django.db.models import Count, Sum, Q
        from django.utils import timezone
        
        user = self.request.user
        
        # آمار کلی
        total_orders = Order.objects.filter(user=user).count()
        paid_orders = Order.objects.filter(user=user, status='paid').count()
        total_licenses = License.objects.filter(order__user=user).count()
        active_licenses = License.objects.filter(
            order__user=user,
            order__status='paid',
            status='active',
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).count()
        total_spent = Order.objects.filter(user=user, status='paid').aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        # سفارش‌ها
        orders = Order.objects.filter(user=user).select_related('product', 'plan').order_by('-created_at')
        
        # فیلتر سفارش‌ها
        status_filter = self.request.GET.get('order_status', '')
        if status_filter:
            orders = orders.filter(status=status_filter)
        
        search_query = self.request.GET.get('order_search', '')
        if search_query:
            orders = orders.filter(
                Q(product__title__icontains=search_query) |
                Q(id__icontains=search_query)
            )
        
        # لایسنس‌ها
        licenses = License.objects.filter(order__user=user).select_related('order', 'order__product', 'plan').order_by('-created_at')

        from licenses.services.management import build_license_dashboard
        license_dashboard = build_license_dashboard(user)

        # سفارش‌های paid بدون لایسنس — نیاز به ثبت شناسه سخت‌افزار
        from django.db.models import Exists, OuterRef
        orders_pending_claim = Order.objects.filter(
            user=user,
            status='paid',
        ).annotate(
            has_license=Exists(License.objects.filter(order_id=OuterRef('pk'))),
        ).filter(has_license=False).select_related('product', 'plan').order_by('-paid_at', '-created_at')
        
        # فیلتر لایسنس‌ها
        license_status_filter = self.request.GET.get('license_status', '')
        if license_status_filter:
            licenses = licenses.filter(status=license_status_filter)
        
        # تراکنش‌ها
        transactions = Transaction.objects.filter(order__user=user).select_related('order').order_by('-created_at')
        
        # محصولات فعال برای خرید لایسنس جدید
        from shop.models import Product
        products = Product.objects.filter(is_active=True).prefetch_related('plans').order_by('order', '-created_at')
        
        # اطلاعات افیلیت (اگر کاربر خرید انجام داده باشد)
        affiliate = None
        affiliate_wallet = None
        affiliate_stats = {}
        has_paid_orders = paid_orders > 0
        
        if has_paid_orders:
            try:
                from affiliates.models import Affiliate, Wallet, AffiliateSale
                affiliate = Affiliate.objects.filter(user=user).first()
                
                if affiliate:
                    # دریافت یا ایجاد کیف پول
                    affiliate_wallet, created = Wallet.objects.get_or_create(user=user)
                    
                    # آمار افیلیت
                    total_sales = AffiliateSale.objects.filter(affiliate=affiliate)
                    from django.conf import settings
                    affiliate_stats = {
                        'total_sales_count': total_sales.count(),
                        'total_commission': sum(sale.commission_amount for sale in total_sales) or 0,
                        'wallet_balance': affiliate_wallet.balance,
                        'total_earned': affiliate_wallet.total_earned,
                        'referral_url': self.request.build_absolute_uri('/') + f'?ref={affiliate.code}',
                        'recent_sales': total_sales.order_by('-created_at')[:5],
                        'min_withdrawal': settings.AFFILIATE_MIN_WITHDRAWAL,
                    }
            except Exception:
                pass
        
        # سفارش‌های پرداخت شده برای نمای کلی
        paid_orders_for_overview = Order.objects.filter(
            user=user, 
            status='paid'
        ).select_related('product', 'plan').order_by('-created_at')[:5]
        
        context.update({
            # آمار
            'total_orders': total_orders,
            'paid_orders': paid_orders,
            'total_licenses': total_licenses,
            'active_licenses': active_licenses,
            'total_spent': total_spent,
            
            # داده‌ها
            'orders': orders[:50],  # محدود به 50 مورد
            'paid_orders_for_overview': paid_orders_for_overview,  # فقط برای نمای کلی
            'licenses': licenses,
            'license_dashboard': license_dashboard,
            'orders_pending_claim': orders_pending_claim,
            'transactions': transactions[:50],
            'products': products,  # محصولات برای خرید لایسنس جدید
            
            # فیلترها
            'order_status_filter': status_filter,
            'order_search': search_query,
            'license_status_filter': license_status_filter,
            
            # افیلیت
            'has_paid_orders': has_paid_orders,
            'affiliate': affiliate,
            'affiliate_wallet': affiliate_wallet,
            'affiliate_stats': affiliate_stats,
        })
        return context


class ProfileView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    form_class = ProfileForm
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('profile')
    
    def get_object(self):
        profile, created = UserProfile.objects.get_or_create(user=self.request.user)
        return profile
    
    def form_valid(self, form):
        messages.success(self.request, 'پروفایل شما با موفقیت به‌روزرسانی شد.')
        return super().form_valid(form)


class UpdateUserInfoView(LoginRequiredMixin, View):
    """ویو AJAX برای به‌روزرسانی اطلاعات کاربری"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            user = request.user
            
            from accounts.phone_utils import normalize_phone, is_valid_iran_mobile

            username = data.get('username', '').strip()
            email = data.get('email', '').strip()
            phone = normalize_phone(data.get('phone', '').strip())
            first_name = data.get('first_name', '').strip()
            last_name = data.get('last_name', '').strip()

            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name

            if username and username != user.username:
                if User.objects.filter(username=username).exclude(pk=user.pk).exists():
                    return JsonResponse({'success': False, 'error': 'نام کاربری قبلاً استفاده شده است.'}, status=400)
                user.username = username

            if email and email != user.email:
                if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                    return JsonResponse({'success': False, 'error': 'ایمیل قبلاً استفاده شده است.'}, status=400)
                user.email = email

            if phone and phone != user.phone:
                if not is_valid_iran_mobile(phone):
                    return JsonResponse({'success': False, 'error': 'شماره موبایل معتبر نیست.'}, status=400)
                if User.objects.filter(phone=phone).exclude(pk=user.pk).exists():
                    return JsonResponse({'success': False, 'error': 'این شماره قبلاً ثبت شده است.'}, status=400)
                user.phone = phone
            
            user.save()
            return JsonResponse({
                'success': True,
                'message': 'اطلاعات کاربری با موفقیت به‌روزرسانی شد.',
                'data': {
                    'username': user.username,
                    'email': user.email,
                    'phone': user.phone or '-'
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class UpdateProfileView(LoginRequiredMixin, View):
    """ویو AJAX برای به‌روزرسانی اطلاعات تکمیلی پروفایل"""
    
    def post(self, request):
        try:
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            
            bio = request.POST.get('bio', '').strip()
            address = request.POST.get('address', '').strip()
            city = request.POST.get('city', '').strip()
            postal_code = request.POST.get('postal_code', '').strip()
            
            if 'avatar' in request.FILES:
                profile.avatar = request.FILES['avatar']
            
            profile.bio = bio
            profile.address = address
            profile.city = city
            profile.postal_code = postal_code
            profile.save()
            
            return JsonResponse({
                'success': True,
                'message': 'اطلاعات تکمیلی با موفقیت به‌روزرسانی شد.',
                'data': {
                    'bio': profile.bio or '-',
                    'address': profile.address or '-',
                    'city': profile.city or '-',
                    'postal_code': profile.postal_code or '-',
                    'avatar_url': profile.avatar.url if profile.avatar else ''
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)


class ClaimLicenseView(LoginRequiredMixin, View):
    """صدور لایسنس پس از ثبت شناسه سخت‌افزار برای سفارش پرداخت‌شده."""

    def post(self, request):
        order_id = request.POST.get('order_id', '').strip()
        hardware_fingerprint = request.POST.get('hardware_fingerprint', '').strip()
        label = request.POST.get('label', '').strip()

        from django.core.exceptions import ValidationError
        from licenses.services.claim import claim_license_for_order
        from licenses.services.management import update_device_slot

        try:
            license_obj = claim_license_for_order(
                request.user,
                order_id,
                hardware_fingerprint,
            )
            if label:
                activation = license_obj.activations.filter(
                    hardware_fingerprint=hardware_fingerprint.strip(),
                ).first()
                if activation:
                    update_device_slot(request.user, activation.pk, label=label)
            messages.success(
                request,
                f'لایسنس برای پلن «{license_obj.plan.name}» صادر شد. کلید را کپی کرده و در ربات وارد کنید.',
            )
        except ValidationError as exc:
            msg = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
            messages.error(request, msg)
        except Exception as exc:
            messages.error(request, f'خطا در صدور لایسنس: {exc}')

        return redirect(f"{reverse_lazy('dashboard')}?tab=licenses#licenses")

