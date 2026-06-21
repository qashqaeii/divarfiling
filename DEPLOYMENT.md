# راهنمای استقرار Production — فایلینگ دیوار (Divar Shop)

> **نسخه سند:** 2.0  
> **پلتفرم هدف:** Ubuntu 22.04 LTS / Debian 12  
> **دامنه:** [divarfiling.ir](https://divarfiling.ir)  
> **پشته:** Django 4.2 · Gunicorn · Nginx · PostgreSQL · Redis

---

## فهرست مطالب

1. [نمای کلی معماری](#۱-نمای-کلی-معماری)
2. [پیش‌نیازها](#۲-پیش‌نیازها)
3. [چک‌لیست قبل از استقرار](#۳-چک‌لیست-قبل-از-استقرار)
4. [آماده‌سازی سرور](#۴-آماده‌سازی-سرور)
5. [انتقال کد به سرور](#۵-انتقال-کد-به-سرور)
6. [پیکربندی محیط (.env)](#۶-پیکربندی-محیط-env)
7. [دیتابیس PostgreSQL](#۷-دیتابیس-postgresql)
8. [Redis (کش و Rate Limit)](#۸-redis-کش-و-rate-limit)
9. [راه‌اندازی Django](#۹-راه‌اندازی-django)
10. [فایل نصب ربات (Setup)](#۱۰-فایل-نصب-ربات-setup)
11. [Gunicorn](#۱۱-gunicorn)
12. [Systemd Service](#۱۲-systemd-service)
13. [Nginx و SSL](#۱۳-nginx-و-ssl)
14. [فایروال](#۱۴-فایروال)
15. [تأیید استقرار](#۱۵-تأیید-استقرار)
16. [به‌روزرسانی Production](#۱۶-به‌روزرسانی-production)
17. [عملیات روزمره](#۱۷-عملیات-روزمره)
18. [عیب‌یابی](#۱۸-عیب‌یابی)
19. [چک‌لیست امنیتی](#۱۹-چک‌لیست-امنیتی)
20. [فایل‌های مرتبط](#۲۰-فایل‌های-مرتبط)
21. [مدیریت گرافیکی دیتابیس (Adminer)](#۲۱-مدیریت-گرافیکی-دیتابیس-adminer)

---

## ۱. نمای کلی معماری

```
                    ┌─────────────┐
   کاربر ─────────► │   Nginx     │  :80 / :443
                    │  (reverse   │
                    │   proxy)    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        /static/     /media/     127.0.0.1:8000
        (فایل‌های    (آپلودها)         │
         جمع‌شده)                      ▼
                              ┌─────────────┐
                              │  Gunicorn   │
                              │  (Django)   │
                              └──────┬──────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              PostgreSQL          Redis          django/files/
              (داده‌ها)      (rate limit)    (فایل نصب ZIP)
```

| لایه | نقش |
|------|-----|
| **Nginx** | SSL، سرو فایل‌های استاتیک/مدیا، پروکسی به Gunicorn |
| **Gunicorn** | اجرای WSGI Django با چند worker |
| **PostgreSQL** | ذخیره‌سازی دائمی (کاربران، سفارش‌ها، لایسنس‌ها) |
| **Redis** | کش مشترک بین workerها — محدودسازی API لایسنس |
| **django/files/** | فایل نصب ربات (`Divar-Real-Estate-Install.zip`) — منبع اصلی دانلود |

---

## ۲. پیش‌نیازها

### سرور

| مورد | حداقل | پیشنهادی |
|------|--------|----------|
| CPU | 1 vCPU | 2+ vCPU |
| RAM | 2 GB | 4 GB |
| Disk | 20 GB | 40 GB+ (فایل نصب ~250 MB) |
| OS | Ubuntu 22.04 / Debian 12 | Ubuntu 22.04 LTS |

### نرم‌افزار

- Python **3.10+**
- PostgreSQL **14+**
- Redis **6+**
- Nginx **1.18+**
- Git (اختیاری، برای deploy با pull)

### دسترسی

- SSH با کاربر دارای `sudo`
- DNS دامنه `divarfiling.ir` و `www.divarfiling.ir` → IP سرور
- Merchant ID درگاه [زیبال](https://zibal.ir)
- گواهی SSL (Let's Encrypt)

### متغیر مسیر پروژه

در تمام این سند از **`DJANGO_ROOT`** استفاده می‌شود. قبل از deploy یک مسیر ثابت انتخاب کنید:

| محیط | مسیر پیشنهادی |
|------|----------------|
| استقرار استاندارد | `/var/www/divar_shop` |
| سرور فعلی (service موجود) | `/root/Django` |

> **مهم:** مسیر `DJANGO_ROOT` باید در **هر سه** فایل یکسان باشد:  
> `divar_shop.service` · `nginx_divar_shop.conf` · `gunicorn_config.py`

---

## ۳. چک‌لیست قبل از استقرار

- [ ] DNS دامنه به IP سرور اشاره می‌کند
- [ ] `SECRET_KEY` و `LICENSE_*` کلیدهای جدید و قوی تولید شده‌اند
- [ ] `DEBUG=False` در production
- [ ] Merchant ID واقعی زیبال (نه `zibal` تست) در `.env`
- [ ] فایل `.env` در Git commit **نشده**
- [ ] فایل `files/Divar-Real-Estate-Install.zip` روی سرور قرار دارد
- [ ] پوشه `venv/` از لوکال کپی **نمی‌شود** — روی سرور ساخته می‌شود

---

## ۴. آماده‌سازی سرور

### ۴.۱ به‌روزرسانی سیستم

```bash
sudo apt update && sudo apt upgrade -y
```

### ۴.۲ نصب پکیج‌های پایه

```bash
sudo apt install -y \
  python3 python3-pip python3-venv python3-dev \
  nginx postgresql postgresql-contrib \
  redis-server \
  git curl certbot python3-certbot-nginx \
  build-essential libpq-dev
```

### ۴.۳ ایجاد کاربر و دایرکتوری (پیشنهادی)

```bash
sudo useradd -m -s /bin/bash divaruser
sudo mkdir -p /var/www/divar_shop
sudo chown divaruser:divaruser /var/www/divar_shop
```

> اگر از `/root/Django` استفاده می‌کنید، این مرحله را رد کنید.

### ۴.۴ فعال‌سازی سرویس‌های سیستمی

```bash
sudo systemctl enable --now postgresql redis-server nginx
```

---

## ۵. انتقال کد به سرور

### ۵.۱ روش Git (پیشنهادی)

```bash
cd /var/www/divar_shop
git clone <repository-url> .
# یا فقط پوشه django:
git clone <repository-url> repo && mv repo/django/* . && rm -rf repo
```

### ۵.۲ روش SCP / SFTP (از Windows)

```powershell
# PowerShell — جایگزین USER و IP
scp -r django/* user@212.80.29.56:/var/www/divar_shop/
```

### ۵.۳ فایل‌ها و پوشه‌های لازم

| انتقال | توضیح |
|--------|--------|
| ✅ تمام کد `django/` | apps، templates، static، manage.py |
| ✅ `requirements.txt` | وابستگی‌های Python |
| ✅ `gunicorn_config.py` | تنظیمات Gunicorn |
| ✅ `nginx_divar_shop.conf` | تنظیمات Nginx |
| ✅ `divar_shop.service` | واحد systemd |
| ✅ `files/Divar-Real-Estate-Install.zip` | فایل نصب ربات |
| ❌ `venv/` | روی سرور مجدداً ساخته می‌شود |
| ❌ `__pycache__/` | نیازی نیست |
| ❌ `.env` | روی سرور از قالب ساخته می‌شود |

---

## ۶. پیکربندی محیط (.env)

### ۶.۱ ایجاد فایل

```bash
cd $DJANGO_ROOT
cp .env.example .env
nano .env
```

> برای production می‌توانید از `env_template.txt` به‌عنوان پایه استفاده کنید، اما **تمام کلیدها و رمزها را حتماً بازنویسی کنید.**

### ۶.۲ تولید کلیدهای امن

```bash
source venv/bin/activate
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### ۶.۳ متغیرهای ضروری

```env
# ── Django ──
SECRET_KEY=<کلید-تصادفی-۵۰+-کاراکتر>
DEBUG=False
ALLOWED_HOSTS=divarfiling.ir,www.divarfiling.ir,212.80.29.56
SITE_URL=https://divarfiling.ir
CSRF_TRUSTED_ORIGINS=https://divarfiling.ir,https://www.divarfiling.ir

# ── PostgreSQL ──
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=divarfilingDb
DATABASE_USER=divarfilingAdmin
DATABASE_PASSWORD=<رمز-قوی>
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_CONN_MAX_AGE=600

# ── درگاه زیبال ──
ZIBAL_MERCHANT_ID=<merchant-id-واقعی>
ZIBAL_CALLBACK_URL=https://divarfiling.ir/payment/callback/

# ── لایسنس ربات دسکتاپ ──
LICENSE_SECRET_KEY=<کلید-۳۲+-کاراکتر>
LICENSE_BOT_API_KEY=<کلید-مشترک-با-اپ-دسکتاپ>
LICENSE_ALLOW_LOCAL_DEV=False

# ── Redis ──
CACHE_BACKEND=django.core.cache.backends.redis.RedisCache
CACHE_LOCATION=redis://127.0.0.1:6379/1

# ── ایمیل ──
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=mail.divarfiling.ir
EMAIL_PORT=587
EMAIL_HOST_USER=noreply@divarfiling.ir
EMAIL_HOST_PASSWORD=<رمز-smtp>
DEFAULT_FROM_EMAIL=noreply@divarfiling.ir
```

### ۶.۴ جدول مرجع متغیرها

| متغیر | الزامی | توضیح |
|-------|--------|--------|
| `SECRET_KEY` | ✅ | کلید رمز Django |
| `DEBUG` | ✅ | همیشه `False` در production |
| `ALLOWED_HOSTS` | ✅ | دامنه + IP سرور |
| `ZIBAL_MERCHANT_ID` | ✅ | بدون آن پرداخت غیرفعال است |
| `LICENSE_SECRET_KEY` | ✅ | امضای کلید لایسنس |
| `LICENSE_BOT_API_KEY` | ✅ | احراز هویت API ربات |
| `CACHE_BACKEND` | ⚠️ | بدون Redis، rate limit بین workerها کار نمی‌کند |
| `GOFTINO_WIDGET_ID` | ❌ | ویجت چت آنلاین (اختیاری) |

---

## ۷. دیتابیس PostgreSQL

### ۷.۱ ایجاد کاربر و دیتابیس

```bash
sudo -u postgres psql <<'EOF'
CREATE USER divarfilingAdmin WITH PASSWORD 'YOUR_DATABASE_PASSWORD';
CREATE DATABASE divarfilingDb OWNER divarfilingAdmin;
GRANT ALL PRIVILEGES ON DATABASE divarfilingDb TO divarfilingAdmin;
EOF
```

یا از اسکریپت آماده:

```bash
# ابتدا رمز را در scripts/setup_postgresql.sql جایگزین کنید
sudo -u postgres psql -f scripts/setup_postgresql.sql
```

### ۷.۲ دسترسی Schema (PostgreSQL 15+)

```bash
sudo -u postgres psql -d divarfilingDb <<'EOF'
GRANT ALL ON SCHEMA public TO divarfilingAdmin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO divarfilingAdmin;
EOF
```

### ۷.۳ تست اتصال

```bash
psql -h localhost -U divarfilingAdmin -d divarfilingDb -c "SELECT 1;"
```

---

## ۸. Redis (کش و Rate Limit)

Redis برای محدودسازی درخواست‌های API لایسنس بین workerهای Gunicorn ضروری است.

```bash
# بررسی وضعیت
sudo systemctl status redis-server
redis-cli ping   # باید PONG برگرداند
```

نصب client Python (در venv):

```bash
pip install redis
```

---

## ۹. راه‌اندازی Django

```bash
cd $DJANGO_ROOT

# محیط مجازی
python3 -m venv venv
source venv/bin/activate

# وابستگی‌ها
pip install --upgrade pip
pip install -r requirements.txt
pip install redis

# migrations
python manage.py migrate

# superuser
python manage.py createsuperuser

# فایل‌های استاتیک
python manage.py collectstatic --noinput

# پوشه لاگ
mkdir -p logs
chmod 755 logs

# همگام‌سازی محصول و پلن‌های لایسنس
python manage.py sync_bot_product
```

### دستورات مدیریتی مفید

| دستور | کاربرد |
|-------|--------|
| `sync_bot_product` | ایجاد/به‌روزرسانی محصول اصلی و پلن‌ها |
| `import_product` | وارد کردن محصول نسخه حرفه‌ای (legacy) |
| `createsuperuser` | دسترسی پنل ادمین `/admin/` |

---

## ۱۰. فایل نصب ربات (Setup)

پس از پرداخت موفق، کاربر فایل **`Divar-Real-Estate-Install.zip`** را دانلود می‌کند.

### مسیر منبع

```
$DJANGO_ROOT/files/Divar-Real-Estate-Install.zip
```

سیستم دانلود **اولویت** را به این فایل می‌دهد (نه نسخه قدیمی در `media/products/`).

### استقرار فایل

```bash
mkdir -p $DJANGO_ROOT/files
# کپی از build لوکال:
scp Divar-Real-Estate-Install.zip user@server:$DJANGO_ROOT/files/

# بررسی حجم (باید چند صد مگابایت باشد، نه چند بایت)
ls -lh $DJANGO_ROOT/files/Divar-Real-Estate-Install.zip
```

### به‌روزرسانی نسخه جدید installer

```bash
# 1. فایل جدید را جایگزین کنید
cp /path/to/new/Divar-Real-Estate-Install.zip $DJANGO_ROOT/files/

# 2. (اختیاری) همگام‌سازی رکورد محصول در دیتابیس
source venv/bin/activate
python manage.py sync_bot_product

# 3. restart سرویس
sudo systemctl restart divar_shop
```

> **نکته:** با منطق فعلی دانلود، فقط جایگزینی فایل در `files/` کافی است — restart برای اطمینان از workerهای تازه توصیه می‌شود.

---

## ۱۱. Gunicorn

### ۱۱.۱ تنظیمات (`gunicorn_config.py`)

| پارامتر | مقدار پیش‌فرض | توضیح |
|---------|---------------|--------|
| `bind` | `127.0.0.1:8000` | فقط localhost — Nginx پروکسی می‌کند |
| `workers` | `CPU × 2 + 1` | تعداد worker |
| `timeout` | `30` | ثانیه |
| `accesslog` | `logs/gunicorn_access.log` | |
| `errorlog` | `logs/gunicorn_error.log` | |

### ۱۱.۲ تست دستی (قبل از systemd)

```bash
cd $DJANGO_ROOT
source venv/bin/activate
gunicorn --config gunicorn_config.py divar_shop.wsgi:application
```

در ترمینال دیگر:

```bash
curl -I http://127.0.0.1:8000/
```

با `Ctrl+C` متوقف کنید.

---

## ۱۲. Systemd Service

### ۱۲.۱ نصب واحد سرویس

```bash
sudo cp divar_shop.service /etc/systemd/system/
sudo nano /etc/systemd/system/divar_shop.service
```

**فیلدهایی که باید با `DJANGO_ROOT` هماهنگ شوند:**

```ini
[Service]
User=divaruser          # یا root — بسته به سیاست سرور
Group=divaruser
WorkingDirectory=/var/www/divar_shop
EnvironmentFile=/var/www/divar_shop/.env
Environment="PATH=/var/www/divar_shop/venv/bin"
ExecStart=/var/www/divar_shop/venv/bin/gunicorn \
    --config /var/www/divar_shop/gunicorn_config.py \
    divar_shop.wsgi:application
Restart=always
RestartSec=3
```

### ۱۲.۲ فعال‌سازی

```bash
sudo systemctl daemon-reload
sudo systemctl enable divar_shop
sudo systemctl start divar_shop
sudo systemctl status divar_shop
```

### ۱۲.۳ مشاهده لاگ

```bash
sudo journalctl -u divar_shop -f --no-pager
```

---

## ۱۳. Nginx و SSL

### ۱۳.۱ نصب تنظیمات

```bash
sudo cp nginx_divar_shop.conf /etc/nginx/sites-available/divar_shop
sudo nano /etc/nginx/sites-available/divar_shop
```

**مسیرهایی که باید ویرایش شوند** (جستجو: `/var/www/divar_shop`):

- `alias` برای `/static/` → `$DJANGO_ROOT/staticfiles/`
- `alias` برای `/media/` → `$DJANGO_ROOT/media/`
- `server_name` برای IP سرور

```bash
sudo ln -sf /etc/nginx/sites-available/divar_shop /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

### ۱۳.۲ گواهی SSL (Let's Encrypt)

```bash
sudo certbot --nginx -d divarfiling.ir -d www.divarfiling.ir
```

Certbot مسیرهای SSL را در `nginx_divar_shop.conf` تنظیم می‌کند:

```
/etc/letsencrypt/live/divarfiling.ir/fullchain.pem
/etc/letsencrypt/live/divarfiling.ir/privkey.pem
```

### ۱۳.۳ تمدید خودکار

```bash
sudo certbot renew --dry-run
```

### ۱۳.۴ رفتار دسترسی

| آدرس | رفتار |
|------|--------|
| `https://divarfiling.ir` | سایت اصلی با SSL |
| `http://divarfiling.ir` | redirect به HTTPS |
| `http://212.80.29.56` | HTTP مستقیم (بدون redirect — برای تست/دسترسی IP) |

---

## ۱۴. فایروال

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'    # 80 + 443
sudo ufw enable
sudo ufw status
```

> پورت **8000** را باز **نکنید** — Gunicorn فقط روی localhost گوش می‌دهد.

---

## ۱۵. تأیید استقرار

### چک‌لیست عملکردی

| # | تست | دستور / URL | نتیجه مورد انتظار |
|---|-----|-------------|-------------------|
| 1 | Gunicorn | `systemctl status divar_shop` | `active (running)` |
| 2 | Nginx | `systemctl status nginx` | `active (running)` |
| 3 | PostgreSQL | `psql -c "SELECT 1;"` | `1` |
| 4 | Redis | `redis-cli ping` | `PONG` |
| 5 | صفحه اصلی | `curl -I https://divarfiling.ir` | `HTTP/2 200` |
| 6 | استاتیک | باز کردن `/static/` در مرورگر | CSS/JS بدون 404 |
| 7 | ادمین | `https://divarfiling.ir/admin/` | صفحه ورود |
| 8 | فایل نصب | `ls -lh files/Divar-Real-Estate-Install.zip` | > 100 MB |
| 9 | پرداخت | تست sandbox زیبال | redirect و callback |
| 10 | دانلود | پس از پرداخت تست | `Divar-Real-Estate-Install.zip` |

### بررسی لاگ‌ها

```bash
# Django
tail -f $DJANGO_ROOT/logs/django.log

# Gunicorn
tail -f $DJANGO_ROOT/logs/gunicorn_error.log

# Nginx
sudo tail -f /var/log/nginx/error.log
```

---

## ۱۶. به‌روزرسانی Production

```bash
cd $DJANGO_ROOT
source venv/bin/activate

# 1. دریافت کد جدید
git pull origin main

# 2. وابستگی‌ها
pip install -r requirements.txt

# 3. migrations
python manage.py migrate

# 4. استاتیک
python manage.py collectstatic --noinput

# 5. (در صورت تغییر محصول/installer)
python manage.py sync_bot_product

# 6. restart
sudo systemctl restart divar_shop
sudo systemctl reload nginx
```

### فقط به‌روزرسانی installer

```bash
scp Divar-Real-Estate-Install.zip user@server:$DJANGO_ROOT/files/
sudo systemctl restart divar_shop
```

---

## ۱۷. عملیات روزمره

```bash
# وضعیت سرویس‌ها
sudo systemctl status divar_shop nginx postgresql redis-server

# restart
sudo systemctl restart divar_shop
sudo systemctl reload nginx

# لاگ زنده
sudo journalctl -u divar_shop -f

# backup دیتابیس
pg_dump -U divarfilingAdmin -d divarfilingDb -F c -f backup_$(date +%Y%m%d).dump

# restore
pg_restore -U divarfilingAdmin -d divarfilingDb backup_YYYYMMDD.dump
```

---

## ۱۸. عیب‌یابی

### سرویس Django اجرا نمی‌شود

```bash
sudo journalctl -u divar_shop -n 100 --no-pager
ls -la $DJANGO_ROOT
cat $DJANGO_ROOT/.env | grep -v PASSWORD | grep -v SECRET
```

**علت‌های رایج:** مسیر اشتباه در service · `.env` ناقص · migration اجرا نشده · پورت 8000 اشغال

### Nginx خطای 502 Bad Gateway

```bash
sudo systemctl status divar_shop
ss -tlnp | grep 8000
curl -I http://127.0.0.1:8000/
```

**علت‌های رایج:** Gunicorn down · timeout · خطای import در Django

### فایل‌های استاتیک 404

```bash
python manage.py collectstatic --noinput
ls -la $DJANGO_ROOT/staticfiles/
# مسیر alias در nginx را با STATIC_ROOT مقایسه کنید
```

### CSRF / Redirect Loop

- `CSRF_TRUSTED_ORIGINS` باید با `https://` شروع شود
- `SITE_URL` باید `https://divarfiling.ir` باشد
- header `X-Forwarded-Proto` در nginx تنظیم شده باشد

### پرداخت کار نمی‌کند

- `ZIBAL_MERCHANT_ID` را در `.env` بررسی کنید
- Callback URL در پنل زیبال: `https://divarfiling.ir/payment/callback/`
- لاگ: `grep -i zibal $DJANGO_ROOT/logs/django.log`

### دانلود فایل قدیمی یا خالی

```bash
ls -lh $DJANGO_ROOT/files/Divar-Real-Estate-Install.zip
# باید فایل کامل (~250MB) باشد، نه placeholder
python manage.py sync_bot_product
sudo systemctl restart divar_shop
```

### Rate limit لایسنس بین workerها کار نمی‌کند

```bash
redis-cli ping
grep CACHE_BACKEND $DJANGO_ROOT/.env
pip show redis
```

---

## ۱۹. چک‌لیست امنیتی

| # | مورد | وضعیت |
|---|------|--------|
| 1 | `DEBUG=False` | ☐ |
| 2 | `SECRET_KEY` منحصربه‌فرد و خارج از Git | ☐ |
| 3 | `LICENSE_SECRET_KEY` و `LICENSE_BOT_API_KEY` قوی | ☐ |
| 4 | `ALLOWED_HOSTS` فقط دامنه/IP مجاز | ☐ |
| 5 | HTTPS فعال با HSTS | ☐ |
| 6 | پورت 8000 فقط localhost | ☐ |
| 7 | `.env` permission `600` | ☐ |
| 8 | PostgreSQL رمز قوی | ☐ |
| 9 | UFW فعال | ☐ |
| 10 | backup دوره‌ای دیتابیس | ☐ |
| 11 | Adminer فقط localhost + Basic Auth (+ IP محدود) | ☐ |

```bash
chmod 600 $DJANGO_ROOT/.env
```

---

## ۲۰. فایل‌های مرتبط

| فایل | نقش |
|------|-----|
| `.env.example` | قالب متغیرهای محیط (بدون secret واقعی) |
| `env_template.txt` | قالب production — **commit نکنید با secret واقعی** |
| `gunicorn_config.py` | worker، bind، logging |
| `nginx_divar_shop.conf` | reverse proxy، SSL، static/media |
| `divar_shop.service` | واحد systemd |
| `scripts/setup_postgresql.sql` | اسکریپت ایجاد DB |
| `requirements.txt` | وابستگی‌های Python |
| `files/Divar-Real-Estate-Install.zip` | فایل نصب ربات |
| `shop/services/downloads.py` | منطق دانلود پس از پرداخت |
| `INSTALL.md` | راهنمای نصب توسعه |
| `QUICK_DEPLOY.md` | خلاصه deploy سریع |
| `docker-compose.db-admin.yml` | Adminer — رابط وب مدیریت PostgreSQL |
| `nginx_db_admin.conf` | Nginx + SSL + Basic Auth برای Adminer |

---

## ۲۱. مدیریت گرافیکی دیتابیس (Adminer)

> **توجه:** این پروژه از **PostgreSQL** استفاده می‌کند، نه MySQL.  
> **phpMyAdmin** فقط با MySQL/MariaDB کار می‌کند.  
> معادل مناسب برای PostgreSQL: **[Adminer](https://www.adminer.org/)** (رابط شبیه phpMyAdmin) یا **pgAdmin**.

### گزینه‌های موجود

| ابزار | مناسب برای | توضیح |
|-------|------------|--------|
| **Django Admin** | `/admin/` | مدیریت مدل‌ها — از قبل فعال است |
| **Adminer** | SQL خام، جداول، export | پیشنهادی — سبک و شبیه phpMyAdmin |
| **pgAdmin** | کار پیشرفته PostgreSQL | سنگین‌تر، برای DBA |

### ۲۱.۱ نصب Docker (یک‌بار)

```bash
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
```

### ۲۱.۲ اجرای Adminer

```bash
cd $DJANGO_ROOT
docker compose -f docker-compose.db-admin.yml up -d

# بررسی
docker ps | grep divar_db_admin
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080   # باید 200 باشد
```

Adminer فقط روی **`127.0.0.1:8080`** bind می‌شود — از اینترنت مستقیم در دسترس نیست.

### ۲۱.۳ ورود به Adminer

| فیلد | مقدار |
|------|--------|
| **System** | PostgreSQL |
| **Server** | `host.docker.internal` |
| **Username** | `divarfilingAdmin` (از `.env`) |
| **Password** | `DATABASE_PASSWORD` (از `.env`) |
| **Database** | `divarfilingDb` |

### ۲۱.۴ دسترسی از مرورگر (با Nginx + SSL)

برای مدیریت از راه دور، زیردامنه امن با Basic Auth:

```bash
# 1. DNS: db.divarfiling.ir → IP سرور

# 2. رمز Basic Auth
sudo apt install -y apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd_dbadmin admin_db

# 3. کپی و فعال‌سازی Nginx
sudo cp nginx_db_admin.conf /etc/nginx/sites-available/db_admin
sudo ln -s /etc/nginx/sites-available/db_admin /etc/nginx/sites-enabled/
sudo certbot --nginx -d db.divarfiling.ir
sudo nginx -t && sudo systemctl reload nginx
```

سپس: `https://db.divarfiling.ir` → ورود Basic Auth → صفحه Adminer → اطلاعات PostgreSQL بالا.

> **امنیت:** پورت 8080 را در UFW باز **نکنید**. فقط Nginx (443) در معرض اینترنت باشد.

### ۲۱.۵ دسترسی محلی با SSH Tunnel (بدون Nginx)

از کامپیوتر شخصی:

```bash
ssh -L 8080:127.0.0.1:8080 root@212.80.29.56
```

سپس در مرورگر: `http://127.0.0.1:8080`

### ۲۱.۶ توقف / به‌روزرسانی

```bash
cd $DJANGO_ROOT
docker compose -f docker-compose.db-admin.yml down
docker compose -f docker-compose.db-admin.yml pull
docker compose -f docker-compose.db-admin.yml up -d
```

### ۲۱.۷ توسعه محلی (Windows)

اگر `.env` شما SQLite دارد (`DATABASE_ENGINE=sqlite3`)، Adminer مستقیماً به SQLite وصل نمی‌شود. گزینه‌ها:

- **Django Admin:** `http://127.0.0.1:8000/admin/`
- **DB Browser for SQLite:** [sqlitebrowser.org](https://sqlitebrowser.org/)
- **PostgreSQL محلی:** در `.env` به PostgreSQL سوئیچ کنید و Adminer را با Docker Desktop اجرا کنید

---

## پشتیبانی

در صورت بروز مشکل:

1. لاگ‌های بخش [۱۸. عیب‌یابی](#۱۸-عیب‌یابی) را بررسی کنید
2. خروجی `python manage.py check --deploy` را اجرا کنید
3. با تیم توسعه تماس بگیرید و **لاگ + زمان خطا** را ارسال کنید

```bash
cd $DJANGO_ROOT && source venv/bin/activate
python manage.py check --deploy
```
