"""
ویوهای فروشگاه
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, TemplateView, CreateView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.conf import settings
from django.db import models
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.views import View
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.utils.decorators import method_decorator
from pathlib import Path
from .bot_catalog import (
    BOT_PRODUCT_SLUG, bot_page_content, get_bot_product, get_bot_product_buy_url,
    get_bot_product_url, home_display_stats, home_page_content, license_guide_content,
    product_fake_reviews, product_rating_display_stats,
)
from .bot_install_video import get_bot_install_video_context, resolve_guide_video
from workspace.services.filing_video import get_filing_video_context
from workspace.services.crm_video import get_crm_video_context
from .sample_excel import get_sale_apartment_excel_preview
from .education_content import education_hub_content
from .education_academy import get_education_academy_hero
from .android_tutorial_content import android_tutorial_content, android_tutorial_schema_json
from .android_tutorial_video import get_android_video_context, resolve_android_video
from .seo_landings import get_landing, landing_schema_json
from .services.app_downloads import build_android_apk_response
from .author_content import author_page_content, AUTHOR_SLUG
from workspace.services.jalali_input import format_jalali_datetime
from .models import Product, LicensePlan, Order, ProductRating, ProductReview, ReviewHelpful, DiscountCode
from .forms import ContactForm, BuyForm, RatingForm, ReviewForm
import requests
import json


class HomeView(TemplateView):
    template_name = 'shop/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bot_product'] = get_bot_product()
        context['home_page'] = home_page_content()
        context['stats'] = home_display_stats()
        
        # SEO Meta Tags
        context['meta_title'] = 'فایلینگ دیوار — سیستم‌عامل مشاور حرفه‌ای املاک'
        context['meta_description'] = (
            'سیستم‌عامل مشاوران حرفه‌ای املاک: دیدن فرصت‌ها زودتر از رقبا، '
            'فایلینگ هوشمند، CRM، تطبیق فایل و مشتری و تحلیل بازار.'
        )
        context['meta_keywords'] = (
            'فایلینگ دیوار, سیستم عامل مشاور املاک, CRM املاک, ربات دیوار, '
            'استخراج آگهی, تحلیل بازار املاک, میزکار مشاور'
        )
        import json
        from shop.templatetags.seo_tags import get_site_url, get_site_name
        site_url = get_site_url()
        context['schema_data'] = json.dumps({
            '@context': 'https://schema.org',
            '@type': 'SoftwareApplication',
            'name': get_site_name(),
            'applicationCategory': 'BusinessApplication',
            'operatingSystem': 'Windows, Web',
            'description': context['meta_description'],
            'url': site_url,
            'inLanguage': 'fa-IR',
            'offers': {
                '@type': 'Offer',
                'priceCurrency': 'IRR',
                'availability': 'https://schema.org/InStock',
            },
        }, ensure_ascii=False)
        return context


class ProductListView(TemplateView):
    """تنها محصول — ربات استخراج؛ هدایت مستقیم به صفحه محصول."""

    def get(self, request, *args, **kwargs):
        return redirect(get_bot_product_url())


class ProductDetailView(DetailView):
    model = Product
    template_name = 'shop/product_bot.html'
    context_object_name = 'product'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Product.objects.filter(is_active=True)

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if request.method == 'GET' and getattr(self, 'object', None):
            from shop.services.plan_funnel import record_plan_funnel_event
            record_plan_funnel_event(request, 'pricing_view', product=self.object)
        return response

    def get_template_names(self):
        if self.object and self.object.slug == BOT_PRODUCT_SLUG:
            return ['shop/product_bot.html']
        return ['shop/product_detail.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        context['plans'] = product.plans.filter(is_active=True).order_by('order', 'price')
        context['daily_plan_used'] = False
        context['buyable_plans'] = list(context['plans'])
        context['bot_page'] = bot_page_content()
        if product.slug == BOT_PRODUCT_SLUG:
            context['excel_sample'] = get_sale_apartment_excel_preview()
            context['install_video'] = get_bot_install_video_context()

        # بررسی وجود ویدیو در media
        context['has_video_media'] = product.media.filter(media_type='video').exists()
        
        # تعیین اولین media برای نمایش
        first_media = product.media.first()
        context['first_media_type'] = first_media.media_type if first_media else None
        
        # اولین ویدیو و اولین تصویر
        first_video = product.media.filter(media_type='video').first()
        first_image = product.media.filter(media_type='image').first()
        context['first_video'] = first_video
        context['first_image'] = first_image
        
        # آمار و نظرات نمایشی (نظرات واقعی کاربران عمومی نمایش داده نمی‌شود)
        rating_display = product_rating_display_stats()
        context['average_rating'] = rating_display['average_rating']
        context['rating_count'] = rating_display['rating_count']
        context['rating_distribution'] = rating_display['rating_distribution']
        context['rating_percentages'] = rating_display['rating_percentages']
        context['display_reviews'] = product_fake_reviews()
        context['reviews_count'] = rating_display['reviews_count']

        # بررسی اینکه آیا کاربر قبلاً امتیاز داده یا نظر داده
        if self.request.user.is_authenticated:
            from shop.services.plan_guards import user_has_purchased_daily_plan

            context['daily_plan_used'] = user_has_purchased_daily_plan(self.request.user)
            context['buyable_plans'] = [
                plan for plan in context['plans']
                if not (context['daily_plan_used'] and plan.plan_type == 'daily')
            ]

            user_rating = ProductRating.objects.filter(
                product=product,
                user=self.request.user
            ).first()
            context['user_rating'] = user_rating
            
            user_review = ProductReview.objects.filter(
                product=product,
                user=self.request.user
            ).first()
            context['user_review'] = user_review
        
        # فرم‌ها
        context['rating_form'] = RatingForm(product=product, user=self.request.user if self.request.user.is_authenticated else None)
        context['review_form'] = ReviewForm(product=product, user=self.request.user if self.request.user.is_authenticated else None)
        
        # SEO Meta Tags
        context['meta_title'] = f'{product.title} - فروشگاه ربات دیوار'
        context['meta_description'] = (
            product.short_description
            or 'ربات استخراج دیوار و اپ اندروید — یک لایسنس، ویندوز + موبایل، فایلینگ و CRM'
        )
        context['meta_keywords'] = f'{product.title}, ربات دیوار, اپ اندروید, فایلینگ دیوار'
        
        # تصویر برای Open Graph
        if product.media.exists():
            media = product.media.first()
            if media and media.media_type == 'image':
                context['meta_image'] = media.file.url
        
        # Breadcrumbs
        context['breadcrumb_items'] = [
            {'name': 'خانه', 'url': '/'},
            {'name': 'ربات استخراج', 'active': True},
        ]
        
        # Schema.org برای Product با اطلاعات امتیاز
        from django.conf import settings
        from django.urls import reverse
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        
        schema_data = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product.title,
            "description": product.short_description or str(product.description)[:200] if product.description else '',
            "url": f"{site_url}{product.get_absolute_url()}",
        }
        
        if product.media.exists():
            media = product.media.first()
            if media and media.media_type == 'image':
                schema_data["image"] = f"{site_url}{media.file.url}"
        
        if product.plans.exists():
            plan = product.plans.first()
            schema_data["offers"] = {
                "@type": "Offer",
                "price": float(plan.price),
                "priceCurrency": "IRR",
                "availability": "https://schema.org/InStock",
            }
        
        # افزودن اطلاعات امتیاز به Schema.org
        if context['rating_count'] > 0:
            schema_data["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": context['average_rating'],
                "reviewCount": context['reviews_count'],
                "bestRating": "5",
                "worstRating": "1"
            }
        
        import json
        context['schema_data'] = json.dumps(schema_data, ensure_ascii=False)
        
        return context


class RenewLicenseView(LoginRequiredMixin, View):
    """ورود به جریان تمدید — همان کلید لایسنس با تاریخ انقضای جدید."""

    def get(self, request, license_id):
        from licenses.services.renewal import get_renewable_license_for_user
        from urllib.parse import urlencode

        license_obj = get_renewable_license_for_user(request.user, license_id)
        product = license_obj.order.product
        params = urlencode({
            'renew': license_obj.pk,
            'plan': license_obj.plan_id,
        })
        return redirect(f"{reverse('buy', kwargs={'slug': product.slug})}?{params}")


class BuyView(LoginRequiredMixin, CreateView):
    model = Order
    form_class = BuyForm
    template_name = 'shop/buy.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.product = get_object_or_404(Product, slug=kwargs['slug'], is_active=True)
        self.renewal_license = None
        if request.user.is_authenticated:
            self.renewal_license = self._load_renewal_license()
            plan = self._get_selected_plan()
            blocked = self._redirect_for_plan_requirements(plan)
            if blocked:
                return blocked
        return super().dispatch(request, *args, **kwargs)

    def _load_renewal_license(self):
        from licenses.services.renewal import get_renewable_license_for_user

        renew_id = self.request.GET.get('renew') or self.request.POST.get('renew')
        if not renew_id:
            return None
        try:
            license_id = int(renew_id)
        except (ValueError, TypeError):
            return None
        try:
            license_obj = get_renewable_license_for_user(self.request.user, license_id)
        except Http404:
            messages.error(self.request, 'لایسنس انتخاب‌شده برای تمدید یافت نشد یا قابل تمدید نیست.')
            return None
        if license_obj.order.product_id != self.product.id:
            raise Http404
        return license_obj
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['product'] = self.product
        kwargs['user'] = self.request.user
        requested_plan = self._get_requested_plan()
        if requested_plan and not kwargs.get('data'):
            kwargs.setdefault('initial', {})['plan'] = requested_plan.pk
        if self.renewal_license and not kwargs.get('data'):
            kwargs.setdefault('initial', {})['plan'] = self.renewal_license.plan_id
        return kwargs

    def _get_requested_plan(self):
        plan_id = self.request.GET.get('plan')
        if not plan_id:
            return None
        try:
            return self.product.plans.get(pk=int(plan_id), is_active=True)
        except (LicensePlan.DoesNotExist, ValueError, TypeError):
            return None

    def _get_selected_plan(self):
        plan_id = self.request.POST.get('plan') if self.request.method == 'POST' else self.request.GET.get('plan')
        if not plan_id:
            return None
        try:
            return self.product.plans.get(pk=int(plan_id), is_active=True)
        except (LicensePlan.DoesNotExist, ValueError, TypeError):
            return None

    def _redirect_for_plan_requirements(self, plan):
        from shop.services.plan_guards import (
            BLOCK_PHONE_VERIFY,
            evaluate_plan_purchase,
            verify_phone_redirect_url,
        )

        ok, message, reason = evaluate_plan_purchase(self.request.user, plan)
        if ok:
            return None
        messages.warning(self.request, message)
        if reason == BLOCK_PHONE_VERIFY:
            return redirect(verify_phone_redirect_url(self.request.get_full_path()))
        return redirect(reverse('buy', kwargs={'slug': self.product.slug}))

    def get(self, request, *args, **kwargs):
        from shop.services.plan_funnel import record_plan_funnel_event
        plan = self._get_requested_plan() or self._get_selected_plan()
        record_plan_funnel_event(request, 'checkout_view', product=self.product, plan=plan)
        if request.user.is_authenticated:
            try:
                from accounts.services.growth_journey import on_checkout_start
                from accounts.models import MarketingLead, LeadTouchpoint
                from accounts.phone_utils import normalize_phone
                from accounts.services.lead_attribution import record_touchpoint
                on_checkout_start(user=request.user)
                phone = normalize_phone(getattr(request.user, 'phone', '') or '')
                lead = MarketingLead.objects.filter(phone_normalized=phone).first() if phone else None
                if lead:
                    record_touchpoint(
                        lead=lead,
                        event_type=LeadTouchpoint.EventType.CHECKOUT_START,
                        user=request.user,
                    )
            except Exception:
                pass
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from shop.services.plan_guards import (
            evaluate_plan_purchase,
            user_has_purchased_daily_plan,
        )

        daily_plan_used = user_has_purchased_daily_plan(self.request.user)

        from shop.services.plan_pricing import calculate_plan_purchase_prices

        plans_with_prices = []
        for plan in self.product.plans.filter(is_active=True).order_by('order', 'price'):
            purchase_ok, purchase_message, _purchase_reason = evaluate_plan_purchase(
                self.request.user,
                plan,
            )
            pricing = calculate_plan_purchase_prices(
                plan,
                self.product,
                self.request.user,
                request=self.request,
                quantity=1,
            )
            plans_with_prices.append({
                'plan': plan,
                'original_price': int(pricing['original_price']),
                'unit_list_price': int(pricing['unit_list_price']),
                'unit_sale_price': int(pricing['unit_sale_price']),
                'discount_amount': int(pricing['discount_amount']),
                'final_price': int(pricing['final_price']),
                'has_discount': pricing['has_discount'],
                'has_promo_offer': pricing['has_promo_offer'],
                'has_repeat_discount': pricing['has_repeat_discount'],
                'repeat_discount_percentage': pricing['repeat_discount_percentage'],
                'discount_reasons': pricing['discount_reasons'],
                'purchase_blocked': not purchase_ok,
                'purchase_block_message': purchase_message,
                'features': plan.normalized_features(),
                'tagline': plan.tagline.strip(),
            })

        has_previous_purchase = any(p['has_repeat_discount'] for p in plans_with_prices)
        
        from shop.models import PaymentSettings
        pay_settings = PaymentSettings.load()
        payment_methods = pay_settings.available_methods()

        requested_plan = self._get_requested_plan()
        selected_plan_id = None
        if self.request.method == 'POST':
            posted_plan = self.request.POST.get('plan')
            if posted_plan:
                try:
                    plan_pk = int(posted_plan)
                    if self.product.plans.filter(pk=plan_pk, is_active=True).exists():
                        selected_plan_id = plan_pk
                except (ValueError, TypeError):
                    pass
        if selected_plan_id is None:
            if requested_plan:
                requested_ok, _, _ = evaluate_plan_purchase(self.request.user, requested_plan)
                if requested_ok:
                    selected_plan_id = requested_plan.pk
            if selected_plan_id is None and self.renewal_license:
                selected_plan_id = self.renewal_license.plan_id
            if selected_plan_id is None:
                for plan_data in plans_with_prices:
                    if not plan_data['purchase_blocked']:
                        selected_plan_id = plan_data['plan'].pk
                        break

        selected_plan = None
        if selected_plan_id:
            selected_plan = self.product.plans.filter(pk=selected_plan_id, is_active=True).first()

        renewal_preview = None
        if self.renewal_license:
            from licenses.services.renewal import compute_renewed_expires_at

            preview_plan = selected_plan or self.renewal_license.plan
            new_expires = compute_renewed_expires_at(self.renewal_license, preview_plan)
            renewal_preview = {
                'license_key': self.renewal_license.license_key,
                'current_expires_at': self.renewal_license.expires_at,
                'new_expires_at': new_expires,
                'is_expired': self.renewal_license.status == 'expired',
            }

        context.update({
            'product': self.product,
            'plans_with_prices': plans_with_prices,
            'selected_plan_id': selected_plan_id,
            'has_previous_purchase': has_previous_purchase,
            'daily_plan_used': daily_plan_used,
            'pay_settings': pay_settings,
            'payment_methods': payment_methods,
            'show_payment_choice': len(payment_methods) > 1,
            'renewal_license': self.renewal_license,
            'is_renewal': bool(self.renewal_license),
            'renewal_preview': renewal_preview,
        })

        from shop.services.plan_guards import requires_phone_verification_for_plan, verify_phone_redirect_url

        context['phone_verification_required'] = (
            self.request.user.is_authenticated
            and requires_phone_verification_for_plan(selected_plan)
            and not self.request.user.phone_verified
        )
        if context['phone_verification_required']:
            context['verify_phone_url'] = verify_phone_redirect_url(self.request.get_full_path())
        
        return context
    
    def form_valid(self, form):
        renew_param = self.request.POST.get('renew')
        if renew_param and not self.renewal_license:
            messages.error(self.request, 'درخواست تمدید نامعتبر است.')
            return redirect(f"{reverse('dashboard_tab', kwargs={'tab': 'licenses'})}#licenses")

        blocked = self._redirect_for_plan_requirements(form.cleaned_data.get('plan'))
        if blocked:
            return blocked

        order = form.save(commit=False)
        order.user = self.request.user
        order.product = self.product
        order.quantity = 1 if self.renewal_license else (form.cleaned_data.get('quantity') or 1)
        if self.renewal_license:
            order.renewal_license = self.renewal_license

        from shop.services.plan_pricing import calculate_plan_purchase_prices

        discount_code = form.cleaned_data.get('discount_code')
        pricing = calculate_plan_purchase_prices(
            order.plan,
            self.product,
            self.request.user,
            request=self.request,
            quantity=order.quantity,
            discount_code=discount_code,
        )
        order.original_price = pricing['original_price']
        order.discount_amount = pricing['discount_amount']
        order.amount = pricing['final_price']

        from affiliates.services import resolve_order_affiliate
        affiliate = resolve_order_affiliate(self.request.user, self.request)
        if affiliate:
            order.affiliate = affiliate

        if discount_code:
            is_valid, message = discount_code.is_valid(self.request.user)
            if not is_valid:
                form.add_error('discount_code', message)
                return self.form_invalid(form)
            order.discount_code = discount_code
            base_pricing = calculate_plan_purchase_prices(
                order.plan,
                self.product,
                self.request.user,
                request=self.request,
                quantity=order.quantity,
            )
            if pricing['final_price'] >= base_pricing['final_price']:
                form.add_error('discount_code', 'کد تخفیف قابل اعمال نیست.')
                return self.form_invalid(form)

        from shop.models import PaymentSettings
        pay_settings = PaymentSettings.load()
        available = pay_settings.available_methods()
        if not available:
            form.add_error(None, 'در حال حاضر هیچ روش پرداختی فعال نیست. با پشتیبانی تماس بگیرید.')
            return self.form_invalid(form)

        requested_method = self.request.POST.get('payment_method', '').strip()
        if requested_method in available:
            order.payment_method = requested_method
        else:
            order.payment_method = available[0]
        
        order.save()
        
        # افزایش تعداد استفاده کد تخفیف
        if discount_code:
            discount_code.used_count += 1
            discount_code.save(update_fields=['used_count'])

        if order.amount <= 0:
            from shop.services.order_fulfillment import fulfill_order_after_payment
            fulfill_order_after_payment(order)
            return redirect('payment:success', order_id=order.id)

        if order.payment_method == 'card_transfer':
            return redirect('payment:card_transfer', order_id=order.id)
        return redirect('payment:checkout', order_id=order.id)


class AboutView(TemplateView):
    template_name = 'shop/about.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # SEO Meta Tags
        context['meta_title'] = 'درباره ما - فروشگاه ربات دیوار'
        context['meta_description'] = 'درباره فروشگاه ربات دیوار. ما با سال‌ها تجربه در زمینه توسعه نرم‌افزار و تحلیل داده، محصولاتی با کیفیت ارائه می‌دهیم.'
        context['meta_keywords'] = 'درباره ما, ربات دیوار, تیم ما'
        return context


class ContactView(FormView):
    form_class = ContactForm
    template_name = 'shop/contact.html'
    success_url = reverse_lazy('contact')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # SEO Meta Tags
        context['meta_title'] = 'تماس با ما - فروشگاه ربات دیوار'
        context['meta_description'] = 'تماس با فروشگاه ربات دیوار. برای سوالات، پیشنهادات و پشتیبانی با ما در ارتباط باشید.'
        context['meta_keywords'] = 'تماس با ما, پشتیبانی, ارتباط با ربات دیوار'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'پیام شما با موفقیت ارسال شد. در اسرع وقت با شما تماس خواهیم گرفت.')
        # در اینجا می‌توانید ایمیل ارسال کنید
        return super().form_valid(form)


class TermsView(TemplateView):
    template_name = 'shop/terms.html'


class PrivacyView(TemplateView):
    template_name = 'shop/privacy.html'


class AndroidAppDownloadView(View):
    """دانلود عمومی APK اندروید از django/files/."""

    def get(self, request):
        return build_android_apk_response()


class LicenseGuideView(TemplateView):
    template_name = 'shop/license_guide.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['guide'] = license_guide_content()
        ctx['bot_product'] = get_bot_product()
        ctx['bot_buy_url'] = get_bot_product_buy_url()

        video = ctx['guide'].get('video', {})
        ctx['video_mode'], ctx['video_src'] = resolve_guide_video(video)
        ctx['install_video'] = get_bot_install_video_context()

        user = self.request.user
        if user.is_authenticated:
            from licenses.models import License

            ctx['user_licenses'] = License.objects.filter(
                order__user=user,
            ).select_related('order', 'plan').order_by('-created_at')[:5]
            from workspace.services.access import get_bot_access_state
            access = get_bot_access_state(user)
            ctx['has_active_license'] = access['has_bot_license']
            ctx['has_pending_bot_activation'] = access['has_pending_bot_activation']
        else:
            ctx['user_licenses'] = []
            ctx['has_active_license'] = False
        return ctx


class SeoLandingView(TemplateView):
    """لندینگ سئو — محتوا از seo_landings.py"""
    template_name = 'shop/seo_landing.html'
    MARKET_TEMPLATE = 'shop/seo_landing_market.html'
    MARKET_SLUG = 'real-estate-market-analysis'

    def get_template_names(self):
        slug = self.kwargs.get('landing_slug', '')
        if slug == self.MARKET_SLUG:
            return [self.MARKET_TEMPLATE]
        return [self.template_name]

    def dispatch(self, request, *args, **kwargs):
        slug = kwargs.get('landing_slug', '')
        if not get_landing(slug):
            from django.http import Http404
            raise Http404('صفحه یافت نشد')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        slug = kwargs['landing_slug']
        landing = get_landing(slug)
        ctx['landing'] = landing
        ctx['bot_product'] = get_bot_product()
        ctx['meta_title'] = landing['meta_title']
        ctx['meta_description'] = landing['meta_description']
        ctx['meta_keywords'] = landing['meta_keywords']
        ctx['schema_data'] = landing_schema_json(landing)
        return ctx


class AuthorPageView(TemplateView):
    template_name = 'shop/author.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        author = author_page_content()
        ctx['author'] = author
        ctx['meta_title'] = author['meta_title']
        ctx['meta_description'] = author['meta_description']
        ctx['meta_keywords'] = author['meta_keywords']
        from blog.models import Post
        from django.contrib.auth import get_user_model
        User = get_user_model()
        author_user = User.objects.filter(
            models.Q(username__icontains='hossein') | models.Q(first_name__icontains='حسین')
        ).first()
        if author_user:
            posts_qs = (
                Post.objects.filter(is_published=True, author=author_user)
                .select_related('category')
                .order_by('-published_at')
            )
            ctx['author_posts'] = posts_qs[:12]
            ctx['author_post_count'] = posts_qs.count()
        else:
            posts_qs = Post.objects.filter(is_published=True).select_related('category').order_by('-published_at')
            ctx['author_posts'] = posts_qs[:6]
            ctx['author_post_count'] = posts_qs.count()
        return ctx


class EducationView(TemplateView):
    template_name = 'shop/education.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['edu'] = education_hub_content()
        ctx['bot_product'] = get_bot_product()
        ctx['bot_buy_url'] = get_bot_product_buy_url()
        ctx['install_video'] = get_bot_install_video_context()
        ctx['filing_video'] = get_filing_video_context()
        ctx['crm_video'] = get_crm_video_context()
        ctx['academy_hero'] = get_education_academy_hero()
        user = self.request.user
        if user.is_authenticated:
            from workspace.services.access import get_bot_access_state
            access = get_bot_access_state(user)
            ctx['has_bot_license'] = access['has_bot_license']
        else:
            ctx['has_bot_license'] = False
        ctx['meta_title'] = 'آموزش — مرکز یادگیری فایلینگ دیوار'
        ctx['meta_description'] = (
            'آکادمی ویدیویی رایگان، مسیرهای یادگیری CRM، ربات استخراج دیوار، فایلینگ و تحلیل بازار. '
            'راهنماهای گام‌به‌گام برای مشاوران املاک.'
        )
        ctx['meta_keywords'] = (
            'آموزش فایلینگ دیوار, آکادمی ویدیویی, راهنمای CRM املاک, آموزش ربات دیوار, '
            'تحلیل بازار املاک, میزکار مشاور'
        )
        from shop.academy_playlist_seo import education_hub_schema_json
        edu = ctx.get('edu') or {}
        faq_pairs = edu.get('faq') if isinstance(edu.get('faq'), list) else None
        ctx['schema_data'] = education_hub_schema_json(self.request, faq_pairs=faq_pairs)
        return ctx


class PublicAcademyView(TemplateView):
    """صفحه عمومی آکادمی — معرفی و لینک به پلی‌لیست."""
    template_name = 'shop/academy.html'

    def get_context_data(self, **kwargs):
        from shop.academy_playlist_seo import (
            ACADEMY_PUBLIC_FAQ,
            academy_landing_meta,
            academy_landing_schema_json,
        )
        from shop.education_academy import get_education_academy_hero
        from workspace.academy.services.public_playlist_service import (
            flatten_public_videos,
            get_public_playlist_sections,
            playlist_stats,
            video_item_seo,
        )
        from shop.templatetags.seo_tags import get_site_url

        ctx = super().get_context_data(**kwargs)
        sections = get_public_playlist_sections()
        flat = flatten_public_videos(sections)
        stats = playlist_stats(sections)
        meta = academy_landing_meta(stats=stats)
        hero = get_education_academy_hero()
        site_url = get_site_url()

        ctx['playlist_sections'] = sections
        ctx['playlist_stats'] = stats
        ctx['playlist_flat'] = flat
        ctx['academy_faq'] = ACADEMY_PUBLIC_FAQ
        ctx.update(meta)
        ctx['schema_data'] = academy_landing_schema_json(
            self.request, sections=sections, flat_items=flat,
        )

        hero_poster = ''
        hero_video = hero.get('video')
        if hero_video:
            for item in flat:
                if item['video'].id == hero_video.id or item['video'].slug == hero_video.slug:
                    hero_poster = video_item_seo(item, site_url=site_url).get('poster_url') or ''
                    break
            if not hero_poster:
                player = hero.get('player') or {}
                poster = player.get('poster') or ''
                if poster.startswith(('http://', 'https://')):
                    hero_poster = poster
                elif poster:
                    if player.get('poster_kind') == 'static':
                        hero_poster = f'{site_url}/static/{poster.lstrip("/")}'
                    elif poster.startswith('/'):
                        hero_poster = f'{site_url}{poster}'
                    else:
                        hero_poster = f'{site_url}/{poster}'
        elif flat:
            hero_poster = video_item_seo(flat[0], site_url=site_url).get('poster_url') or ''

        ctx['hero_poster'] = hero_poster
        if hero_poster:
            ctx['meta_image'] = hero_poster
        return ctx


@method_decorator(ensure_csrf_cookie, name='dispatch')
class PublicAcademyPlaylistView(TemplateView):
    """پلی‌لیست عمومی ویدیوهای آکادمی — UI شبیه یوتوب/آپارات."""
    template_name = 'shop/academy_playlist.html'

    def dispatch(self, request, *args, **kwargs):
        from workspace.academy.services.public_playlist_service import (
            get_public_playlist_sections,
            resolve_public_video,
        )
        sections = get_public_playlist_sections()
        if not sections:
            from django.http import Http404
            raise Http404('ویدیوی عمومی یافت نشد.')
        slug = kwargs.get('slug')
        active, flat = resolve_public_video(sections, slug)
        if slug and not active:
            from django.http import Http404
            raise Http404('ویدیو یافت نشد.')
        # Hub (/academy/videos/) keeps active=None for index SEO (200, not redirect)
        if slug:
            self._playlist_active = active
        else:
            self._playlist_active = None
        self._playlist_sections = sections
        self._playlist_flat = flat
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from shop.academy_playlist_seo import ACADEMY_PUBLIC_FAQ, academy_playlist_meta, academy_playlist_schema_json
        from shop.templatetags.seo_tags import get_site_url
        from workspace.academy.services.public_playlist_service import playlist_stats, video_item_seo

        ctx = super().get_context_data(**kwargs)
        sections = self._playlist_sections
        active = self._playlist_active
        flat = self._playlist_flat
        stats = playlist_stats(sections)
        meta = academy_playlist_meta(active_item=active, sections=sections, stats=stats)

        ctx.update(meta)
        ctx['playlist_sections'] = sections
        ctx['playlist_flat'] = flat
        ctx['active_item'] = active
        ctx['playlist_stats'] = stats
        ctx['academy_faq'] = ACADEMY_PUBLIC_FAQ
        ctx['schema_data'] = academy_playlist_schema_json(
            self.request, active_item=active, sections=sections, flat_items=flat,
        )
        ctx['first_video_item'] = flat[0] if flat else None
        if active:
            seo = video_item_seo(active, site_url=get_site_url())
            player = active['player']
            if seo['poster_url']:
                ctx['meta_image'] = seo['poster_url']
            ctx['active_player'] = player
            ctx['active_video'] = active['video']
            prev_item = next_item = None
            for i, item in enumerate(flat):
                if item['video'].id == active['video'].id:
                    if i > 0:
                        prev_item = flat[i - 1]
                    if i < len(flat) - 1:
                        next_item = flat[i + 1]
                    break
            ctx['prev_item'] = prev_item
            ctx['next_item'] = next_item
        elif flat:
            poster = video_item_seo(flat[0], site_url=get_site_url()).get('poster_url')
            if poster:
                ctx['meta_image'] = poster
        return ctx


class PublicAcademyVideoViewAPIView(View):
    """ثبت بازدید پخش ویدیو در پلی‌لیست عمومی."""

    def post(self, request, slug: str):
        from workspace.academy.models import AcademyVideo
        from workspace.academy.services.progress_service import track_event
        from workspace.academy.services.view_tracking import record_video_view

        video = get_object_or_404(
            AcademyVideo,
            slug=slug,
            is_active=True,
            is_public=True,
            path__is_active=True,
        )
        views = record_video_view(video)
        user = request.user if request.user.is_authenticated else None
        track_event(
            user,
            'academy_video_started',
            video=video,
            metadata={'source': 'public_playlist', 'video_slug': slug},
        )
        return JsonResponse({'ok': True, 'views_count': views})


class AndroidTutorialView(TemplateView):
    template_name = 'shop/android_tutorial.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tutorial = android_tutorial_content()
        ctx['tutorial'] = tutorial
        ctx['bot_buy_url'] = get_bot_product_buy_url()

        ctx['video_mode'], ctx['video_src'] = resolve_android_video({'url': ''})
        ctx['overview_video'] = get_android_video_context('overview')

        user = self.request.user
        if user.is_authenticated:
            from workspace.services.access import get_bot_access_state
            access = get_bot_access_state(user)
            ctx['has_bot_license'] = access['has_bot_license']
        else:
            ctx['has_bot_license'] = False

        ctx['meta_title'] = 'آموزش اپ اندروید — راهنمای کامل فایلینگ دیوار'
        ctx['meta_description'] = (
            'آموزش حرفه‌ای نصب، ورود، استخراج آگهی دیوار، فایلینگ، CRM و اعلان‌ها '
            'در اپ موبایل فایلینگ دیوار. ویدیو و تصویر گام‌به‌گام برای مشاوران املاک.'
        )
        ctx['meta_keywords'] = (
            'آموزش اپ اندروید فایلینگ دیوار, نصب APK دیوار فایلینگ, '
            'اپ مشاور املاک اندروید, CRM موبایل املاک, استخراج دیوار موبایل, '
            'Play Protect نصب APK, آموزش فایلینگ موبایل'
        )
        ctx['meta_image'] = '/static/images/android/posters/android-video-overview.jpg'
        ctx['schema_data'] = android_tutorial_schema_json(self.request)
        return ctx


def verification_file(request):
    """Serve verification file"""
    file_path = Path(settings.BASE_DIR) / '66998772.txt'
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content, content_type='text/plain; charset=utf-8')
    except FileNotFoundError:
        return HttpResponse('File not found', status=404)


@login_required
@require_POST
def submit_rating(request, slug):
    """ثبت یا به‌روزرسانی امتیاز محصول"""
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    form = RatingForm(request.POST, product=product, user=request.user)
    if form.is_valid():
        rating = form.save()
        average_rating = ProductRating.get_average_rating(product)
        rating_count = ProductRating.get_rating_count(product)
        
        return JsonResponse({
            'success': True,
            'message': 'امتیاز شما با موفقیت ثبت شد.',
            'average_rating': average_rating,
            'rating_count': rating_count,
            'user_rating': rating.rating
        })
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


@login_required
@require_POST
def submit_review(request, slug):
    """ثبت نظر محصول"""
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    # بررسی اینکه آیا کاربر قبلاً نظر داده
    existing_review = ProductReview.objects.filter(
        product=product,
        user=request.user
    ).first()
    
    # دریافت امتیاز مرتبط (اگر وجود دارد)
    rating = None
    if request.user.is_authenticated:
        rating = ProductRating.objects.filter(
            product=product,
            user=request.user
        ).first()
    
    form = ReviewForm(request.POST, product=product, user=request.user, rating=rating)
    if form.is_valid():
        if existing_review:
            # به‌روزرسانی نظر موجود
            existing_review.title = form.cleaned_data['title']
            existing_review.content = form.cleaned_data['content']
            existing_review.rating = rating
            existing_review.save()
            review = existing_review
            message = 'ممنون! نظر شما ثبت شد.'
        else:
            review = form.save()
            message = 'ممنون از وقتی که گذاشتید. نظر شما ثبت شد.'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'review': {
                'id': review.id,
                'title': review.title,
                'content': review.content,
                'user': review.user.username,
                'created_at': format_jalali_datetime(review.created_at),
                'is_approved': review.is_approved,
                'is_verified_purchase': review.is_verified_purchase
            }
        })
    else:
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


@login_required
@require_POST
def mark_review_helpful(request, review_id):
    """علامت‌گذاری نظر به عنوان مفید"""
    review = get_object_or_404(ProductReview, id=review_id, is_approved=True)
    
    # بررسی اینکه آیا کاربر قبلاً این نظر را مفید علامت زده
    helpful, created = ReviewHelpful.objects.get_or_create(
        review=review,
        user=request.user
    )
    
    if created:
        # افزایش تعداد مفید
        review.helpful_count += 1
        review.save(update_fields=['helpful_count'])
        return JsonResponse({
            'success': True,
            'message': 'نظر به عنوان مفید ثبت شد.',
            'helpful_count': review.helpful_count,
            'is_helpful': True
        })
    else:
        # حذف علامت مفید
        helpful.delete()
        review.helpful_count = max(0, review.helpful_count - 1)
        review.save(update_fields=['helpful_count'])
        return JsonResponse({
            'success': True,
            'message': 'علامت مفید حذف شد.',
            'helpful_count': review.helpful_count,
            'is_helpful': False
        })


@login_required
@require_POST
def apply_discount_code(request, slug):
    """اعمال کد تخفیف و محاسبه قیمت نهایی"""
    import json

    from shop.services.plan_pricing import calculate_plan_purchase_prices

    try:
        data = json.loads(request.body)
        discount_code_str = data.get('discount_code', '').strip().upper()
        plan_id = data.get('plan_id')
        quantity = int(data.get('quantity') or 1)

        if not plan_id:
            return JsonResponse({
                'success': False,
                'message': 'لطفاً یک پلن انتخاب کنید.'
            }, status=400)

        product = get_object_or_404(Product, slug=slug, is_active=True)
        plan = get_object_or_404(LicensePlan, id=plan_id, product=product, is_active=True)

        from shop.services.plan_guards import evaluate_plan_purchase
        purchase_ok, purchase_message, _ = evaluate_plan_purchase(request.user, plan)
        if not purchase_ok:
            return JsonResponse({
                'success': False,
                'message': purchase_message,
            }, status=400)

        discount_code_obj = None
        if discount_code_str:
            try:
                discount_code_obj = DiscountCode.objects.get(code=discount_code_str)
            except DiscountCode.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'کد تخفیف یافت نشد.'
                }, status=400)

            is_valid, error_msg = discount_code_obj.is_valid(request.user)
            if not is_valid:
                return JsonResponse({
                    'success': False,
                    'message': error_msg
                }, status=400)

        base_pricing = calculate_plan_purchase_prices(
            plan, product, request.user, request=request, quantity=quantity,
        )
        pricing = calculate_plan_purchase_prices(
            plan,
            product,
            request.user,
            request=request,
            quantity=quantity,
            discount_code=discount_code_obj,
        )

        if discount_code_obj and pricing['final_price'] >= base_pricing['final_price']:
            return JsonResponse({
                'success': False,
                'message': 'کد تخفیف قابل اعمال نیست.'
            }, status=400)

        discount_details = []
        if base_pricing['has_promo_offer']:
            promo_amount = int(base_pricing['original_price'] - (base_pricing['unit_sale_price'] * base_pricing['quantity']))
            if promo_amount > 0:
                discount_details.append({
                    'type': 'promo_offer',
                    'label': f'{plan.promo_discount_percent()}% آفر ویژه',
                    'amount': promo_amount,
                })
        if base_pricing['has_repeat_discount']:
            repeat_amount = int(
                (base_pricing['unit_sale_price'] * base_pricing['quantity'])
                - (base_pricing['final_price'] if not discount_code_obj else pricing['final_price'])
            )
            discount_details.append({
                'type': 'repeat_purchase',
                'label': f'{base_pricing["repeat_discount_percentage"]}% تخفیف خرید مجدد',
                'amount': max(0, repeat_amount),
            })

        if discount_code_obj:
            code_discount = int(base_pricing['final_price'] - pricing['final_price'])
            if code_discount > 0:
                if discount_code_obj.discount_type == 'percentage':
                    discount_label = f'{int(discount_code_obj.discount_value)}% تخفیف'
                else:
                    discount_label = f'{int(discount_code_obj.discount_value):,} تومان تخفیف'
                discount_details.append({
                    'type': 'discount_code',
                    'label': discount_label,
                    'code': discount_code_obj.code,
                    'amount': code_discount,
                })

        return JsonResponse({
            'success': True,
            'original_price': int(pricing['original_price']),
            'total_discount': int(pricing['discount_amount']),
            'final_price': int(pricing['final_price']),
            'discount_details': discount_details,
            'has_discount': pricing['has_discount'],
            'quantity': pricing['quantity'],
        })

    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse({
            'success': False,
            'message': 'خطا در پردازش درخواست.'
        }, status=400)
    except Exception:
        return JsonResponse({
            'success': False,
            'message': 'خطایی رخ داد. لطفاً دوباره تلاش کنید.'
        }, status=500)

