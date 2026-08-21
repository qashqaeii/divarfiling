"""ویوهای ورود و ثبت‌نام مبتنی بر OTP / پیامک."""
from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View

from accounts.forms import (
    OtpCodeForm,
    OtpPhoneForm,
    RegisterPasswordForm,
)
from accounts.models import User, UserProfile
from accounts.phone_utils import normalize_phone, phone_username
from accounts.services.otp import OtpError, OtpRateLimitError, request_otp, verify_otp

logger = logging.getLogger(__name__)

SESSION_PHONE = 'otp_phone'
SESSION_PURPOSE = 'otp_purpose'
SESSION_NEXT = 'otp_next'
SESSION_REGISTER_VERIFIED = 'otp_register_verified'
SESSION_REGISTER_PASSWORD = 'otp_register_password_hash'
SESSION_RESET_VERIFIED = 'otp_reset_verified'


def _safe_next(request, fallback='workspace:home'):
    next_url = request.GET.get('next') or request.POST.get('next') or request.session.get(SESSION_NEXT)
    if next_url and str(next_url).startswith('/') and not str(next_url).startswith('//'):
        return next_url
    return reverse_lazy(fallback) if ':' in fallback else fallback


def _store_challenge(request, phone: str, purpose: str):
    request.session[SESSION_PHONE] = phone
    request.session[SESSION_PURPOSE] = purpose
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url:
        request.session[SESSION_NEXT] = next_url
    request.session.modified = True


def _clear_otp_session(request):
    for key in (
        SESSION_PHONE,
        SESSION_PURPOSE,
        SESSION_NEXT,
        SESSION_REGISTER_VERIFIED,
        SESSION_REGISTER_PASSWORD,
        SESSION_RESET_VERIFIED,
    ):
        request.session.pop(key, None)


class OtpLoginStartView(View):
    """ورود با پیامک — مرحله ۱: شماره موبایل."""

    template_name = 'accounts/otp_login.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(_safe_next(request))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name, {
            'form': OtpPhoneForm(),
            'step': 'phone',
            'next': request.GET.get('next', ''),
        })

    def post(self, request):
        form = OtpPhoneForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form,
                'step': 'phone',
                'next': request.POST.get('next', ''),
            })

        phone = form.cleaned_data['phone']
        if not User.objects.filter(phone=phone).exists():
            form.add_error('phone', 'حسابی با این شماره یافت نشد. ابتدا ثبت‌نام کنید.')
            return render(request, self.template_name, {
                'form': form,
                'step': 'phone',
                'next': request.POST.get('next', ''),
            })

        try:
            challenge = request_otp(phone, 'login', request=request)
        except OtpRateLimitError as exc:
            messages.error(request, exc.message)
            return render(request, self.template_name, {
                'form': form,
                'step': 'phone',
                'next': request.POST.get('next', ''),
                'retry_after': exc.retry_after,
            })
        except OtpError as exc:
            messages.error(request, exc.message)
            return render(request, self.template_name, {
                'form': form,
                'step': 'phone',
                'next': request.POST.get('next', ''),
            })

        _store_challenge(request, challenge.phone, 'login')
        messages.success(request, 'کد تأیید به شماره شما ارسال شد.')
        url = reverse('otp_login_verify')
        next_q = request.POST.get('next') or request.GET.get('next')
        if next_q:
            url = f'{url}?next={next_q}'
        return redirect(url)


class OtpLoginVerifyView(View):
    """ورود با پیامک — مرحله ۲: تأیید کد."""

    template_name = 'accounts/otp_login.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(_safe_next(request))
        phone = request.session.get(SESSION_PHONE)
        purpose = request.session.get(SESSION_PURPOSE)
        if not phone or purpose != 'login':
            return redirect('otp_login')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        phone = request.session.get(SESSION_PHONE)
        return render(request, self.template_name, {
            'form': OtpCodeForm(),
            'step': 'code',
            'phone': phone,
            'phone_display': _display_phone(phone),
            'next': request.GET.get('next', ''),
            'resend_url': reverse('otp_login_resend'),
        })

    def post(self, request):
        phone = request.session.get(SESSION_PHONE)
        form = OtpCodeForm(request.POST)
        ctx = {
            'form': form,
            'step': 'code',
            'phone': phone,
            'phone_display': _display_phone(phone),
            'next': request.POST.get('next', ''),
            'resend_url': reverse('otp_login_resend'),
        }
        if not form.is_valid():
            return render(request, self.template_name, ctx)

        try:
            verify_otp(phone, 'login', form.cleaned_data['code'])
        except OtpError as exc:
            form.add_error('code', exc.message)
            return render(request, self.template_name, ctx)

        user = User.objects.filter(phone=phone).first()
        if not user or not user.is_active:
            messages.error(request, 'حساب کاربری یافت نشد یا غیرفعال است.')
            _clear_otp_session(request)
            return redirect('otp_login')

        if not user.phone_verified:
            user.mark_phone_verified()

        login(request, user, backend='accounts.backends.PhoneAuthBackend')
        next_url = _safe_next(request)
        _clear_otp_session(request)
        return redirect(next_url)


class OtpLoginResendView(View):
    def post(self, request):
        phone = request.session.get(SESSION_PHONE)
        purpose = request.session.get(SESSION_PURPOSE)
        if not phone or purpose != 'login':
            return redirect('otp_login')
        try:
            request_otp(phone, 'login', request=request)
            messages.success(request, 'کد جدید ارسال شد.')
        except OtpRateLimitError as exc:
            messages.error(request, exc.message)
        except OtpError as exc:
            messages.error(request, exc.message)
        url = reverse('otp_login_verify')
        next_q = request.POST.get('next') or request.GET.get('next')
        if next_q:
            url = f'{url}?next={next_q}'
        return redirect(url)


class OtpRegisterStartView(View):
    """ثبت‌نام — مرحله ۱: شماره موبایل."""

    template_name = 'accounts/otp_register.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(_safe_next(request))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name, {
            'form': OtpPhoneForm(),
            'step': 'phone',
            'next': request.GET.get('next', ''),
        })

    def post(self, request):
        form = OtpPhoneForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form,
                'step': 'phone',
                'next': request.POST.get('next', ''),
            })

        phone = form.cleaned_data['phone']
        if User.objects.filter(phone=phone).exists():
            form.add_error('phone', 'این شماره قبلاً ثبت‌نام شده است. وارد شوید.')
            return render(request, self.template_name, {
                'form': form,
                'step': 'phone',
                'next': request.POST.get('next', ''),
            })

        try:
            challenge = request_otp(phone, 'register', request=request)
        except OtpRateLimitError as exc:
            messages.error(request, exc.message)
            return render(request, self.template_name, {
                'form': form,
                'step': 'phone',
                'next': request.POST.get('next', ''),
                'retry_after': exc.retry_after,
                'show_password_fallback': True,
            })
        except OtpError as exc:
            messages.error(
                request,
                f'{exc.message} می‌توانید فعلاً با رمز عبور ثبت‌نام کنید.',
            )
            url = reverse('register_password')
            next_q = request.POST.get('next') or request.GET.get('next')
            if next_q:
                url = f'{url}?next={next_q}'
            return redirect(url)

        _store_challenge(request, challenge.phone, 'register')
        request.session.pop(SESSION_REGISTER_VERIFIED, None)
        messages.success(request, 'کد تأیید به شماره شما ارسال شد.')
        url = reverse('otp_register_verify')
        next_q = request.POST.get('next') or request.GET.get('next')
        if next_q:
            url = f'{url}?next={next_q}'
        return redirect(url)


class OtpRegisterVerifyView(View):
    """ثبت‌نام — مرحله ۲: تأیید کد."""

    template_name = 'accounts/otp_register.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(_safe_next(request))
        phone = request.session.get(SESSION_PHONE)
        purpose = request.session.get(SESSION_PURPOSE)
        if not phone or purpose != 'register':
            return redirect('register')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        phone = request.session.get(SESSION_PHONE)
        return render(request, self.template_name, {
            'form': OtpCodeForm(),
            'step': 'code',
            'phone': phone,
            'phone_display': _display_phone(phone),
            'next': request.GET.get('next', ''),
            'resend_url': reverse('otp_register_resend'),
        })

    def post(self, request):
        phone = request.session.get(SESSION_PHONE)
        form = OtpCodeForm(request.POST)
        ctx = {
            'form': form,
            'step': 'code',
            'phone': phone,
            'phone_display': _display_phone(phone),
            'next': request.POST.get('next', ''),
            'resend_url': reverse('otp_register_resend'),
        }
        if not form.is_valid():
            return render(request, self.template_name, ctx)

        try:
            verify_otp(phone, 'register', form.cleaned_data['code'])
        except OtpError as exc:
            form.add_error('code', exc.message)
            return render(request, self.template_name, ctx)

        request.session[SESSION_REGISTER_VERIFIED] = True
        request.session.modified = True
        url = reverse('otp_register_password')
        next_q = request.POST.get('next') or request.GET.get('next')
        if next_q:
            url = f'{url}?next={next_q}'
        return redirect(url)


class OtpRegisterResendView(View):
    def post(self, request):
        phone = request.session.get(SESSION_PHONE)
        purpose = request.session.get(SESSION_PURPOSE)
        if not phone or purpose != 'register':
            return redirect('register')
        try:
            request_otp(phone, 'register', request=request)
            messages.success(request, 'کد جدید ارسال شد.')
        except OtpRateLimitError as exc:
            messages.error(request, exc.message)
        except OtpError as exc:
            messages.error(request, exc.message)
        url = reverse('otp_register_verify')
        next_q = request.POST.get('next') or request.GET.get('next')
        if next_q:
            url = f'{url}?next={next_q}'
        return redirect(url)


class OtpRegisterPasswordView(View):
    """ثبت‌نام — مرحله ۳: تعیین رمز عبور و ایجاد حساب."""

    template_name = 'accounts/otp_register.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(_safe_next(request))
        phone = request.session.get(SESSION_PHONE)
        if (
            not phone
            or request.session.get(SESSION_PURPOSE) != 'register'
            or not request.session.get(SESSION_REGISTER_VERIFIED)
        ):
            return redirect('register')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        phone = request.session.get(SESSION_PHONE)
        return render(request, self.template_name, {
            'form': RegisterPasswordForm(),
            'step': 'password',
            'phone': phone,
            'phone_display': _display_phone(phone),
            'next': request.GET.get('next', ''),
        })

    def post(self, request):
        phone = request.session.get(SESSION_PHONE)
        form = RegisterPasswordForm(request.POST)
        ctx = {
            'form': form,
            'step': 'password',
            'phone': phone,
            'phone_display': _display_phone(phone),
            'next': request.POST.get('next', ''),
        }
        if not form.is_valid():
            return render(request, self.template_name, ctx)

        from accounts.services.account_completion import AccountCompletionError, create_user_from_verified_phone

        try:
            user = create_user_from_verified_phone(
                phone,
                form.cleaned_data['password1'],
                request=request,
            )
        except AccountCompletionError as exc:
            messages.error(request, exc.message)
            _clear_otp_session(request)
            return redirect('login')

        login(request, user, backend='accounts.backends.PhoneAuthBackend')
        next_url = _safe_next(request)
        _clear_otp_session(request)
        messages.success(request, 'حساب شما با موفقیت ساخته شد.')
        return redirect(next_url)


class OtpVerifyPhoneView(View):
    """تأیید موبایل حساب جاری — برای خرید پلن آزمایشی و موارد مشابه."""

    template_name = 'accounts/otp_verify_phone.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            login_url = reverse('login')
            next_path = request.get_full_path()
            return redirect(f'{login_url}?next={next_path}')
        if request.user.phone_verified:
            messages.info(request, 'شماره موبایل شما قبلاً تأیید شده است.')
            return redirect(_safe_next(request, 'dashboard'))
        return super().dispatch(request, *args, **kwargs)

    def _account_phone(self, request) -> str:
        from accounts.phone_utils import is_valid_iran_mobile, normalize_phone

        return normalize_phone(request.user.phone or '')

    def _ensure_otp_sent(self, request, phone: str) -> bool:
        if (
            request.session.get(SESSION_PURPOSE) == 'verify_phone'
            and request.session.get(SESSION_PHONE) == phone
        ):
            return True
        try:
            request_otp(phone, 'verify_phone', request=request)
            _store_challenge(request, phone, 'verify_phone')
            return True
        except OtpRateLimitError as exc:
            messages.error(request, str(exc))
        except OtpError as exc:
            messages.error(request, str(exc))
        return False

    def get(self, request):
        from accounts.phone_utils import is_valid_iran_mobile

        phone = self._account_phone(request)
        if not is_valid_iran_mobile(phone):
            messages.error(
                request,
                'شماره موبایل حساب شما معتبر نیست. ابتدا از پروفایل آن را اصلاح کنید.',
            )
            return redirect('profile')

        self._ensure_otp_sent(request, phone)
        return render(request, self.template_name, {
            'form': OtpCodeForm(),
            'phone_display': _display_phone(phone),
            'next': request.GET.get('next', ''),
            'resend_url': reverse('otp_verify_phone_resend'),
        })

    def post(self, request):
        from accounts.phone_utils import is_valid_iran_mobile

        phone = self._account_phone(request)
        if not is_valid_iran_mobile(phone):
            messages.error(request, 'شماره موبایل حساب شما معتبر نیست.')
            return redirect('profile')

        form = OtpCodeForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form,
                'phone_display': _display_phone(phone),
                'next': request.POST.get('next', ''),
                'resend_url': reverse('otp_verify_phone_resend'),
            })

        session_phone = request.session.get(SESSION_PHONE)
        if session_phone != phone:
            messages.error(request, 'نشست تأیید منقضی شده — کد جدید درخواست دهید.')
            return redirect(request.path + (f'?next={request.POST.get("next")}' if request.POST.get('next') else ''))

        try:
            verify_otp(phone, 'verify_phone', form.cleaned_data['code'])
        except OtpError as exc:
            messages.error(request, str(exc))
            return render(request, self.template_name, {
                'form': form,
                'phone_display': _display_phone(phone),
                'next': request.POST.get('next', ''),
                'resend_url': reverse('otp_verify_phone_resend'),
            })

        request.user.mark_phone_verified()
        next_url = _safe_next(request, 'dashboard')
        _clear_otp_session(request)
        messages.success(request, 'شماره موبایل شما با موفقیت تأیید شد.')
        return redirect(next_url)


class OtpVerifyPhoneResendView(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        phone = normalize_phone(request.user.phone or '')
        try:
            request_otp(phone, 'verify_phone', request=request)
            _store_challenge(request, phone, 'verify_phone')
            messages.success(request, 'کد تأیید مجدداً ارسال شد.')
        except OtpRateLimitError as exc:
            messages.error(request, str(exc))
        except OtpError as exc:
            messages.error(request, str(exc))

        url = reverse('otp_verify_phone')
        next_url = request.POST.get('next')
        if next_url:
            url = f'{url}?next={next_url}'
        return redirect(url)


def _display_phone(phone: str) -> str:
    phone = normalize_phone(phone or '')
    if len(phone) == 11:
        return f'{phone[:4]}***{phone[-2:]}'
    return phone


class OtpPasswordResetStartView(View):
    """بازیابی رمز — مرحله ۱: شماره موبایل."""

    template_name = 'accounts/otp_password_reset.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(_safe_next(request))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name, {
            'form': OtpPhoneForm(),
            'step': 'phone',
        })

    def post(self, request):
        form = OtpPhoneForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form,
                'step': 'phone',
            })

        phone = form.cleaned_data['phone']
        if not User.objects.filter(phone=phone, is_active=True).exists():
            form.add_error('phone', 'حسابی با این شماره یافت نشد.')
            return render(request, self.template_name, {
                'form': form,
                'step': 'phone',
            })

        try:
            challenge = request_otp(phone, 'password_reset', request=request)
        except OtpRateLimitError as exc:
            messages.error(request, exc.message)
            return render(request, self.template_name, {
                'form': form,
                'step': 'phone',
                'retry_after': exc.retry_after,
            })
        except OtpError as exc:
            messages.error(request, exc.message)
            return render(request, self.template_name, {
                'form': form,
                'step': 'phone',
            })

        _store_challenge(request, challenge.phone, 'password_reset')
        request.session.pop(SESSION_RESET_VERIFIED, None)
        messages.success(request, 'کد تأیید به شماره شما ارسال شد.')
        return redirect('otp_password_reset_verify')


class OtpPasswordResetVerifyView(View):
    """بازیابی رمز — مرحله ۲: تأیید کد."""

    template_name = 'accounts/otp_password_reset.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(_safe_next(request))
        phone = request.session.get(SESSION_PHONE)
        purpose = request.session.get(SESSION_PURPOSE)
        if not phone or purpose != 'password_reset':
            return redirect('password_reset')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        phone = request.session.get(SESSION_PHONE)
        return render(request, self.template_name, {
            'form': OtpCodeForm(),
            'step': 'code',
            'phone': phone,
            'phone_display': _display_phone(phone),
            'resend_url': reverse('otp_password_reset_resend'),
        })

    def post(self, request):
        phone = request.session.get(SESSION_PHONE)
        form = OtpCodeForm(request.POST)
        ctx = {
            'form': form,
            'step': 'code',
            'phone': phone,
            'phone_display': _display_phone(phone),
            'resend_url': reverse('otp_password_reset_resend'),
        }
        if not form.is_valid():
            return render(request, self.template_name, ctx)

        try:
            verify_otp(phone, 'password_reset', form.cleaned_data['code'])
        except OtpError as exc:
            form.add_error('code', exc.message)
            return render(request, self.template_name, ctx)

        if not User.objects.filter(phone=phone, is_active=True).exists():
            messages.error(request, 'حساب کاربری یافت نشد یا غیرفعال است.')
            _clear_otp_session(request)
            return redirect('password_reset')

        request.session[SESSION_RESET_VERIFIED] = True
        request.session.modified = True
        return redirect('otp_password_reset_password')


class OtpPasswordResetResendView(View):
    def post(self, request):
        phone = request.session.get(SESSION_PHONE)
        purpose = request.session.get(SESSION_PURPOSE)
        if not phone or purpose != 'password_reset':
            return redirect('password_reset')
        try:
            request_otp(phone, 'password_reset', request=request)
            messages.success(request, 'کد جدید ارسال شد.')
        except OtpRateLimitError as exc:
            messages.error(request, exc.message)
        except OtpError as exc:
            messages.error(request, exc.message)
        return redirect('otp_password_reset_verify')


class OtpPasswordResetPasswordView(View):
    """بازیابی رمز — مرحله ۳: تعیین رمز جدید."""

    template_name = 'accounts/otp_password_reset.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(_safe_next(request))
        phone = request.session.get(SESSION_PHONE)
        if (
            not phone
            or request.session.get(SESSION_PURPOSE) != 'password_reset'
            or not request.session.get(SESSION_RESET_VERIFIED)
        ):
            return redirect('password_reset')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        phone = request.session.get(SESSION_PHONE)
        return render(request, self.template_name, {
            'form': RegisterPasswordForm(),
            'step': 'password',
            'phone': phone,
            'phone_display': _display_phone(phone),
        })

    def post(self, request):
        phone = request.session.get(SESSION_PHONE)
        form = RegisterPasswordForm(request.POST)
        ctx = {
            'form': form,
            'step': 'password',
            'phone': phone,
            'phone_display': _display_phone(phone),
        }
        if not form.is_valid():
            return render(request, self.template_name, ctx)

        from accounts.services.account_completion import AccountCompletionError, set_password_for_phone

        try:
            set_password_for_phone(phone, form.cleaned_data['password1'])
        except AccountCompletionError as exc:
            messages.error(request, exc.message)
            _clear_otp_session(request)
            return redirect('password_reset')

        _clear_otp_session(request)
        messages.success(request, 'رمز عبور شما با موفقیت تغییر کرد. اکنون می‌توانید وارد شوید.')
        return redirect('login')
