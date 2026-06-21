# راهنمای حل مشکل Cache استایل‌ها

## مشکل
گاهی استایل‌های قدیمی لود می‌شوند به دلیل cache مرورگر یا سرور.

## راه‌حل‌ها

### 1. افزایش نسخه CSS (انجام شده)
نسخه CSS از `v=3.5` به `v=4.0` افزایش یافت. این باعث می‌شود مرورگر فایل جدید را دانلود کند.

### 2. اجرای collectstatic
بعد از هر تغییر در فایل‌های استاتیک، باید دستور زیر را اجرا کنید:

```bash
cd django
source venv/bin/activate
python manage.py collectstatic --noinput
```

### 3. پاک کردن Cache مرورگر
برای کاربران:
- **Chrome/Edge**: `Ctrl + Shift + Delete` → Clear browsing data → Cached images and files
- **Firefox**: `Ctrl + Shift + Delete` → Cache
- **Safari**: `Cmd + Option + E`

یا استفاده از Hard Refresh:
- **Windows/Linux**: `Ctrl + F5` یا `Ctrl + Shift + R`
- **Mac**: `Cmd + Shift + R`

### 4. پاک کردن Cache Nginx (اگر از Nginx استفاده می‌کنید)
```bash
# ریستارت Nginx
sudo systemctl restart nginx

# یا پاک کردن cache Nginx
sudo rm -rf /var/cache/nginx/*
sudo systemctl reload nginx
```

### 5. بررسی فایل‌های Static
مطمئن شوید که فایل‌های جدید در `staticfiles` کپی شده‌اند:
```bash
ls -la django/staticfiles/css/main.css
```

### 6. افزودن Meta Tag برای جلوگیری از Cache (اختیاری)
می‌توانید در `base.html` این meta tag را اضافه کنید:
```html
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
```

**توجه**: این روش برای development مناسب است، اما در production توصیه نمی‌شود.

### 7. استفاده از Versioning خودکار (پیشنهادی)
می‌توانید از timestamp یا hash فایل برای versioning استفاده کنید:

```python
# در settings.py
import hashlib
import os

def get_file_hash(filepath):
    """محاسبه hash فایل"""
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()[:8]

# در template
{% load static %}
<link rel="stylesheet" href="{% static 'css/main.css' %}?v={{ 'css/main.css'|file_hash }}">
```

## نکات مهم
1. همیشه بعد از تغییر CSS، نسخه را افزایش دهید
2. در production، `collectstatic` را بعد از هر deploy اجرا کنید
3. برای development، می‌توانید از `DEBUG=True` استفاده کنید که cache را غیرفعال می‌کند

## دستورات سریع
```bash
# 1. افزایش نسخه در base.html (انجام شده)
# 2. اجرای collectstatic
cd django && source venv/bin/activate && python manage.py collectstatic --noinput

# 3. ریستارت سرور (اگر از systemd استفاده می‌کنید)
sudo systemctl restart divar_shop

# 4. ریستارت Nginx
sudo systemctl restart nginx
```

