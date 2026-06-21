# مراحل بعدی استقرار

## وضعیت فعلی ✅
- ✅ پکیج‌ها نصب شدند
- ✅ فایل .env ایجاد شد
- ✅ Migrations اجرا شد
- ✅ فایل‌های استاتیک جمع‌آوری شدند
- ✅ پوشه logs ایجاد شد

---

## مرحله ۱: تکمیل تنظیمات فایل .env

فایل `.env` را ویرایش کنید و مقادیر زیر را تنظیم کنید:

```bash
nano .env
```

**مهم: `SECRET_KEY` را حتماً تغییر دهید!**

برای تولید SECRET_KEY جدید:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

مثال فایل `.env` (یا `cp env_template.txt .env`):
```env
SECRET_KEY=کلید-تولید-شده-در-بالا
DEBUG=False
ALLOWED_HOSTS=divarfiling.ir,www.divarfiling.ir,212.80.29.56
SITE_URL=https://divarfiling.ir
CSRF_TRUSTED_ORIGINS=https://divarfiling.ir,https://www.divarfiling.ir

DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=divarfilingDb
DATABASE_USER=divarfilingAdmin
DATABASE_PASSWORD=رمز-دیتابیس-شما

ZIBAL_MERCHANT_ID=کد-مرچنت-زیبال-شما
ZIBAL_CALLBACK_URL=https://divarfiling.ir/payment/callback/

LICENSE_SECRET_KEY=کلید-رمز-لایسنس-شما
LICENSE_BOT_API_KEY=کلید-API-ربات-دسکتاپ

EMAIL_HOST=mail.divarfiling.ir
EMAIL_PORT=587
EMAIL_HOST_USER=noreply@divarfiling.ir
EMAIL_HOST_PASSWORD=رمز-SMTP-شما
DEFAULT_FROM_EMAIL=noreply@divarfiling.ir
```

---

## مرحله ۲: تست Gunicorn

قبل از تنظیم systemd service، Gunicorn را به صورت دستی تست کنید:

```bash
# اطمینان از فعال بودن venv
source venv/bin/activate

# تست Gunicorn
gunicorn --config gunicorn_config.py divar_shop.wsgi:application
```

اگر بدون خطا اجرا شد، با `Ctrl+C` متوقف کنید.

---

## مرحله ۳: تنظیم Systemd Service

```bash
# کپی فایل service
sudo cp divar_shop.service /etc/systemd/system/

# بررسی محتوای فایل (مسیرها باید /root/Django باشند)
cat /etc/systemd/system/divar_shop.service

# بارگذاری مجدد systemd
sudo systemctl daemon-reload

# فعال‌سازی سرویس (اجرای خودکار در بوت)
sudo systemctl enable divar_shop

# راه‌اندازی سرویس
sudo systemctl start divar_shop

# بررسی وضعیت
sudo systemctl status divar_shop
```

اگر خطایی وجود داشت، لاگ را بررسی کنید:
```bash
sudo journalctl -u divar_shop -n 50
```

---

## مرحله ۴: نصب و تنظیم Nginx

### ۴.۱ نصب Nginx (اگر نصب نشده)

```bash
sudo apt update
sudo apt install -y nginx
```

### ۴.۲ کپی فایل تنظیمات

```bash
sudo cp nginx_divar_shop.conf /etc/nginx/sites-available/divar_shop
```

### ۴.۳ ایجاد لینک سمبلیک

```bash
sudo ln -s /etc/nginx/sites-available/divar_shop /etc/nginx/sites-enabled/
```

### ۴.۴ حذف تنظیمات پیش‌فرض (اختیاری)

```bash
sudo rm /etc/nginx/sites-enabled/default
```

### ۴.۵ بررسی تنظیمات

```bash
sudo nginx -t
```

اگر خطایی نشان داد، بررسی کنید:
- مسیر `/root/Django/staticfiles/` وجود دارد
- مسیر `/root/Django/media/` وجود دارد

### ۴.۶ راه‌اندازی Nginx

```bash
sudo systemctl restart nginx
sudo systemctl status nginx
```

---

## مرحله ۵: تنظیم فایروال

```bash
# بررسی وضعیت فایروال
sudo ufw status

# باز کردن پورت‌های لازم
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS (اگر SSL دارید)

# فعال‌سازی فایروال (اگر فعال نیست)
sudo ufw enable
```

---

## مرحله ۶: تست نهایی

### ۶.۱ بررسی سرویس‌ها

```bash
# بررسی Gunicorn
sudo systemctl status divar_shop

# بررسی Nginx
sudo systemctl status nginx

# بررسی پورت 8000 (Gunicorn باید روی این پورت باشد)
sudo netstat -tlnp | grep 8000
```

### ۶.۲ تست در مرورگر

به آدرس `http://212.80.29.56` بروید.

### ۶.۳ بررسی لاگ‌ها در صورت مشکل

```bash
# لاگ Systemd Service
sudo journalctl -u divar_shop -f

# لاگ Nginx
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# لاگ Gunicorn
tail -f /root/Django/logs/gunicorn_error.log
tail -f /root/Django/logs/gunicorn_access.log

# لاگ Django
tail -f /root/Django/logs/django.log
```

---

## دستورات مفید

### راه‌اندازی مجدد سرویس‌ها

```bash
# راه‌اندازی مجدد Django
sudo systemctl restart divar_shop

# راه‌اندازی مجدد Nginx
sudo systemctl restart nginx

# راه‌اندازی مجدد هر دو
sudo systemctl restart divar_shop nginx
```

### توقف سرویس‌ها

```bash
sudo systemctl stop divar_shop
sudo systemctl stop nginx
```

### مشاهده لاگ‌های زنده

```bash
sudo journalctl -u divar_shop -f
```

---

## مشکلات رایج و راه‌حل

### خطای 502 Bad Gateway

**علت:** Gunicorn در حال اجرا نیست یا به پورت 8000 دسترسی ندارد.

**راه‌حل:**
```bash
# بررسی وضعیت
sudo systemctl status divar_shop

# بررسی پورت
sudo netstat -tlnp | grep 8000

# راه‌اندازی مجدد
sudo systemctl restart divar_shop
```

### فایل‌های استاتیک نمایش داده نمی‌شوند

**راه‌حل:**
```bash
# بررسی وجود فایل‌ها
ls -la /root/Django/staticfiles/

# بررسی دسترسی‌ها
sudo chmod -R 755 /root/Django/staticfiles
```

### خطای Permission Denied

**راه‌حل:**
```bash
# بررسی دسترسی‌های پوشه
ls -la /root/Django/

# اگر نیاز بود، دسترسی‌ها را تغییر دهید
chmod -R 755 /root/Django
```

### خطای ModuleNotFoundError

**راه‌حل:**
```bash
# اطمینان از فعال بودن venv
source venv/bin/activate

# نصب مجدد وابستگی‌ها
pip install -r requirements.txt
```

---

## نکات مهم

1. ✅ حتماً `SECRET_KEY` را در فایل `.env` تغییر دهید
2. ✅ `DEBUG=False` در production
3. ✅ بررسی کنید که `ALLOWED_HOSTS` شامل IP سرور باشد
4. ✅ برای production حتماً از HTTPS استفاده کنید (بعداً می‌توانید SSL اضافه کنید)

---

## بعد از استقرار موفق

1. ایجاد superuser (اگر هنوز ایجاد نکرده‌اید):
   ```bash
   python manage.py createsuperuser
   ```

2. تنظیم SSL (اختیاری اما توصیه می‌شود):
   - استفاده از Let's Encrypt با Certbot
   - فعال‌سازی بخش HTTPS در `nginx_divar_shop.conf`

3. پشتیبان‌گیری منظم از دیتابیس:
   ```bash
   python manage.py dumpdata > backup.json
   ```

