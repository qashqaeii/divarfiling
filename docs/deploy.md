cd ~/DivarFiling
source venv/bin/activate
git pull origin main
python manage.py migrate
python manage.py sync_public_knowledge
python manage.py collectstatic --noinput
sudo systemctl restart divar_shop

# بازیابی تمدید/صدور ناقص پس از پرداخت (cron هر ~۱۰ دقیقه)
# python manage.py reconcile_order_fulfillments --limit 100
