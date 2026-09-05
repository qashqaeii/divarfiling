"""
فرم‌های فروشگاه
"""
from django import forms
from .models import Order, LicensePlan, ProductRating, ProductReview


class BuyForm(forms.ModelForm):
    plan = forms.ModelChoiceField(
        queryset=LicensePlan.objects.none(),
        widget=forms.RadioSelect,
        label='انتخاب پلن'
    )
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        required=False,
        label='تعداد مشاور',
        widget=forms.NumberInput(attrs={
            'class': 'ck-qty-input',
            'min': '1',
            'step': '1',
            'inputmode': 'numeric',
        }),
    )
    discount_code = forms.CharField(
        max_length=50,
        required=False,
        label='کد تخفیف',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'کد تخفیف خود را وارد کنید (اختیاری)'
        })
    )
    
    class Meta:
        model = Order
        fields = ['plan']
    
    def __init__(self, *args, **kwargs):
        product = kwargs.pop('product', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.user = user
        if product:
            qs = LicensePlan.objects.filter(
                product=product,
                is_active=True,
            )
            if user and user.is_authenticated:
                from shop.services.plan_guards import user_has_purchased_daily_plan
                if user_has_purchased_daily_plan(user):
                    qs = qs.exclude(plan_type='daily')
            self.fields['plan'].queryset = qs

    def clean_plan(self):
        plan = self.cleaned_data.get('plan')
        if plan and self.user and self.user.is_authenticated:
            from shop.services.plan_guards import evaluate_plan_purchase
            ok, message, _ = evaluate_plan_purchase(self.user, plan)
            if not ok:
                raise forms.ValidationError(message)
        return plan

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity') or 1
        plan = self.cleaned_data.get('plan')
        if not plan:
            return 1
        from shop.services.plan_pricing import clamp_quantity
        return clamp_quantity(plan, quantity)

    def clean(self):
        cleaned = super().clean()
        plan = cleaned.get('plan')
        quantity = cleaned.get('quantity') or 1
        if plan and not plan.allow_bulk_purchase and quantity != 1:
            self.add_error('quantity', 'این پلن فقط به‌صورت تکی قابل خرید است.')
        return cleaned
    
    def clean_discount_code(self):
        discount_code = self.cleaned_data.get('discount_code', '').strip().upper()
        if discount_code:
            from .models import DiscountCode
            try:
                code_obj = DiscountCode.objects.get(code=discount_code)
                # بررسی اعتبار کد تخفیف (بدون user چون در این مرحله user در دسترس نیست)
                is_valid, message = code_obj.is_valid()
                if not is_valid:
                    raise forms.ValidationError(message)
                return code_obj
            except DiscountCode.DoesNotExist:
                raise forms.ValidationError('کد تخفیف یافت نشد.')
        return None


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100, label='نام', widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(label='ایمیل', widget=forms.EmailInput(attrs={'class': 'form-control'}))
    subject = forms.CharField(max_length=200, label='موضوع', widget=forms.TextInput(attrs={'class': 'form-control'}))
    message = forms.CharField(
        label='پیام',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5})
    )


class RatingForm(forms.ModelForm):
    """فرم امتیازدهی محصول"""
    rating = forms.ChoiceField(
        choices=ProductRating.RATING_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'rating-radio'}),
        label='امتیاز شما'
    )
    
    class Meta:
        model = ProductRating
        fields = ['rating']
    
    def __init__(self, *args, **kwargs):
        self.product = kwargs.pop('product', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        rating = super().save(commit=False)
        if self.product:
            rating.product = self.product
        if self.user:
            rating.user = self.user
        
        # اگر کاربر قبلاً امتیاز داده، آن را به‌روزرسانی کن
        if commit:
            existing_rating = ProductRating.objects.filter(
                product=self.product,
                user=self.user
            ).first()
            if existing_rating:
                existing_rating.rating = rating.rating
                existing_rating.save()
                return existing_rating
            rating.save()
        return rating


class ReviewForm(forms.ModelForm):
    """فرم ثبت نظر محصول"""
    title = forms.CharField(
        max_length=200,
        label='عنوان نظر',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'عنوان نظر خود را وارد کنید'
        })
    )
    content = forms.CharField(
        label='متن نظر',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 6,
            'placeholder': 'نظر خود را در مورد این محصول بنویسید...'
        })
    )
    
    class Meta:
        model = ProductReview
        fields = ['title', 'content']
    
    def __init__(self, *args, **kwargs):
        self.product = kwargs.pop('product', None)
        self.user = kwargs.pop('user', None)
        self.rating = kwargs.pop('rating', None)
        super().__init__(*args, **kwargs)
    
    def save(self, commit=True):
        review = super().save(commit=False)
        if self.product:
            review.product = self.product
        if self.user:
            review.user = self.user
        if self.rating:
            review.rating = self.rating
        
        # بررسی اینکه آیا کاربر قبلاً خرید کرده یا نه
        if self.user and self.product:
            from .models import Order
            has_purchase = Order.objects.filter(
                user=self.user,
                product=self.product,
                status='paid'
            ).exists()
            review.is_verified_purchase = has_purchase
        
        # نظرات کاربران در ادمین بررسی می‌شود و عمومی نمایش داده نمی‌شود
        review.is_approved = False
        
        if commit:
            review.save()
        return review

