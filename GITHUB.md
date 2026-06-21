# راه‌اندازی GitHub (مخزن خصوصی)

## یک‌بار: ساخت repo روی GitHub

1. برو به [github.com/new](https://github.com/new)
2. نام: `divarfiling` (یا هر نامی که می‌خواهی)
3. **Private** را انتخاب کن
4. تیک «Add README» را **نزن** (از قبل README داریم)
5. Create repository

## یک‌بار: اتصال لوکال به GitHub

```powershell
cd D:\MYROBOTS\DIVAR-SCRAPER\django

# جایگزین USERNAME و REPO_NAME
git remote add origin https://github.com/USERNAME/REPO_NAME.git
git branch -M main
git push -u origin main
```

ورود: GitHub از **Personal Access Token** به‌جای پسورد استفاده می‌کند.
ساخت توکن: GitHub → Settings → Developer settings → Personal access tokens → Generate (scope: `repo`).

## روزمره: بعد از هر تغییر

```powershell
cd D:\MYROBOTS\DIVAR-SCRAPER\django
git add .
git status          # حتماً .env نباشد!
git commit -m "توضیح کوتاه تغییر"
git push
```

## Deploy روی سرور (بعد از push)

```bash
ssh root@62.60.204.73
cd /root/DivarFiling
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart divar_shop
```

یا از لوکال: `.\deploy.ps1`

## فایل‌هایی که هرگز در Git نیستند

- `.env` — رمزها و کلیدهای production
- `env_template.txt` — نسخهٔ واقعی تنظیمات سرور
- `venv/` — محیط مجازی
- `db.sqlite3` — دیتابیس لوکال
- `staticfiles/` — خروجی collectstatic
- `media/` — آپلود کاربران
- `files/*.zip` — فایل نصب ربات (با scp به سرور بفرست)
