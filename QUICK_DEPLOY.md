# راهنمای سریع استقرار روی سرور

## خلاصه مراحل

### ✅ کارهای انجام شده (قبل از کپی فایل‌ها)

تمام تنظیمات لازم انجام شده است. فایل‌های زیر آماده هستند:
- ✅ `.env.example` - الگوی متغیرهای محیطی
- ✅ `gunicorn_config.py` - تنظیمات Gunicorn
- ✅ `nginx_divar_shop.conf` - تنظیمات Nginx
- ✅ `divar_shop.service` - فایل Systemd Service
- ✅ `settings.py` - بهینه‌سازی شده برای production
- ✅ `requirements.txt` - شامل gunicorn و psycopg2

---

## مراحل استقرار روی سرور

### مرحله ۱: کپی فایل‌ها به سرور

فایل‌های پروژه را به سرور کپی کنید:
- تمام محتوای پوشه `django/` (به جز `venv/` و `__pycache__/`)
- مسیر پیشنهادی روی سرور: `/var/www/divar_shop/`

**نکته مهم:** پوشه `venv/` را کپی نکنید!

---

### مرحله ۲: نصب پکیج‌ها روی سرور

```bash
# اتصال به سرور
ssh root@212.80.29.56

# نصب پکیج‌های سیستم
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib

# رفتن به دایرکتوری پروژه
cd /var/www/divar_shop

# ایجاد محیط مجازی
python3 -m venv venv
source venv/bin/activate

# نصب وابستگی‌ها
pip install --upgrade pip
pip install -r requirements.txt
```

---

### مرحله ۳: تنظیم فایل .env

```bash
# کپی فایل نمونه
cp env_template.txt .env

# ویرایش فایل (در صورت نیاز)
nano .env
```

**مهم‌ترین تنظیمات:**
```env
SECRET_KEY=کلید-رمز-قوی-اینجا
DEBUG=False
ALLOWED_HOSTS=divarfiling.ir,www.divarfiling.ir,212.80.29.56
SITE_URL=https://divarfiling.ir

DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=divarfilingDb
DATABASE_USER=divarfilingAdmin
DATABASE_PASSWORD=رمز-دیتابیس-شما
```

**تولید SECRET_KEY:**
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

### مرحله ۴: تنظیمات Django

```bash
# ایجاد دیتابیس PostgreSQL (یک‌بار روی سرور)
sudo -u postgres psql -f scripts/setup_postgresql.sql

# اجرای migrations
python manage.py migrate

# ایجاد superuser
python manage.py createsuperuser

# جمع‌آوری فایل‌های استاتیک
python manage.py collectstatic --noinput

# ایجاد پوشه logs
mkdir -p logs
```

---

### مرحله ۵: تنظیم Gunicorn Service

```bash
# کپی فایل service
sudo cp divar_shop.service /etc/systemd/system/

# ویرایش فایل (در صورت نیاز - بررسی مسیرها)
sudo nano /etc/systemd/system/divar_shop.service

# فعال‌سازی و راه‌اندازی
sudo systemctl daemon-reload
sudo systemctl enable divar_shop
sudo systemctl start divar_shop

# بررسی وضعیت
sudo systemctl status divar_shop
```

---

### مرحله ۶: تنظیم Nginx

```bash
# کپی فایل تنظیمات
sudo cp nginx_divar_shop.conf /etc/nginx/sites-available/divar_shop

# ایجاد لینک
sudo ln -s /etc/nginx/sites-available/divar_shop /etc/nginx/sites-enabled/

# حذف تنظیمات پیش‌فرض (اختیاری)
sudo rm /etc/nginx/sites-enabled/default

# بررسی تنظیمات
sudo nginx -t

# راه‌اندازی مجدد
sudo systemctl restart nginx
```

**نکته:** در فایل `nginx_divar_shop.conf` مسیر `/var/www/divar_shop` را بررسی کنید.

---

### مرحله ۷: تنظیم فایروال

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS (اگر SSL دارید)
sudo ufw enable
```

---

### مرحله ۸: تست

1. در مرورگر به `http://212.80.29.56` بروید
2. بررسی لاگ‌ها در صورت بروز مشکل:

```bash
# لاگ Django Service
sudo journalctl -u divar_shop -f

# لاگ Nginx
sudo tail -f /var/log/nginx/error.log

# لاگ Gunicorn
tail -f /var/www/divar_shop/logs/gunicorn_error.log
```

---

## دستورات مفید

### راه‌اندازی مجدد سرویس‌ها
```bash
sudo systemctl restart divar_shop
sudo systemctl restart nginx
```

### بررسی وضعیت
```bash
sudo systemctl status divar_shop
sudo systemctl status nginx
```

### مشاهده لاگ‌ها
```bash
sudo journalctl -u divar_shop -n 50
tail -f /var/www/divar_shop/logs/django.log
```

---

## مشکلات رایج

### خطای 502 Bad Gateway
- بررسی کنید Gunicorn در حال اجرا است: `sudo systemctl status divar_shop`
- بررسی پورت 8000: `sudo netstat -tlnp | grep 8000`

### فایل‌های استاتیک نمایش داده نمی‌شوند
```bash
sudo chown -R www-data:www-data /var/www/divar_shop/staticfiles
sudo chmod -R 755 /var/www/divar_shop/staticfiles
```

### دسترسی به فایل‌های media
```bash
sudo chown -R www-data:www-data /var/www/divar_shop/media
sudo chmod -R 755 /var/www/divar_shop/media
```

---

## نکات مهم

1. ✅ حتماً `SECRET_KEY` را تغییر دهید
2. ✅ `DEBUG=False` در production
3. ✅ `ALLOWED_HOSTS` را صحیح تنظیم کنید
4. ✅ فایل `.env` را در Git commit نکنید
5. ✅ برای production حتماً از HTTPS استفاده کنید

---

برای راهنمای کامل‌تر، فایل `DEPLOYMENT.md` را مطالعه کنید.

