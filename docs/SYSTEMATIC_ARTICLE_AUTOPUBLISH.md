# Systematic Article Auto Publish — Production

انتشار خودکار روزانه مقالات تحلیل بازار (حداکثر ۱ در روز، QA + AI Polish).

## Command

```bash
cd /path/to/django   # e.g. /root/DivarFiling
source venv/bin/activate
python manage.py run_systematic_article_autopublish
```

| Flag | Effect |
|------|--------|
| `--dry-run` | کاندید + تصمیم — بدون ساخت |
| `--shadow` | ساخت + پولیش + QA — بدون Publish |
| `--force` | نادیده `is_enabled` و `publish_time` (shadow_mode همچنان از config) |
| `--recover-stuck` | فقط بازیابی runهای `generating` / `ai_polishing` قدیمی |
| `--no-recover` | pipeline بدون recover ابتدایی |

## Deploy steps (code only — تنظیمات prod را دستی تغییر دهید)

```bash
git pull origin main
python manage.py migrate blog
sudo systemctl daemon-reload
sudo systemctl enable --now divar-systematic-article-autopublish.timer
```

Copy unit files from `django/deploy/`:

```bash
sudo cp deploy/divar-systematic-article-autopublish.service /etc/systemd/system/
sudo cp deploy/divar-systematic-article-autopublish.timer /etc/systemd/system/
```

Adjust `WorkingDirectory`, `User`, and log path in the service file for your server.

## Recommended rollout

1. **Shadow یک هفته:** `shadow_mode=True`, `is_enabled=True` — timer با `--shadow` یا config shadow (بدون live).
2. **Dry run دستی:** `python manage.py run_systematic_article_autopublish --dry-run`
3. **Shadow کامل:** `python manage.py run_systematic_article_autopublish --shadow --force`
4. **Live:** `shadow_mode=False` در پنل — timer همان `run_systematic_article_autopublish` بدون فلگ.

## Stuck runs

اجراهای فعال بیش از ۶ ساعت بدون `updated_at` به `needs_review` منتقل می‌شوند (`recover_stuck_autopublish_runs`).

دستی:

```bash
python manage.py run_systematic_article_autopublish --recover-stuck
```

## Timezone

`publish_time` روی config و `OnCalendar` تایمر باید با `TIME_ZONE=Asia/Tehran` هم‌خوان باشند.

## AI Polish

از زنجیره `ai_workspace.providers` استفاده می‌کند. تنظیم اختیاری:

```python
AI_FEATURE_GENERATION = {
    'market_article_polish': {'temperature': 0.25, 'max_tokens': 8000},
}
```

## Admin UI

`/accounts/admin-panel/blog/systematic/autopublish/` — وضعیت، Shadow/Live، اجرای بعدی، پولیش AI، تاریخچه مراحل.
