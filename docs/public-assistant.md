# دستیار عمومی AI و دانشنامه

## فعال‌سازی

در `.env` سرور:

```env
PUBLIC_ASSISTANT_ENABLED=true
```

اختیاری:

```env
PUBLIC_ASSISTANT_RATE_LIMIT_PER_HOUR=40
PUBLIC_ASSISTANT_SESSION_RATE_LIMIT_PER_HOUR=25
```

Providerهای AI همان `ARVAN_AI_*` / `GEMINI_*` / `OPENROUTER_*` موجود هستند.

## استقرار

```bash
cd ~/DivarFiling
source venv/bin/activate
git pull origin main
python manage.py migrate
python manage.py sync_public_knowledge
python manage.py collectstatic --noinput
sudo systemctl restart divar_shop
```

## به‌روزرسانی دانشنامه

1. فایل‌های `public_assistant/knowledge/articles/*.md` را ویرایش کنید (یا از `article_seed.py` + `build_markdown.py`).
2. `python manage.py sync_public_knowledge`
3. `--dry-run` برای اعتبارسنجی بدون نوشتن در DB

## محدوده

- ویجت روی `templates/base.html` (صفحات عمومی mk-public)
- غیرفعال روی `/workspace/`, `/admin/`, `/api/`, `/payment/`, ورود/ثبت‌نام

## تست

```bash
python manage.py test public_assistant
```
