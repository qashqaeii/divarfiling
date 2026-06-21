# رفع مشکل دسترسی (403 Forbidden)

## مشکل
خطای 403 Forbidden برای فایل‌های استاتیک به دلیل مشکل دسترسی است.

## راه‌حل

### ۱. بررسی دسترسی‌های فعلی

```bash
# بررسی دسترسی‌های پوشه staticfiles
ls -la /root/Django/staticfiles/

# بررسی دسترسی‌های پوشه media
ls -la /root/Django/media/

# بررسی دسترسی‌های پوشه اصلی
ls -la /root/Django/ | head -20
```

### ۲. تنظیم دسترسی‌های صحیح

```bash
# تنظیم دسترسی‌های staticfiles
sudo chmod -R 755 /root/Django/staticfiles
sudo chown -R root:root /root/Django/staticfiles

# تنظیم دسترسی‌های media
sudo chmod -R 755 /root/Django/media
sudo chown -R root:root /root/Django/media

# تنظیم دسترسی‌های پوشه اصلی (اگر نیاز بود)
sudo chmod 755 /root/Django
```

### ۳. بررسی دسترسی‌های Nginx

Nginx باید بتواند به فایل‌ها دسترسی داشته باشد. اگر از کاربر `www-data` استفاده می‌کنید:

```bash
# اگر Nginx با کاربر www-data اجرا می‌شود
sudo chown -R www-data:www-data /root/Django/staticfiles
sudo chown -R www-data:www-data /root/Django/media
sudo chmod -R 755 /root/Django/staticfiles
sudo chmod -R 755 /root/Django/media
```

اما چون ما از کاربر `root` استفاده می‌کنیم، باید مطمئن شویم که Nginx می‌تواند به پوشه `/root` دسترسی داشته باشد.

### ۴. راه‌حل بهتر: تغییر مالکیت به www-data

```bash
# تغییر مالکیت فایل‌های استاتیک و مدیا به www-data
sudo chown -R www-data:www-data /root/Django/staticfiles
sudo chown -R www-data:www-data /root/Django/media

# تنظیم دسترسی‌ها
sudo chmod -R 755 /root/Django/staticfiles
sudo chmod -R 755 /root/Django/media

# راه‌اندازی مجدد Nginx
sudo systemctl restart nginx
```

### ۵. یا راه‌حل جایگزین: تغییر دسترسی پوشه root

```bash
# اگر می‌خواهید از کاربر root استفاده کنید
sudo chmod 755 /root
sudo chmod 755 /root/Django
sudo chmod -R 755 /root/Django/staticfiles
sudo chmod -R 755 /root/Django/media
```

---

## تست بعد از تغییرات

```bash
# تست فایل CSS
curl -I http://212.80.29.56/static/css/main.css

# تست فایل JS
curl -I http://212.80.29.56/static/js/main.js

# بررسی لاگ Nginx
sudo tail -f /var/log/nginx/error.log
```

---

## بررسی SELinux (اگر فعال است)

اگر SELinux فعال است، ممکن است نیاز به تنظیمات اضافی باشد:

```bash
# بررسی وضعیت SELinux
getenforce

# اگر فعال است، می‌توانید موقتاً غیرفعال کنید (توصیه نمی‌شود)
# یا context را تنظیم کنید
```

---

## نکات مهم

1. Nginx معمولاً با کاربر `www-data` اجرا می‌شود
2. فایل‌های استاتیک باید قابل خواندن توسط Nginx باشند
3. پوشه‌های والد نیز باید دسترسی مناسب داشته باشند

