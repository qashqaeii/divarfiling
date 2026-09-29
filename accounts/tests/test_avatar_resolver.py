from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from accounts.avatar_catalog import (
    DEFAULT_AVATAR_KEY,
    contact_avatar_gender_prefix,
    contact_avatar_role_slug,
    contact_role_avatar_static_relative_path,
    normalize_avatar_key,
    resolve_contact_avatar_display,
    resolve_user_avatar_display,
)
from accounts.models import User, UserProfile
from workspace.models import Customer


class AvatarCatalogTests(SimpleTestCase):
    def test_normalize_avatar_key(self):
        self.assertEqual(normalize_avatar_key('avatar_05'), 'avatar_05')
        self.assertEqual(normalize_avatar_key('avatar5'), 'avatar_05')
        self.assertIsNone(normalize_avatar_key('avatar_99'))

    def test_missing_avatar_asset_falls_back_to_avatar_01(self):
        self.assertEqual(normalize_avatar_key('avatar_00'), None)
        self.assertEqual(DEFAULT_AVATAR_KEY, 'avatar_01')


class AvatarResolverTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u1', password='x')
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_user_selected_avatar_is_persisted_in_resolver(self):
        self.profile.avatar_key = 'avatar_03'
        self.profile.save(update_fields=['avatar_key'])
        display = resolve_user_avatar_display(self.profile)
        self.assertFalse(display['has_custom_avatar'])
        self.assertEqual(display['avatar_key'], 'avatar_03')
        self.assertEqual(display['effective_key'], 'avatar_03')

    def test_existing_profile_photo_is_not_overwritten(self):
        self.profile.avatar_key = 'avatar_02'
        self.profile.avatar = SimpleUploadedFile('me.jpg', b'file', content_type='image/jpeg')
        self.profile.save()
        display = resolve_user_avatar_display(self.profile)
        self.assertTrue(display['has_custom_avatar'])
        self.assertTrue(display['url'])

    def test_contact_without_photo_uses_role_avatar(self):
        customer = Customer.objects.create(
            user=self.user,
            name='علی',
            customer_type='خریدار',
            gender='male',
        )
        display = resolve_contact_avatar_display(customer)
        self.assertFalse(display['has_photo'])
        self.assertIn('CONTACTAVATAR/MANBuyer.webp', display['photo_url'])
        self.assertEqual(display['avatar_key'], 'contact_man_buyer')

    def test_contact_female_uses_woman_role_avatar(self):
        customer = Customer.objects.create(
            user=self.user,
            name='سارا',
            customer_type='متقاضی خرید',
            gender='female',
        )
        self.assertEqual(
            contact_role_avatar_static_relative_path(customer),
            'images/avatar/CONTACTAVATAR/WOMANBuyerApplicant.webp',
        )

    def test_contact_without_gender_defaults_to_man(self):
        customer = Customer.objects.create(
            user=self.user,
            name='ناشناس',
            customer_type='سرنخ',
        )
        self.assertEqual(contact_avatar_gender_prefix(customer), 'MAN')
        self.assertEqual(contact_avatar_role_slug(customer), 'Lead')

    def test_legal_entity_uses_corporate_avatar(self):
        customer = Customer.objects.create(
            user=self.user,
            name='شرکت',
            customer_type='اشخاص حقوقی',
            is_legal_entity=True,
            gender='female',
        )
        self.assertEqual(contact_avatar_role_slug(customer), 'CorporateEntity')
        self.assertEqual(contact_avatar_gender_prefix(customer), 'MAN')

    def test_contact_with_photo_uses_contact_photo(self):
        customer = Customer.objects.create(user=self.user, name='سارا')
        customer.photo = SimpleUploadedFile('c.jpg', b'x', content_type='image/jpeg')
        customer.save()
        display = resolve_contact_avatar_display(customer)
        self.assertTrue(display['has_photo'])
        self.assertTrue(display['photo_url'])
