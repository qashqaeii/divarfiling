# PostgreSQL محلی (ویندوز) — کپی دیتای Production

هدف: Django فقط به **PostgreSQL روی همین ویندوز** وصل شود؛ هیچ تغییری روی سرور Production نیست.

## پیش‌نیاز

- PostgreSQL 16 نصب شده، پورت `5432`
- فایل بکاپ: `D:\MYROBOTS\DIVAR-SCRAPER\backups\divarfiling\divarfiling_local.dump`
- نام دیتابیس در dump: `divarfilingdb`

## ۱. Restore (یک‌بار یا هنگام تازه‌سازی دیتا)

PowerShell (با دسترسی Administrator لازم نیست):

```powershell
cd D:\MYROBOTS\DIVAR-SCRAPER\backups\divarfiling
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\restore-local.ps1
```

اسکریپت:

- نقش محلی `divarfilingadmin` با رمزی که خودتان انتخاب می‌کنید می‌سازد
- dump را با `--no-owner --no-acl` در `divarfilingdb` بازیابی می‌کند
- فقط به `127.0.0.1` وصل می‌شود

برای **پاک‌سازی کامل و restore دوباره** (فقط لوکال):

```sql
-- در psql با کاربر postgres:
DROP DATABASE IF EXISTS divarfilingdb;
CREATE DATABASE divarfilingdb OWNER postgres;
```

سپس اسکریپت را دوباره اجرا کنید.

## ۲. تنظیم `django/.env`

روی ویندوز از قالب لوکال استفاده کنید، نه `env_template.txt` (Production):

```powershell
cd D:\MYROBOTS\DIVAR-SCRAPER\django
copy env.local.example .env
```

فقط `DATABASE_PASSWORD` را با رمز کاربر `divarfiling_local` پر کنید. secretهای Production را در `.env` لوکال نگذارید.

## ۳. اجرای Django

```powershell
cd D:\MYROBOTS\DIVAR-SCRAPER\django
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py check
python manage.py runserver
```

`migrate` فقط اسکیمای لوکال را با کد فعلی هم‌تراز می‌کند؛ به Production وصل نیست.

## ۴. جلوگیری از اثر روی Production

- `DATABASE_HOST` فقط `127.0.0.1` / `localhost`
- درگاه پرداخت، SMS واقعی، و ایمیل SMTP Production را در لوکال استفاده نکنید
- cron / `reconcile_order_fulfillments` و workerهای acquisition روی لوکال اجرا نشوند مگر عمداً برای تست

## عیب‌یابی

- **رمز postgres**: همان رمزی که در نصب PostgreSQL برای superuser `postgres` تعیین کردید
- **pg_restore خطا 1**: اغلب هشدار است؛ اگر `auth_user` شمارش داشت، ادامه دهید
- **اتصال Django**: `python manage.py dbshell` سپس `\dt` برای اطمینان از جداول
