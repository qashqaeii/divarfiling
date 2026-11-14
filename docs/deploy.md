cd ~/DivarFiling
source venv/bin/activate
git pull origin main
python manage.py migrate
python manage.py sync_public_knowledge
python manage.py collectstatic --noinput
sudo systemctl restart divar_shop

# بازیابی تمدید/صدور ناقص پس از پرداخت (cron هر ~۱۰ دقیقه)
# python manage.py reconcile_order_fulfillments --limit 100

# همگام‌سازی نشست فایلینگ با خطوط استخراج (cron هر ~۵ دقیقه، کنار run_acquisition_automation)
# python manage.py reconcile_extraction_lines

# به‌روزرسانی places-web.json (جلوگیری از خطای district is not valid در API دیوار)
# cd ~/DivarFiling-repo  # یا مسیر مونورپو با scripts/update_places_web.py
# python scripts/update_places_web.py
# cp config/places-web.json /root/config/places-web.json   # مسیر پیش‌فرض phone-detector روی سرور
