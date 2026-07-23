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
    """ثبت‌نام با شماره و رمز — مسیر جایگزین وقتی پیامک در دسترس نیست."""

    model = User
    form_class = RegisterForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('workspace:home')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url and str(next_url).startswith('/') and not str(next_url).startswith('//'):
            return next_url
        return reverse_lazy('workspace:home')

    def form_valid(self, form):
        response = super().form_valid(form)
        phone = form.cleaned_data.get('phone')
        password = form.cleaned_data.get('password1')
        user = authenticate(username=phone, password=password)
        if user:
            from affiliates.services import assign_referred_user, capture_referral_from_request
            affiliate = capture_referral_from_request(self.request)
            assign_referred_user(user, affiliate)
            login(self.request, user, backend='accounts.backends.PhoneAuthBackend')
            UserProfile.objects.get_or_create(user=user)
            try:
                from accounts.services.lead_attribution import attribute_signup
                attribute_signup(user=user, request=self.request)
            except Exception:
                import logging
                logging.getLogger(__name__).exception('lead acquisition signup attribution failed')
            messages.info(
                self.request,
                'حساب شما ساخته شد. برای امنیت بیشتر، بعداً شماره موبایل را با پیامک تأیید کنید.',
            )
        return response


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.user.is_authenticated and request.method == 'GET':
            try:
                from accounts.services.growth_journey import on_workspace_login
                on_workspace_login(user=request.user)
            except Exception:
                pass
        return response
    
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
        pending_orders_count = Order.objects.filter(
            user=user,
            status__in=('pending', 'pending_verification'),
        ).count()
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
        from django.db.models import Exists, OuterRef
        from licenses.services.claim import issue_license_for_paid_order
        from licenses.services.management import build_license_dashboard

        licenses = License.objects.filter(order__user=user).select_related('order', 'order__product', 'plan').order_by('-created_at')

        # سفارش‌های paid قدیمی بدون لایسنس — صدور خودکار (سازگاری با خریدهای قبلی)
        orders_pending_claim = Order.objects.filter(
            user=user,
            status='paid',
        ).annotate(
            has_license=Exists(License.objects.filter(order_id=OuterRef('pk'))),
        ).filter(has_license=False).select_related('product', 'plan').order_by('-paid_at', '-created_at')
        for pending_order in list(orders_pending_claim):
            issue_license_for_paid_order(pending_order)
        if orders_pending_claim.exists():
            licenses = License.objects.filter(order__user=user).select_related('order', 'order__product', 'plan').order_by('-created_at')
            orders_pending_claim = Order.objects.filter(
                user=user,
                status='paid',
            ).annotate(
                has_license=Exists(License.objects.filter(order_id=OuterRef('pk'))),
            ).filter(has_license=False).select_related('product', 'plan').order_by('-paid_at', '-created_at')

        license_dashboard = build_license_dashboard(user)
        # فیلتر لایسنس‌ها
        license_status_filter = self.request.GET.get('license_status', '')
        if license_status_filter:
            licenses = licenses.filter(status=license_status_filter)
        
        # تراکنش‌ها
        transactions = Transaction.objects.filter(order__user=user).select_related(
            'order', 'order__product', 'order__plan',
        ).order_by('-created_at')
        
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
                    from affiliates.services.referral import build_referral_url, get_referred_users_data
                    referred = get_referred_users_data(affiliate, limit=50)
                    affiliate_wallet, created = Wallet.objects.get_or_create(user=user)
                    
                    total_sales = AffiliateSale.objects.filter(affiliate=affiliate)
                    from django.conf import settings
                    affiliate_stats = {
                        'total_sales_count': total_sales.count(),
                        'total_commission': sum(sale.commission_amount for sale in total_sales) or 0,
                        'wallet_balance': affiliate_wallet.balance,
                        'total_earned': affiliate_wallet.total_earned,
                        'referral_url': build_referral_url(self.request, affiliate),
                        'recent_sales': total_sales.order_by('-created_at')[:5],
                        'min_withdrawal': settings.AFFILIATE_MIN_WITHDRAWAL,
                        'referred_users_count': referred['total'],
                        'referred_users_with_orders': referred['with_orders'],
                        'referred_users_without_orders': referred['without_orders'],
                        'referred_users': referred['items'],
                        'referred_users_has_more': referred['has_more'],
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
            'pending_orders_count': pending_orders_count,
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

        # پروفایل عمومی مشاور (شبکه‌های اجتماعی + برندینگ صفحه اشتراک)
        try:
            from workspace.mixins import get_or_create_settings
            from workspace.services.public_share_common import (
                SOCIAL_NETWORK_DEFS,
                social_networks_for_display,
                welcome_html_to_plain,
            )
            ws = get_or_create_settings(user)
            socials = ws.social_links if isinstance(ws.social_links, dict) else {}
            agency_socials = ws.agency_social_links if isinstance(ws.agency_social_links, dict) else {}

            def _networks_form(src):
                return [
                    {
                        'key': defn['key'],
                        'label': defn['label'],
                        'icon_file': defn.get('icon_file', ''),
                        'color': defn['color'],
                        'placeholder': defn['placeholder'],
                        'url': (src.get(defn['key']) or '').strip(),
                    }
                    for defn in SOCIAL_NETWORK_DEFS
                ]

            welcome_raw = (ws.default_welcome_message or '').strip()
            photo_url = ''
            card_url = ''
            try:
                if ws.consultant_photo:
                    photo_url = ws.consultant_photo.url
            except (ValueError, AttributeError):
                pass
            try:
                if ws.business_card_image:
                    card_url = ws.business_card_image.url
            except (ValueError, AttributeError):
                pass
            context.update({
                'ws_settings': ws,
                'consultant_agency_name': (ws.agency_name or '').strip(),
                'consultant_welcome_default': welcome_raw,
                'consultant_welcome_plain': welcome_html_to_plain(welcome_raw),
                'consultant_social_networks': _networks_form(socials),
                'consultant_socials_active': social_networks_for_display(socials),
                'agency_social_networks': _networks_form(agency_socials),
                'agency_socials_active': social_networks_for_display(agency_socials),
                'consultant_agency_address': (ws.agency_address or '').strip(),
                'consultant_agency_city': (ws.agency_city or '').strip(),
                'consultant_agency_landline': (ws.agency_landline or '').strip(),
                'consultant_agency_landline_alt': (ws.agency_landline_alt or '').strip(),
                'consultant_agency_website': (ws.agency_website or '').strip(),
                'consultant_agency_latitude': ws.agency_latitude if ws.agency_latitude is not None else '',
                'consultant_agency_longitude': ws.agency_longitude if ws.agency_longitude is not None else '',
                'consultant_photo_url': photo_url,
                'consultant_business_card_url': card_url,
            })
        except Exception:
            context.update({
                'ws_settings': None,
                'consultant_agency_name': '',
                'consultant_welcome_default': '',
                'consultant_welcome_plain': '',
                'consultant_social_networks': [],
                'consultant_socials_active': [],
                'agency_social_networks': [],
                'agency_socials_active': [],
                'consultant_agency_address': '',
                'consultant_agency_city': '',
                'consultant_agency_landline': '',
                'consultant_agency_landline_alt': '',
                'consultant_agency_website': '',
                'consultant_agency_latitude': '',
                'consultant_agency_longitude': '',
                'consultant_photo_url': '',
                'consultant_business_card_url': '',
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
                user.phone_verified = False
                user.phone_verified_at = None

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


class UpdateConsultantProfileView(LoginRequiredMixin, View):
    """ذخیره برندینگ مشاور و شبکه‌های اجتماعی برای صفحه عمومی / مودال اشتراک."""

    def post(self, request):
        try:
            from workspace.mixins import get_or_create_settings
            from workspace.services.public_share_common import (
                agency_social_links_from_post,
                apply_agency_profile_fields,
                save_share_profile_defaults,
                sanitize_welcome_html,
                social_links_from_post,
                social_networks_for_display,
                welcome_html_to_plain,
            )

            agency_name = (request.POST.get('agency_name') or '').strip()[:200]
            welcome_raw = request.POST.get('default_welcome_message') or ''
            welcome_clean = sanitize_welcome_html(welcome_raw)[:8000]
            socials = social_links_from_post(request.POST)
            agency_socials = agency_social_links_from_post(request.POST)

            ws = get_or_create_settings(request.user)
            ws.agency_name = agency_name
            profile_changed = apply_agency_profile_fields(ws, request.POST, request.FILES)
            update_fields = ['agency_name', 'updated_at', *profile_changed]
            # حذف تکراری‌ها با حفظ ترتیب
            seen = set()
            unique_fields = []
            for f in update_fields:
                if f not in seen:
                    seen.add(f)
                    unique_fields.append(f)
            ws.save(update_fields=unique_fields)

            save_share_profile_defaults(
                request.user,
                default_welcome_message=welcome_clean,
                social_links=socials,
                agency_social_links=agency_socials,
                save_welcome=True,
                save_socials=True,
                save_agency_socials=True,
            )
            ws.refresh_from_db()
            active = social_networks_for_display(ws.social_links or {})
            agency_active = social_networks_for_display(ws.agency_social_links or {})
            return JsonResponse({
                'success': True,
                'message': 'پروفایل عمومی مشاور ذخیره شد. در مودال اشتراک و لینک عمومی نمایش داده می‌شود.',
                'data': {
                    'agency_name': ws.agency_name or '',
                    'welcome_plain': welcome_html_to_plain(ws.default_welcome_message or ''),
                    'social_count': len(active),
                    'agency_social_count': len(agency_active),
                    'socials': [
                        {'key': s['key'], 'label': s['label'], 'url': s['url']}
                        for s in active
                    ],
                },
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
                'کلید لایسنس شما آماده است. آن را از همین صفحه کپی کرده و در ربات وارد کنید.',
            )
        except ValidationError as exc:
            msg = exc.messages[0] if getattr(exc, 'messages', None) else str(exc)
            messages.error(request, msg)
        except Exception as exc:
            messages.error(request, f'خطا در صدور لایسنس: {exc}')

        return redirect(f"{reverse_lazy('dashboard')}?tab=licenses#licenses")

