# سیستم فروش ربات دیوار

سیستم فروشگاهی مبتنی بر Django برای عرضه و فروش نسخه‌های مختلف ربات دیوار.

## ویژگی‌ها

- ✅ طراحی RTL و فارسی با تم Glassmorphism
- ✅ سیستم پرداخت آنلاین با درگاه زیبال
- ✅ سیستم لایسنس یک‌سیستمی با فعال‌سازی سخت‌افزاری
- ✅ سیستم همکاری در فروش (Affiliate)
- ✅ داشبورد کاربر و مدیر
- ✅ سیستم بلاگ و مقالات
- ✅ API برای فعال‌سازی لایسنس

## نصب و راه‌اندازی

### پیش‌نیازها

- Python 3.9 یا بالاتر
- pip
- virtualenv (پیشنهادی)

### مراحل نصب

1. ایجاد محیط مجازی:

```bash
python -m venv venv
```

2. فعال‌سازی محیط مجازی:

**Windows (CMD):**
```cmd
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

**ویندوز لوکال (Locally on Windows):**
اگر از محیط گرافیکی یا فایل اکسپلورر روی ویندوز استفاده می‌کنید، می‌توانید CMD یا PowerShell را در همان پوشه پروژه باز کرده و یکی از دستورات بالا را وارد کنید.

3. نصب وابستگی‌ها:

```bash
pip install -r requirements.txt
```

4. اجرای migrations:

```bash
python manage.py migrate
```

5. ایجاد کاربر مدیر:

```bash
python manage.py createsuperuser
```

6. اجرای سرور توسعه:

```bash
python manage.py runserver
```
وقتی Robot.zip واقعی را جایگزین کردی:

cd django
python manage.py sync_bot_product
## تنظیمات

### متغیرهای محیطی

Production: `cp env_template.txt .env` — Dev: `cp .env.example .env`

```env
DATABASE_NAME=divarfilingDb
DATABASE_USER=divarfilingAdmin
SITE_URL=https://divarfiling.ir
ZIBAL_CALLBACK_URL=https://divarfiling.ir/payment/callback/
EMAIL_HOST=mail.divarfiling.ir
DEFAULT_FROM_EMAIL=noreply@divarfiling.ir
```

### تنظیمات زیبال

1. وارد پنل زیبال شوید
2. Merchant ID خود را دریافت کنید
3. Callback URL: `https://divarfiling.ir/payment/callback/`

## ساختار پروژه

```
django/
├── divar_shop/          # تنظیمات اصلی پروژه
├── accounts/            # مدیریت کاربران
├── shop/                # فروشگاه و محصولات
├── licenses/            # سیستم لایسنس
├── affiliates/          # همکاری در فروش
├── blog/                # بلاگ و مقالات
├── templates/           # قالب‌های HTML
├── static/              # فایل‌های استاتیک (CSS, JS)
└── media/               # فایل‌های رسانه (آپلود شده)
```

## استفاده از API لایسنس

### فعال‌سازی لایسنس

```bash
POST /api/licenses/activate/
Content-Type: application/json

{
    "license_key": "XXXX-XXXX-XXXX-XXXX",
    "hardware_fingerprint": "machine-id-or-fingerprint"
}
```

### اعتبارسنجی لایسنس

```bash
POST /api/licenses/validate/
Content-Type: application/json

{
    "license_key": "XXXX-XXXX-XXXX-XXXX",
    "hardware_fingerprint": "machine-id-or-fingerprint"
}
```

## مستندات

برای اطلاعات بیشتر به فایل `django-info.txt` مراجعه کنید.

## پشتیبانی

برای پشتیبانی و گزارش مشکل، با ما تماس بگیرید.

## مجوز

تمامی حقوق محفوظ است.

