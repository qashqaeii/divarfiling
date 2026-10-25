# تالار گفتگو (Community Forum)

## خلاصه

تالار گفتگوی عمومی فایلینگ دیوار یک فضای گفتگوی Real-time برای تمام کاربران احرازهویت‌شده و فعال است، **بدون نیاز به لایسنس**.

مسیر UI: `/workspace/forum/`

Feature flag: `COMMUNITY_FORUM_ENABLED` (پیش‌فرض: `false`)

بدون نصب `channels`، `runserver` HTTP عادی کار می‌کند؛ برای WebSocket حتماً `pip install -r requirements.txt` در همان venv سرور را اجرا کنید.

## معماری

- **PostgreSQL**: منبع اصلی پیام‌ها
- **Django REST** (JSON + CSRF): ارسال، تاریخچه، ویرایش، حذف، واکنش، گزارش، جستجو
- **Django Channels + Redis**: انتشار رویداد به WebSocket
- **سرویس ASGI جدا**: `divar_shop.asgi_ws:application` (Daphne)

HTTP اصلی سایت همچنان از Gunicorn + `divar_shop.asgi` / WSGI استفاده می‌کند.

## متغیرهای محیط

| متغیر | توضیح |
|--------|--------|
| `COMMUNITY_FORUM_ENABLED` | فعال‌سازی تالار |
| `FORUM_REDIS_URL` | Redis برای Channel Layer (مثلاً `redis://127.0.0.1:6379/1`) |
| `FORUM_RATE_LIMIT_CACHE_BACKEND` | کش مشترک Rate Limit (در production Redis) |
| `COMMUNITY_FORUM_RETENTION_DAYS` | پیش‌فرض ۳۰ |

## REST API (نیاز به Session)

پایه: `/workspace/forum/api/`

| مسیر | عمل |
|------|-----|
| `bootstrap/` | تنظیمات اولیه، اطلاعیه، unread |
| `messages/` | GET تاریخچه؛ POST ارسال |
| `messages/<id>/` | PATCH ویرایش؛ DELETE حذف |
| `messages/<id>/reactions/` | POST واکنش |
| `messages/<id>/report/` | POST گزارش |
| `read/` | POST به‌روزرسانی cursor خواندن |
| `search/?q=` | جستجو |
| `profile/` | نام نمایشی / خوش‌آمد |
| `unread/` | شمارنده |

## WebSocket

- مسیر: `/ws/forum/`
- احراز هویت: Session Django
- رویدادها: `message.new`, `message.updated`, `message.deleted`, `reaction.updated`
- Heartbeat: `{ "type": "ping" }` → `pong`

## نگهداری

```bash
python manage.py purge_forum_messages
```

Cron پیشنهادی: هر ساعت.

## استقرار WebSocket

```bash
daphne -b 127.0.0.1 -p 8001 divar_shop.asgi_ws:application
```

Nginx (نمونه):

```nginx
location /ws/ {
    proxy_pass http://127.0.0.1:8001;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
```

## Rollback

1. `COMMUNITY_FORUM_ENABLED=false`
2. restart Gunicorn
3. توقف سرویس Daphne (HTTP اصلی بدون تغییر می‌ماند)

## محدودیت نسخه اول

- فقط پیام متنی
- بدون لینک خارجی در متن
- بدون پیام خصوصی / فایل

## مجوز مدیریت

`community_forum.can_moderate_forum` — پنل: `/accounts/admin-panel/forum/`
