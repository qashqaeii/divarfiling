"""
ابزارهای مربوط به لایسنس
"""
import uuid
import hashlib
import hmac
from django.conf import settings


def generate_license_key(order):
    """تولید کلید لایسنس امن"""
    # ترکیب اطلاعات سفارش
    data = f"{order.id}-{order.product.id}-{order.plan.id}-{order.user.id}"
    
    # تولید HMAC
    secret = settings.LICENSE_SECRET_KEY.encode()
    signature = hmac.new(secret, data.encode(), hashlib.sha256).hexdigest()[:16]
    
    # تولید UUID و ترکیب
    unique_id = str(uuid.uuid4()).replace('-', '')[:16]
    
    # فرمت نهایی: XXXX-XXXX-XXXX-XXXX
    license_key = f"{unique_id[:4]}-{unique_id[4:8]}-{signature[:4]}-{signature[4:8]}"
    
    return license_key.upper()


def hash_license_key(license_key):
    """هش کردن کلید لایسنس برای ذخیره امن"""
    return hashlib.sha256(license_key.encode()).hexdigest()


def verify_license_signature(license_key, order):
    """بررسی امضای لایسنس"""
    data = f"{order.id}-{order.product.id}-{order.plan.id}-{order.user.id}"
    secret = settings.LICENSE_SECRET_KEY.encode()
    expected_signature = hmac.new(secret, data.encode(), hashlib.sha256).hexdigest()[:16]
    
    # استخراج signature از license_key
    parts = license_key.replace('-', '')
    if len(parts) < 16:
        return False
    
    received_signature = parts[8:16]
    return hmac.compare_digest(received_signature, expected_signature[:8])

