# بررسی نهایی استقرار

## ✅ وضعیت فعلی

- ✅ سرویس divar_shop: **active (running)**
- ✅ Gunicorn: **در حال اجرا روی پورت 8000**
- ✅ Nginx: **active (running)**
- ✅ فایروال: **فعال**

---

## بررسی‌های نهایی

### ۱. بررسی دسترسی به سایت

در مرورگر به آدرس زیر بروید:
```
http://212.80.29.56
```

### ۲. بررسی فایل‌های استاتیک

```bash
# بررسی وجود فایل‌های استاتیک
ls -la /root/Django/staticfiles/

# بررسی دسترسی‌ها
sudo chmod -R 755 /root/Django/staticfiles
```

### ۳. بررسی فایل‌های مدیا

```bash
# بررسی وجود فایل‌های مدیا
ls -la /root/Django/media/

# بررسی دسترسی‌ها
sudo chmod -R 755 /root/Django/media
```

### ۴. بررسی لاگ‌های Nginx

```bash
# لاگ خطاها
sudo tail -f /var/log/nginx/error.log

# لاگ دسترسی‌ها
sudo tail -f /var/log/nginx/access.log
```

### ۵. بررسی لاگ‌های Django

```bash
# لاگ Gunicorn
tail -f /root/Django/logs/gunicorn_error.log
tail -f /root/Django/logs/gunicorn_access.log

# لاگ Django
tail -f /root/Django/logs/django.log
```

---

## تست عملکرد

### تست از طریق curl

```bash
# تست صفحه اصلی
curl -I http://212.80.29.56

# تست فایل‌های استاتیک
curl -I http://212.80.29.56/static/css/main.css

# تست فایل‌های مدیا
curl -I http://212.80.29.56/media/
```

---

## مشکلات احتمالی و راه‌حل

### مشکل: صفحه 502 Bad Gateway

**علت:** Nginx نمی‌تواند به Gunicorn متصل شود.

**راه‌حل:**
```bash
# بررسی وضعیت Gunicorn
sudo systemctl status divar_shop

# بررسی پورت 8000
sudo netstat -tlnp | grep 8000

# راه‌اندازی مجدد
sudo systemctl restart divar_shop
```

### مشکل: فایل‌های استاتیک نمایش داده نمی‌شوند

**راه‌حل:**
```bash
# بررسی مسیر در تنظیمات Nginx
sudo cat /etc/nginx/sites-available/divar_shop | grep static

# بررسی دسترسی‌ها
sudo chmod -R 755 /root/Django/staticfiles
sudo chown -R root:root /root/Django/staticfiles

# راه‌اندازی مجدد Nginx
sudo systemctl restart nginx
```

### مشکل: خطای 403 Forbidden

**راه‌حل:**
```bash
# بررسی دسترسی‌های پوشه
ls -la /root/Django/

# تغییر دسترسی‌ها
sudo chmod -R 755 /root/Django
```

### مشکل: خطای 500 Internal Server Error

**راه‌حل:**
```bash
# بررسی لاگ‌های Django
tail -50 /root/Django/logs/django.log

# بررسی لاگ Gunicorn
tail -50 /root/Django/logs/gunicorn_error.log

# بررسی تنظیمات .env
cat /root/Django/.env
```

---

## دستورات مفید برای نگهداری

### راه‌اندازی مجدد سرویس‌ها

```bash
# راه‌اندازی مجدد Django
sudo systemctl restart divar_shop

# راه‌اندازی مجدد Nginx
sudo systemctl restart nginx

# راه‌اندازی مجدد هر دو
sudo systemctl restart divar_shop nginx
```

### مشاهده وضعیت

```bash
# وضعیت Django
sudo systemctl status divar_shop

# وضعیت Nginx
sudo systemctl status nginx

# وضعیت فایروال
sudo ufw status
```

### مشاهده لاگ‌های زنده

```bash
# لاگ Systemd
sudo journalctl -u divar_shop -f

# لاگ Nginx
sudo tail -f /var/log/nginx/error.log
```

---

## به‌روزرسانی پروژه

```bash
cd /root/Django
source venv/bin/activate

# نصب وابستگی‌های جدید
pip install -r requirements.txt

# اجرای migrations
python manage.py migrate

# جمع‌آوری فایل‌های استاتیک
python manage.py collectstatic --noinput

# راه‌اندازی مجدد
sudo systemctl restart divar_shop
```

---

## نکات امنیتی

1. ✅ حتماً `SECRET_KEY` را در `.env` تغییر داده‌اید
2. ✅ `DEBUG=False` در production
3. ✅ `ALLOWED_HOSTS` شامل IP سرور است
4. ⚠️ برای production حتماً از HTTPS استفاده کنید (بعداً می‌توانید SSL اضافه کنید)

---

## بعد از استقرار موفق

1. **ایجاد Superuser** (اگر هنوز ایجاد نکرده‌اید):
   ```bash
   python manage.py createsuperuser
   ```

2. **تنظیم SSL** (توصیه می‌شود):
   - استفاده از Let's Encrypt با Certbot
   - فعال‌سازی بخش HTTPS در `nginx_divar_shop.conf`

3. **پشتیبان‌گیری منظم**:
   ```bash
   python manage.py dumpdata > backup_$(date +%Y%m%d).json
   ```

---

## موفقیت! 🎉

اگر همه چیز درست کار می‌کند، سایت شما در دسترس است:
**http://212.80.29.56**

