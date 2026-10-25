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
| `COMMUNITY_FORUM_ENABLED` | فعال‌سازی تالار (سوئیچ اصلی) |
| `COMMUNITY_FORUM_ROLLOUT_MODE` | `none` (پیش‌فرض)، `allowlist`، `all` |
| `COMMUNITY_FORUM_ALLOWED_USER_IDS` | شناسه کاربران مجاز (با کاما) برای `allowlist` |
| `FORUM_REDIS_URL` | Redis مشترک: Channel Layer، Rate Limit (Lua)، و `forum_shared` (ban و قفل fallback) |
| `COMMUNITY_FORUM_RATE_LIMIT_REQUIRE_REDIS` | `true` = بدون Redis ارسال fail-closed |
| `FORUM_SHARED_CACHE_BACKEND` | در صورت نبود `FORUM_REDIS_URL`، backend جدا برای ban (production: Redis) |
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
| `sync/?anchor_id=&since=` | ویرایش/حذف پیام‌های با `id ≤ anchor` پس از قطع WS |

## WebSocket

- مسیر: `/ws/forum/`
- احراز هویت: Session Django
- رویدادها: `message.new`, `message.updated`, `message.deleted`, `reaction.updated`
- Heartbeat: `{ "type": "ping" }` → `pong`
- Payload broadcast **بدون** `is_mine` — کلاینت با `sender_public_id` مالکیت را تشخیص می‌دهد.
- اتصال در صورت ban خواندن (`can_read=false`) رد می‌شود؛ رویداد `session.revoked` اتصال را می‌بندد.

## Rate limit

- `settings.FORUM_REDIS_URL` از env خوانده می‌شود (نه متغیر داخلی تنها).
- با `FORUM_REDIS_URL`، aliasهای `forum_rate_limit` و `forum_shared` روی Redis تنظیم می‌شوند.
- اگر تالار فعال و `DEBUG=false` و Redis خالی باشد، ارسال fail-closed است.
- اختیاری: `COMMUNITY_FORUM_RATE_LIMIT_REQUIRE_REDIS=true` همیشه fail-closed بدون Redis.

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
