from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import Dataset, Listing
from workspace.services.filters import apply_amenity_filters, apply_listing_filters, parse_filter_params


class ListingRoomsFilterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='filteruser', password='pass', phone='09129999999')
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='rooms-filter-test',
            original_filename='t.xlsx',
            file_format='xlsx',
        )
        self.three_rooms = Listing.objects.create(
            dataset=self.dataset,
            token='r3',
            title='آپارتمان 3 خواب',
            rooms='',
            data={'اتاق': '۳'},
        )
        self.two_rooms = Listing.objects.create(
            dataset=self.dataset,
            token='r2',
            title='دو خواب',
            rooms='2',
        )

    def test_rooms_filter_matches_data_json_when_db_field_empty(self):
        qs = apply_listing_filters(self.dataset.listings.all(), {'rooms': '3'}, self.user)
        filtered = apply_amenity_filters(list(qs), {'rooms': '3'})
        tokens = {lst.token for lst in filtered}
        self.assertIn('r3', tokens)
        self.assertNotIn('r2', tokens)

    def test_rooms_filter_accepts_persian_digits(self):
        qs = apply_listing_filters(self.dataset.listings.all(), {'rooms': '۳'}, self.user)
        filtered = apply_amenity_filters(list(qs), {'rooms': '۳'})
        self.assertEqual({lst.token for lst in filtered}, {'r3'})

    def test_parse_filter_params_normalizes_rooms(self):
        class Req:
            GET = {'rooms': '3'}
        self.assertEqual(parse_filter_params(Req())['rooms'], '3')
