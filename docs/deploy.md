cd ~/DivarFiling
source venv/bin/activate
git pull origin main
python manage.py migrate
python manage.py sync_public_knowledge
python manage.py collectstatic --noinput
sudo systemctl restart divar_shop

## استوری صفحهٔ خانه (CSS/JS)

Nginx برای `/static/` هدر `Cache-Control: public, immutable` (۳۰ روز) می‌فرستد؛ مرورگر با **همان** `?v=` فایل قدیمی را نگه می‌دارد.

پس از هر تغییر در `static/css/home-story*.css` یا `static/js/df-home-story.js`:

1. در `templates/shop/home.html` پارامتر `?v=` همان فایل‌ها را **یک عدد بالا ببرید** و commit کنید.
2. روی سرور حتماً `collectstatic --noinput` (نه فقط restart).
3. برای اطمینان: اندازهٔ فایل روی سرور با لوکال یکی باشد، مثلاً  
   `wc -c staticfiles/css/home-story-file-chapter.css` ≈ `static/css/home-story-file-chapter.css`

اگر UI لوکال درست و production خراب است ولی HTML همان `?v=` را نشان می‌دهد، تقریباً همیشه **collectstatic اجرا نشده** یا کش immutable با bump نسخه refresh نشده است.

# تالار گفتگو (WebSocket — پس از تنظیم Redis و Nginx)
# COMMUNITY_FORUM_ENABLED=true در .env
# sudo systemctl restart divar_forum_ws
# Cron: 0 * * * * python manage.py purge_forum_messages

جزئیات: docs/community_forum.md
