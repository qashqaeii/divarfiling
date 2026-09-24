from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.services.user_display import user_display_name

User = get_user_model()


class UserDisplayNameTests(TestCase):
    def test_username_before_phone_when_no_full_name(self):
        user = User.objects.create_user(
            username='کشکولی',
            password='x',
            phone='09196354424',
        )
        self.assertEqual(user_display_name(user), 'کشکولی')

    def test_full_name_wins(self):
        user = User.objects.create_user(
            username='kashkoli',
            password='x',
            phone='09121111111',
            first_name='حسین',
            last_name='قشقایی',
        )
        self.assertEqual(user_display_name(user), 'حسین قشقایی')
