# راهنمای نصب و راه‌اندازی

## پیش‌نیازها

- Python 3.9 یا بالاتر
- pip (مدیر بسته Python)
- virtualenv (پیشنهادی)

## مراحل نصب

### 1. ایجاد محیط مجازی

```bash
python -m venv venv
```

### 2. فعال‌سازی محیط مجازی

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 3. نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

### 4. تنظیم متغیرهای محیطی

فایل `.env` را از قالب production بسازید:

```bash
cp env_template.txt .env
```

برای توسعه محلی می‌توانید `DEBUG=True` و SQLite استفاده کنید. مقادیر production:

| متغیر | مقدار |
|--------|--------|
| `DATABASE_NAME` | `divarfilingDb` |
| `DATABASE_USER` | `divarfilingAdmin` |
| `SITE_URL` | `https://divarfiling.ir` |
| `EMAIL_HOST` | `mail.divarfiling.ir` |

**تولید SECRET_KEY:**
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### 5. اجرای Migrations

```bash
python manage.py migrate
```

### 6. ایجاد کاربر مدیر

```bash
python manage.py createsuperuser
```

### 7. جمع‌آوری فایل‌های استاتیک

```bash
python manage.py collectstatic --noinput
```

### 8. اجرای سرور توسعه

```bash
python manage.py runserver
```

سپس به آدرس `http://localhost:8000` بروید.

## تنظیمات زیبال

1. وارد پنل زیبال شوید: https://zibal.ir
2. Merchant ID خود را دریافت کنید
3. Callback URL را در پنل زیبال تنظیم کنید: `http://yourdomain.com/payment/callback/`
4. Merchant ID را در فایل `.env` قرار دهید

## ساختار دیتابیس

پس از اجرای migrations، جداول زیر ایجاد می‌شوند:

- `accounts_user` - کاربران
- `accounts_userprofile` - پروفایل کاربران
- `shop_product` - محصولات
- `shop_licenseplan` - پلن‌های لایسنس
- `shop_order` - سفارش‌ها
- `shop_transaction` - تراکنش‌های پرداخت
- `licenses_license` - لایسنس‌ها
- `licenses_licenseactivation` - فعال‌سازی‌های لایسنس
- `affiliates_affiliate` - مشاوران فروش
- `affiliates_affiliatesale` - فروش‌های افیلیت
- `blog_post` - مقالات

## ایجاد محصول نمونه

1. وارد پنل ادمین شوید: `http://localhost:8000/admin`
2. به بخش Products بروید
3. یک محصول جدید ایجاد کنید
4. پلن‌های قیمت را برای محصول اضافه کنید
5. تصاویر و رسانه‌ها را آپلود کنید

## تست سیستم پرداخت

برای تست در محیط توسعه:

1. از Merchant ID تست زیبال استفاده کنید
2. از کارت‌های تست زیبال استفاده کنید
3. در محیط production حتماً از Merchant ID واقعی استفاده کنید

## مشکلات رایج

### خطای Import

اگر با خطای import مواجه شدید:
```bash
pip install --upgrade -r requirements.txt
```

### خطای Database

اگر با خطای database مواجه شدید:
```bash
python manage.py migrate --run-syncdb
```

### خطای Static Files

اگر فایل‌های استاتیک نمایش داده نمی‌شوند:
```bash
python manage.py collectstatic
```

## پشتیبانی

برای پشتیبانی و گزارش مشکل، با تیم توسعه تماس بگیرید.

