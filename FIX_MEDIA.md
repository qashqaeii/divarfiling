# رفع مشکل نمایش فایل‌های مدیا (عکس‌ها و فیلم‌ها)

## مشکل
در production (DEBUG=False)، Django فایل‌های مدیا را سرو نمی‌دهد. این کار باید توسط Nginx انجام شود.

## راه‌حل

### ۱. بررسی وجود فایل‌های مدیا

```bash
# بررسی محتوای پوشه media
ls -la /root/Django/media/

# بررسی فایل‌های محصولات
ls -la /root/Django/media/products/

# بررسی فایل‌های avatars
ls -la /root/Django/media/avatars/
```

### ۲. تنظیم دسترسی‌های پوشه media

```bash
# تغییر مالکیت به www-data
sudo chown -R www-data:www-data /root/Django/media

# تنظیم دسترسی‌ها
sudo chmod -R 755 /root/Django/media

# بررسی دسترسی‌ها
ls -la /root/Django/media/
```

### ۳. بررسی تنظیمات Nginx برای media

```bash
# بررسی مسیر media در Nginx
sudo cat /etc/nginx/sites-available/divar_shop | grep -A 5 "location /media"
```

باید به این صورت باشد:
```nginx
location /media/ {
    alias /root/Django/media/;
    expires 7d;
    add_header Cache-Control "public";
}
```

### ۴. راه‌اندازی مجدد Nginx

```bash
sudo systemctl restart nginx
```

### ۵. تست فایل‌های مدیا

```bash
# تست یک فایل مدیا (مثال)
curl -I http://212.80.29.56/media/products/example.jpg

# یا اگر فایل خاصی دارید
ls /root/Django/media/products/
curl -I http://212.80.29.56/media/products/[نام-فایل]
```

### ۶. بررسی لاگ Nginx

```bash
# بررسی خطاهای مربوط به media
sudo tail -f /var/log/nginx/error.log | grep media
```

---

## بررسی مسیر فایل‌های مدیا در دیتابیس

اگر فایل‌های مدیا در دیتابیس ذخیره شده‌اند، بررسی کنید که مسیرها درست باشند:

```bash
# بررسی دیتابیس (اگر از SQLite استفاده می‌کنید)
sqlite3 /root/Django/db.sqlite3 "SELECT image, video FROM shop_product LIMIT 5;"
```

---

## نکات مهم

1. در production، Django فایل‌های مدیا را سرو نمی‌دهد
2. Nginx باید مسیر `/media/` را به `/root/Django/media/` map کند
3. دسترسی‌های فایل‌های مدیا باید برای Nginx (www-data) قابل خواندن باشد
4. پوشه‌های والد نیز باید دسترسی مناسب داشته باشند

---

## اگر فایل‌های مدیا وجود ندارند

اگر فایل‌های مدیا از سیستم محلی کپی نشده‌اند:

```bash
# از سیستم محلی، فایل‌های media را به سرور کپی کنید
# یا از طریق admin Django فایل‌های جدید آپلود کنید
```

