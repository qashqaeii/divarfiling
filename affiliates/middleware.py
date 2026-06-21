"""
Middleware برای پیگیری لینک‌های افیلیت
"""
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import Affiliate


class AffiliateTrackingMiddleware:
    """Middleware برای ذخیره کد معرف در cookie"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # بررسی وجود پارامتر ref در URL
        ref_code = request.GET.get('ref')
        
        if ref_code:
            # بررسی معتبر بودن کد معرف
            try:
                affiliate = Affiliate.objects.get(code=ref_code, is_active=True)
                # ذخیره در cookie
                response = self.get_response(request)
                max_age = settings.AFFILIATE_COOKIE_DAYS * 24 * 60 * 60
                response.set_cookie(
                    settings.AFFILIATE_COOKIE_NAME,
                    ref_code,
                    max_age=max_age,
                    httponly=True,
                    samesite='Lax'
                )
                return response
            except Affiliate.DoesNotExist:
                pass
        
        return self.get_response(request)
    
    @staticmethod
    def get_affiliate_from_request(request):
        """دریافت افیلیت از cookie یا session"""
        # اول از cookie
        ref_code = request.COOKIES.get(settings.AFFILIATE_COOKIE_NAME)
        
        if ref_code:
            try:
                return Affiliate.objects.get(code=ref_code, is_active=True)
            except Affiliate.DoesNotExist:
                pass
        
        return None

