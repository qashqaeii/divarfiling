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
| `--resume-market-run UUID` | ادامه پولиш/QA از پیش‌نمایش موجود (بدون ساخت نقشه) |
| `--resume-autopublish-run UUID` | همان لاگ AutoPublish قبلی (اختیاری) |

### Resume پس از `ai_polish_failed` (مثال پونک)

```bash
python manage.py run_systematic_article_autopublish \
  --shadow --force \
  --resume-market-run 57c4c9e2-45fc-41cc-91d8-f139b8e152e4 \
  --resume-autopublish-run 7e3eb5c7-e7b1-40c3-8f4e-98c1d63a7c84
```

پیشرفت پولیش در `MarketArticleRun.chart_assets.autopublish_polish_state` ذخیره می‌شود؛ دسته‌های تکمیل‌شده دوباره به AI نمی‌روند.

### AI Polish

- پاسخ JSON: `json_mode` + repair محدود (trailing comma، استخراج `{...}`)
- `JSONDecodeError` → `AIPolishJsonError` (recoverable + retry با backoff)
- دسته‌های کوچک متن (حداکثر ۵ segment / ~۲۸۰۰ کاراکتر)
- SEO جدا از بدنه
- خروجی نامعتبر **هرگز** در `content_html` ذخیره نمی‌شود

### نقشه‌ها (موضوع بعدی)

Overpass timeout و کاشی ماهواره‌ای می‌تواند ساخت را ~۴ دقیقه کند؛ فعلاً با `MARKET_ARTICLE_SKIP_*` در تست کنترل می‌شود. برای production: timeout/cached fallback و ثبت صریح در QA اگر نقشه ضروری نبود — در فاز بعد.

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
- قرارداد JSON: SEO `{"title","excerpt"}`؛ batch `{"texts":[{"id","text"}]}` — آرایه خام یا کلیدهای `segments/items` نرمال می‌شوند
- دسته‌های کوچک (۲ segment / ~۱۲۰۰ کاراکتر)؛ پیشرفت در `chart_assets.autopublish_polish_state` برای Resume
- پس از چند شکست JSON در یک دسته، **identity fallback** (متن اصلی همان segment) با schema معتبر
- خطای عددی در segment → retry تک‌segment؛ سپس **numeric_safety_fallback** (بازگشت متن اصلی) با `segment_id` و توکن در `batch_logs`
- مقایسه اعداد با نرمال‌سازی ارقام فارسی/انگلیسی و جداکننده‌ها؛ رد عدد/قیمت ساختگی جدید
- گزارش: `polish_change_ratio`, `fallback_ratio`, `numeric_safety_fallback_count`
- Shield عددی `⟦DFN:n⟧` قبل از LLM؛ Resume با `completed_segment_ids` + `batch_plan_version`
- شمارش: `polished_segments`, `unchanged_segments`, `identity_fallback_count`, `numeric_safety_fallback_count`
- Providerهای `403` / `geo_blocked` / `auth_error` در همان دسته دوباره صدا زده نمی‌شوند
- شکست نهایی → `ai_polish_failed` + `ai_polish_report.batch_logs` — **بدون انتشار** نسخه بدون پولیش
- QA کامل پس از پولیش

## Admin

`/accounts/admin-panel/blog/systematic/autopublish/`
