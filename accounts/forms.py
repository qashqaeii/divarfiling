"""
فرم‌های مربوط به حساب کاربری
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, UserProfile
from .phone_utils import is_valid_iran_mobile, normalize_phone, phone_username


class LoginForm(AuthenticationForm):
    """فرم ورود — ورود با شماره موبایل و رمز عبور."""

    username = forms.CharField(
        label='شماره موبایل',
        widget=forms.TextInput(attrs={
            'class': 'auth-form-input',
            'placeholder': '۰۹۱۲۳۴۵۶۷۸۹',
            'autofocus': True,
            'autocomplete': 'tel',
            'dir': 'ltr',
            'inputmode': 'tel',
        }),
    )
    password = forms.CharField(
        label='رمز عبور',
        widget=forms.PasswordInput(attrs={
            'class': 'auth-form-input',
            'placeholder': 'رمز عبور',
            'autocomplete': 'current-password',
        }),
    )

    error_messages = {
        'invalid_login': 'شماره موبایل یا رمز عبور اشتباه است.',
        'inactive': 'این حساب کاربری غیرفعال است.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'شماره موبایل'
        self.fields['password'].label = 'رمز عبور'

    def clean_username(self):
        phone = normalize_phone(self.cleaned_data.get('username', ''))
        if not is_valid_iran_mobile(phone):
            raise forms.ValidationError('شماره موبایل معتبر نیست (مثال: ۰۹۱۲۳۴۵۶۷۸۹).')
        return phone


class RegisterForm(UserCreationForm):
    phone = forms.CharField(
        max_length=20, required=True, label='شماره موبایل',
        widget=forms.TextInput(attrs={'class': 'auth-form-input'}),
    )

    class Meta:
        model = User
        fields = ('phone', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone'].label = 'شماره موبایل'
        self.fields['password1'].label = 'رمز عبور'
        self.fields['password2'].label = 'تکرار رمز عبور'
        widget_attrs = {'class': 'auth-form-input'}
        self.fields['phone'].widget.attrs.update({
            **widget_attrs,
            'placeholder': '۰۹۱۲۳۴۵۶۷۸۹',
            'autocomplete': 'tel',
            'dir': 'ltr',
            'inputmode': 'tel',
        })
        for name in ('password1', 'password2'):
            self.fields[name].widget.attrs.update({
                **widget_attrs,
                'placeholder': 'حداقل ۸ کاراکتر',
                'autocomplete': 'new-password',
            })
        self.fields['password1'].widget.attrs['data-password-strength'] = '1'
        self.fields['password2'].widget.attrs['placeholder'] = 'تکرار رمز عبور'

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get('phone', ''))
        if not is_valid_iran_mobile(phone):
            raise forms.ValidationError('شماره موبایل معتبر نیست (مثال: ۰۹۱۲۳۴۵۶۷۸۹).')
        if User.objects.filter(phone=phone).exists():
            raise forms.ValidationError('این شماره قبلاً ثبت‌نام شده است.')
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        phone = self.cleaned_data['phone']
        user.phone = phone
        user.username = phone_username(phone)
        base_username = user.username
        n = 1
        while User.objects.filter(username=user.username).exclude(pk=user.pk).exists():
            user.username = f'{base_username}_{n}'
            n += 1
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['avatar', 'bio', 'address', 'city', 'postal_code']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'avatar': 'تصویر پروفایل',
            'bio': 'درباره من',
            'address': 'آدرس',
            'city': 'شهر',
            'postal_code': 'کد پستی',
        }


class UserInfoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
        }
        labels = {
            'first_name': 'نام',
            'last_name': 'نام خانوادگی',
            'email': 'ایمیل (اختیاری)',
            'phone': 'شماره موبایل',
        }


class OtpPhoneForm(forms.Form):
    """فرم دریافت شماره برای ارسال OTP."""

    phone = forms.CharField(
        max_length=20,
        label='شماره موبایل',
        widget=forms.TextInput(attrs={
            'class': 'auth-form-input',
            'placeholder': '۰۹۱۲۳۴۵۶۷۸۹',
            'autofocus': True,
            'autocomplete': 'tel',
            'dir': 'ltr',
            'inputmode': 'tel',
        }),
    )

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data.get('phone', ''))
        if not is_valid_iran_mobile(phone):
            raise forms.ValidationError('شماره موبایل معتبر نیست (مثال: ۰۹۱۲۳۴۵۶۷۸۹).')
        return phone


class OtpCodeForm(forms.Form):
    """فرم ورود کد یکبارمصرف."""

    code = forms.CharField(
        max_length=8,
        label='کد تأیید',
        widget=forms.TextInput(attrs={
            'class': 'auth-form-input auth-otp-input',
            'placeholder': '------',
            'autofocus': True,
            'autocomplete': 'one-time-code',
            'dir': 'ltr',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
            'maxlength': '8',
        }),
    )

    def clean_code(self):
        raw = (self.cleaned_data.get('code') or '').strip()
        raw = raw.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))
        if not raw.isdigit():
            raise forms.ValidationError('کد تأیید باید عددی باشد.')
        return raw


class RegisterPasswordForm(forms.Form):
    """تعیین رمز پس از تأیید OTP در ثبت‌نام."""

    password1 = forms.CharField(
        label='رمز عبور',
        widget=forms.PasswordInput(attrs={
            'class': 'auth-form-input',
            'placeholder': 'حداقل ۸ کاراکتر',
            'autocomplete': 'new-password',
            'data-password-strength': '1',
        }),
    )
    password2 = forms.CharField(
        label='تکرار رمز عبور',
        widget=forms.PasswordInput(attrs={
            'class': 'auth-form-input',
            'placeholder': 'تکرار رمز عبور',
            'autocomplete': 'new-password',
        }),
    )

    def clean_password1(self):
        password = self.cleaned_data.get('password1') or ''
        if len(password) < 8:
            raise forms.ValidationError('رمز عبور باید حداقل ۸ کاراکتر باشد.')
        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'رمز عبور و تکرار آن یکسان نیستند.')
        return cleaned
