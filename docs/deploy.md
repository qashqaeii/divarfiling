cd ~/DivarFiling
source venv/bin/activate
git pull origin main
python manage.py collectstatic --noinput
python manage.py migrate
sudo systemctl restart divar_shop

