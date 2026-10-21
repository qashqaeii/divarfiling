# Systematic Article Auto Publish — Production

انتشار خودکار روزانه مقالات تحلیل بازار (حداکثر ۱ در روز، AI Polish + QA).

## پیش‌نیاز Deploy (کد فقط — Production config را دستی تغییر دهید)

1. Pull آخرین `main`
2. **Migration** (مسیر وابسته به وضعیت سرور — بخش Migration Conflict)
3. `collectstatic` در صورت تغییر استاتیک
4. Restart `divar_shop` (Gunicorn)
5. **Timer را تا پایان Shadow فعال نکنید**

```bash
cd /path/to/project   # e.g. /root/DivarFiling
source venv/bin/activate
git pull origin main
python manage.py showmigrations blog | tail -5
python manage.py migrate blog
sudo systemctl restart divar_shop
```

## Migration conflict (سرور vs GitHub)

| محیط | وضعیت |
|------|--------|
| **سرور (اعمال‌شده)** | `0007_rename_blog_autopub_run_date_status_idx_blog_system_run_dat_7f48f5_idx` |
| **ریپو (جدید)** | همان `0007` (rename) + `0008_autopublish_polish_and_steps` |

**سروری که قبلاً 0007 rename دارد:**

```bash
python manage.py migrate blog 0007_rename_blog_autopub_run_date_status_idx_blog_system_run_dat_7f48f5_idx  # اگر قبلاً applied است: skip
python manage.py migrate blog   # فقط 0008 اعمال می‌شود
```

**سرور تازه (فقط تا 0006):**

```bash
python manage.py migrate blog   # 0007 سپس 0008
```

**هرگز** migration اعمال‌شده روی سرور را حذف یا squash نکنید. اگر نام فایل 0007 روی سرور با ریپو یکی است، Django آن را applied می‌شناسد.

## Command

```bash
python manage.py run_systematic_article_autopublish
```

| Flag | Effect |
|------|--------|
| `--dry-run` | کاندید + تصمیم — بدون ساخت |
| `--shadow` | ساخت + پولیش + QA — بدون Publish |
| `--force` | نادیده `is_enabled` و `publish_time` |
| `--recover-stuck` | فقط بازیابی runهای فعال قدیمی |
| `--no-recover` | بدون recover ابتدایی |

## Systemd Timer (زمان‌بندی — مستقل از TIME_ZONE جنگو)

فایل‌ها: `deploy/divar-systematic-article-autopublish.service` + `.timer`

```ini
[Timer]
OnCalendar=*-*-* 08:30:00
Timezone=Asia/Tehran
Persistent=true
```

**نصب (پس از تأیید Shadow — الان enable نکنید):**

```bash
sudo cp deploy/divar-systematic-article-autopublish.service /etc/systemd/system/
sudo cp deploy/divar-systematic-article-autopublish.timer /etc/systemd/system/
# مسیر WorkingDirectory و venv در .service را اصلاح کنید
sudo systemctl daemon-reload
# sudo systemctl enable --now divar-systematic-article-autopublish.timer   # فقط بعد از Go-Live
```

**بررسی تقویم روی سرور Linux:**

```bash
systemd-analyze calendar "*-*-* 08:30:00" --timezone=Asia/Tehran
systemctl list-timers divar-systematic-article-autopublish.timer
```

روی Windows/WSL بدون systemd این دستور در دسترس نیست.

`publish_time` در پنل Django فقط برای **اجرای دستی/command** است؛ trigger اصلی production = `Timezone=Asia/Tehran` در unit.

## Rollback

1. **کد:** `git checkout <previous-tag>` + restart Gunicorn
2. **Timer:** `sudo systemctl disable --now divar-systematic-article-autopublish.timer`
3. **Migration:** فیلدهای 0008 را برگردانید فقط اگر واقعاً لازم است — ترجیحاً forward-fix؛ `migrate blog 0007` فقط با تصمیم DBA (داده `step_history` از دست می‌رود)
4. **Run گیرکرده:** `python manage.py run_systematic_article_autopublish --recover-stuck`

## Rollout

1. `migrate blog` + restart اپ
2. `--recover-stuck` برای run قدیمی `generating`
3. چند بار `--shadow --force`
4. Timer را **بعد از** خاموش کردن `shadow_mode` در پنل enable کنید (نه قبل)

## AI Polish

- فقط **segmentهای متنی** به AI می‌رود؛ markup (src/href/class/id/table/chart) ثابت
- شکست AI → `ai_polish_failed` — **بدون انتشار** نسخه بدون پولیش
- QA کامل پس از پولیش

## Admin

`/accounts/admin-panel/blog/systematic/autopublish/`
