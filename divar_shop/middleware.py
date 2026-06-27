"""
Middleware برای مدیریت SSL redirect
جلوگیری از redirect IP به HTTPS
"""
import re


class SSLRedirectMiddleware:
    """
    Middleware برای جلوگیری از redirect IP به HTTPS
    فقط برای دامنه‌ها redirect می‌کند
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # از META بخوانید؛ get_host() قبل از CommonMiddleware باعث DisallowedHost پرحجم در لاگ می‌شود.
        host = (request.META.get('HTTP_HOST') or '').split(':')[0]
        
        # الگوی IP (IPv4)
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        
        if re.match(ip_pattern, host):
            # اگر host یک IP است، X-Forwarded-Proto را به http تنظیم می‌کنیم
            # تا Django فکر کند که درخواست HTTP است و redirect نکند
            request.META['HTTP_X_FORWARDED_PROTO'] = 'http'
            # همچنین SECURE_SSL_REDIRECT را برای این درخواست غیرفعال می‌کنیم
            # با تنظیم یک flag که SecurityMiddleware آن را بررسی کند
            request._disable_ssl_redirect = True
        
        response = self.get_response(request)
        return response

