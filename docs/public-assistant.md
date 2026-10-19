# دستیار عمومی AI و دانشنامه

## فعال‌سازی

در `.env` سرور:

```env
PUBLIC_ASSISTANT_ENABLED=true
PUBLIC_ASSISTANT_TRUSTED_PROXY_IPS=127.0.0.1
```

اختیاری:

```env
PUBLIC_ASSISTANT_RATE_LIMIT_PER_HOUR=40
PUBLIC_ASSISTANT_SESSION_RATE_LIMIT_PER_HOUR=25
PUBLIC_ASSISTANT_SESSION_CREATE_LIMIT_PER_HOUR=12
```

Providerهای AI همان `ARVAN_AI_*` / `GEMINI_*` / `OPENROUTER_*` موجود هستند.

## Rate limit و IP در Production

### Nginx + Gunicorn

درخواست به Django با `REMOTE_ADDR=127.0.0.1` (یا IP داخلی Nginx) می‌رسد. **فقط** در این حالت `X-Forwarded-For` خوانده می‌شود.

- `PUBLIC_ASSISTANT_TRUSTED_PROXY_IPS` باید IPهایی باشد که **مستقیماً** به Gunicorn وصل می‌شوند (معمولاً `127.0.0.1`).
- با `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`، IP واقعی کلاینت در **انتهای** زنجیره قرار می‌گیرد؛ منطق سرور آخرین IP را برای rate limit استفاده می‌کند (جلوگیری از تزریق هدر جعلی در ابتدای زنجیره).
- اگر کلاینت مستقیماً به Gunicorn وصل شود (بدون Nginx)، هدر `X-Forwarded-For` **نادیده** گرفته می‌شود.

**بررسی سریع پس از استقرار** (از سرور، با کوکی/CSRF واقعی یا در shell Django):

```python
from django.test import RequestFactory
from public_assistant.services.rate_limit import client_ip
req = RequestFactory().get('/', REMOTE_ADDR='127.0.0.1', HTTP_X_FORWARDED_FOR='9.9.9.9, 1.2.3.4')
assert client_ip(req) == '1.2.3.4'  # آخرین مقدار، نه 9.9.9.9
```

از مرورگر: چند بار پشت‌سرهم «گفتگوی جدید» بدون کوکی تا سقف `PUBLIC_ASSISTANT_SESSION_CREATE_LIMIT_PER_HOUR` — باید پاسخ **429** بگیرید نه 500.

### چند Worker (Gunicorn)

Rate limit روی `django.core.cache` است. با **چند worker**، backend باید **مشترک** باشد (مثلاً Redis همان `CACHES` پروژه).

- `LocMemCache` فقط برای توسعه تک‌پروسه معتبر است — در production rate limit بین workerها یکسان نیست.
- **بررسی:** در `settings` مقدار `CACHES['default']['BACKEND']` را ببینید؛ باید Redis/Memcached باشد. دو درخواست پشت‌سرهم از همان IP باید شمارنده مشترک داشته باشند (مثلاً پس از رسیدن به سقف، 429).

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
