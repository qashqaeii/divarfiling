"""
ویوهای فروشگاه
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, TemplateView, CreateView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.conf import settings
from django.db import models
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views import View
from django.views.decorators.http import require_POST
from django.utils import timezone
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
        context['meta_title'] = 'فایلینگ دیوار — میزکار CRM رایگان + ربات استخراج املاک'
        context['meta_description'] = (
            'پلتفرم تخصصی مشاوران املاک: CRM رایگان، ربات استخراج دیوار، '
            'فایلینگ خودکار و تحلیل بازار در میزکار.'
        )
        context['meta_keywords'] = (
            'فایلینگ دیوار, CRM املاک, ربات دیوار, استخراج آگهی, '
            'تحلیل بازار املاک, میزکار مشاور, نرم افزار CRM املاک'
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

    def get_template_names(self):
        if self.object and self.object.slug == BOT_PRODUCT_SLUG:
            return ['shop/product_bot.html']
        return ['shop/product_detail.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.object
        context['plans'] = product.plans.filter(is_active=True).order_by('order', 'price')
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


class BuyView(LoginRequiredMixin, CreateView):
    model = Order
    form_class = BuyForm
    template_name = 'shop/buy.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.product = get_object_or_404(Product, slug=kwargs['slug'], is_active=True)
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['product'] = self.product
        requested_plan = self._get_requested_plan()
        if requested_plan and not kwargs.get('data'):
            kwargs.setdefault('initial', {})['plan'] = requested_plan.pk
        return kwargs

    def _get_requested_plan(self):
        plan_id = self.request.GET.get('plan')
        if not plan_id:
            return None
        try:
            return self.product.plans.get(pk=int(plan_id), is_active=True)
        except (LicensePlan.DoesNotExist, ValueError, TypeError):
            return None
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # بررسی اینکه آیا کاربر قبلاً خرید پرداخت شده برای این محصول دارد
        has_previous_purchase = Order.objects.filter(
            user=self.request.user,
            product=self.product,
            status='paid'
        ).exists()
        
        # محاسبه قیمت‌ها برای هر پلن
        plans_with_prices = []
        for plan in self.product.plans.filter(is_active=True).order_by('order', 'price'):
            original_price = plan.price
            discount_amount = 0
            final_price = original_price
            discount_reasons = []
            
            # اعمال تخفیف خریدهای بعدی (اگر کاربر قبلاً خرید کرده باشد)
            if has_previous_purchase and self.product.repeat_purchase_discount > 0:
                from decimal import Decimal
                repeat_discount_percentage = Decimal(str(self.product.repeat_purchase_discount))
                repeat_discount = (original_price * repeat_discount_percentage) // 100
                discount_amount += repeat_discount
                final_price -= repeat_discount
                discount_reasons.append(f'{int(repeat_discount_percentage)}% تخفیف خرید مجدد')

            # تخفیف معرف
            if self.request.user.is_authenticated:
                from affiliates.services import apply_affiliate_discount
                aff_disc, final_price, aff_label = apply_affiliate_discount(
                    self.request.user, self.request, self.product, final_price
                )
                if aff_disc > 0:
                    discount_amount += aff_disc
                    if aff_label:
                        discount_reasons.append(aff_label)
            
            plans_with_prices.append({
                'plan': plan,
                'original_price': original_price,
                'discount_amount': discount_amount,
                'final_price': final_price,
                'has_discount': discount_amount > 0,
                'has_repeat_discount': has_previous_purchase and self.product.repeat_purchase_discount > 0,
                'repeat_discount_percentage': int(self.product.repeat_purchase_discount) if has_previous_purchase else 0,
                'discount_reasons': discount_reasons,
            })
        
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
                selected_plan_id = requested_plan.pk
            elif plans_with_prices:
                selected_plan_id = plans_with_prices[0]['plan'].pk

        context.update({
            'product': self.product,
            'plans_with_prices': plans_with_prices,
            'selected_plan_id': selected_plan_id,
            'has_previous_purchase': has_previous_purchase,
            'pay_settings': pay_settings,
            'payment_methods': payment_methods,
            'show_payment_choice': len(payment_methods) > 1,
        })
        
        return context
    
    def form_valid(self, form):
        order = form.save(commit=False)
        order.user = self.request.user
        order.product = self.product
        
        # محاسبه قیمت با در نظر گیری تخفیف خریدهای بعدی و کد تخفیف
        original_price = order.plan.price
        total_discount_amount = 0
        
        # ذخیره قیمت اصلی
        order.original_price = original_price
        
        # بررسی اینکه آیا کاربر قبلاً خرید پرداخت شده برای این محصول دارد
        has_previous_purchase = Order.objects.filter(
            user=self.request.user,
            product=self.product,
            status='paid'
        ).exists()
        
        # محاسبه قیمت پس از تخفیف‌ها
        price_after_discounts = original_price
        
        # اعمال تخفیف خریدهای بعدی
        if has_previous_purchase and self.product.repeat_purchase_discount > 0:
            from decimal import Decimal
            repeat_discount_percentage = Decimal(str(self.product.repeat_purchase_discount))
            repeat_discount = (original_price * repeat_discount_percentage) // 100
            total_discount_amount += repeat_discount
            price_after_discounts -= repeat_discount

        # تخفیف معرف (قبل از کد تخفیف)
        from affiliates.services import apply_affiliate_discount, resolve_order_affiliate
        affiliate = resolve_order_affiliate(self.request.user, self.request)
        if affiliate:
            order.affiliate = affiliate
        affiliate_discount, price_after_discounts, _affiliate_label = apply_affiliate_discount(
            self.request.user, self.request, self.product, price_after_discounts
        )
        if affiliate_discount > 0:
            total_discount_amount += affiliate_discount
        
        # اعمال کد تخفیف
        discount_code = form.cleaned_data.get('discount_code')
        if discount_code:
            is_valid, message = discount_code.is_valid(self.request.user)
            if not is_valid:
                form.add_error('discount_code', message)
                return self.form_invalid(form)
            
            order.discount_code = discount_code
            code_discount, _ = discount_code.calculate_discount(price_after_discounts, self.request.user)
            if code_discount > 0:
                total_discount_amount += code_discount
                price_after_discounts -= code_discount
            else:
                form.add_error('discount_code', 'کد تخفیف قابل اعمال نیست.')
                return self.form_invalid(form)
        
        # ذخیره مبالغ نهایی
        order.discount_amount = total_discount_amount
        order.amount = max(0, price_after_discounts)  # اطمینان از اینکه مبلغ منفی نشود

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
        user = self.request.user
        if user.is_authenticated:
            from workspace.services.access import get_bot_access_state
            access = get_bot_access_state(user)
            ctx['has_bot_license'] = access['has_bot_license']
        else:
            ctx['has_bot_license'] = False
        ctx['meta_title'] = 'آموزش — مرکز یادگیری فایلینگ دیوار'
        ctx['meta_description'] = (
            'مسیرهای یادگیری CRM رایگان، ربات استخراج دیوار، فایلینگ و تحلیل بازار. '
            'راهنماهای گام‌به‌گام برای مشاوران املاک.'
        )
        ctx['meta_keywords'] = (
            'آموزش فایلینگ دیوار, راهنمای CRM املاک, آموزش ربات دیوار, '
            'تحلیل بازار املاک, میزکار مشاور'
        )
        return ctx


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
    from decimal import Decimal
    import json
    
    try:
        data = json.loads(request.body)
        discount_code_str = data.get('discount_code', '').strip().upper()
        plan_id = data.get('plan_id')
        
        if not plan_id:
            return JsonResponse({
                'success': False,
                'message': 'لطفاً یک پلن انتخاب کنید.'
            }, status=400)
        
        # دریافت محصول و پلن
        product = get_object_or_404(Product, slug=slug, is_active=True)
        plan = get_object_or_404(LicensePlan, id=plan_id, product=product, is_active=True)
        
        # محاسبه قیمت اولیه
        original_price = plan.price
        price_after_discounts = original_price
        total_discount_amount = 0
        discount_details = []
        
        # بررسی تخفیف خریدهای بعدی
        has_previous_purchase = Order.objects.filter(
            user=request.user,
            product=product,
            status='paid'
        ).exists()
        
        if has_previous_purchase and product.repeat_purchase_discount > 0:
            repeat_discount_percentage = Decimal(str(product.repeat_purchase_discount))
            repeat_discount = (original_price * repeat_discount_percentage) // 100
            total_discount_amount += repeat_discount
            price_after_discounts -= repeat_discount
            discount_details.append({
                'type': 'repeat_purchase',
                'label': f'{int(repeat_discount_percentage)}% تخفیف خرید مجدد',
                'amount': int(repeat_discount)
            })

        from affiliates.services import apply_affiliate_discount
        aff_disc, price_after_discounts, aff_label = apply_affiliate_discount(
            request.user, request, product, price_after_discounts
        )
        if aff_disc > 0:
            total_discount_amount += aff_disc
            discount_details.append({
                'type': 'affiliate',
                'label': aff_label or 'تخفیف معرف',
                'amount': int(aff_disc),
            })
        
        # بررسی کد تخفیف
        code_discount = 0
        discount_code_obj = None
        if discount_code_str:
            try:
                discount_code_obj = DiscountCode.objects.get(code=discount_code_str)
                
                # بررسی اعتبار کد تخفیف
                is_valid, error_msg = discount_code_obj.is_valid(request.user)
                if not is_valid:
                    return JsonResponse({
                        'success': False,
                        'message': error_msg
                    }, status=400)
                
                # محاسبه تخفیف کد
                code_discount, discount_message = discount_code_obj.calculate_discount(price_after_discounts, request.user)
                
                if code_discount > 0:
                    total_discount_amount += code_discount
                    price_after_discounts -= code_discount
                    
                    discount_label = ''
                    if discount_code_obj.discount_type == 'percentage':
                        discount_label = f'{int(discount_code_obj.discount_value)}% تخفیف'
                    else:
                        discount_label = f'{int(discount_code_obj.discount_value):,} تومان تخفیف'
                    
                    discount_details.append({
                        'type': 'discount_code',
                        'label': discount_label,
                        'code': discount_code_obj.code,
                        'amount': int(code_discount)
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': discount_message or 'کد تخفیف قابل اعمال نیست.'
                    }, status=400)
                    
            except DiscountCode.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'کد تخفیف یافت نشد.'
                }, status=400)
        
        # اطمینان از اینکه مبلغ منفی نشود
        final_price = max(0, price_after_discounts)
        
        return JsonResponse({
            'success': True,
            'original_price': int(original_price),
            'total_discount': int(total_discount_amount),
            'final_price': int(final_price),
            'discount_details': discount_details,
            'has_discount': total_discount_amount > 0
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'خطا در پردازش درخواست.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'خطایی رخ داد. لطفاً دوباره تلاش کنید.'
        }, status=500)

