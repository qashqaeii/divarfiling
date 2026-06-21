"""
اسکریپت ایجاد superuser
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'divar_shop.settings')
django.setup()

from accounts.models import User

# ایجاد superuser
username = 'qashqaeii'
email = 'qashqaeii.ps4@gmail.com'
password = 'hossein0835'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'Superuser created: {username}')
else:
    print(f'Superuser {username} already exists')

