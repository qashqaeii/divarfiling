cd ~/DivarFiling
source venv/bin/activate
git pull origin main
pip install -r requirements.txt
python manage.py migrate
python manage.py sync_public_knowledge
python manage.py collectstatic --noinput
sudo systemctl restart divar_shop

# تالار گفتگو (WebSocket — پس از تنظیم Redis و Nginx)
# COMMUNITY_FORUM_ENABLED=true در .env
# sudo systemctl restart divar_forum_ws
# Cron: 0 * * * * python manage.py purge_forum_messages

جزئیات: docs/community_forum.md
