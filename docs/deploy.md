cd ~/DivarFiling
source venv/bin/activate
git pull origin main
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart divar_shop
