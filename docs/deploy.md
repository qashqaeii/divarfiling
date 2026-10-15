cd ~/DivarFiling
source venv/bin/activate
git pull origin main
# سیاست AI دو سطحی (پیش‌فرض): AI_LICENSED_UNLIMITED=True در .env
python manage.py collectstatic --noinput
python manage.py migrate
sudo systemctl restart divar_shop
