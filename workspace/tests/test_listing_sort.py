from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import Dataset, Listing
from workspace.services.advertiser_signal import listing_advertiser_display
from workspace.services.filters import sort_queryset


class ListingAdvertiserSortTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='sortuser', password='pass', phone='09127777777')
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='sort-test',
            original_filename='t.xlsx',
            file_format='xlsx',
        )
        self.personal = Listing.objects.create(
            dataset=self.dataset,
            token='p1',
            title='شخصی اول',
            business_type='شخصی',
            price=100,
        )
        self.consultant = Listing.objects.create(
            dataset=self.dataset,
            token='c1',
            title='مشاور اول',
            business_type='مشاور',
            advertiser_signal='consultant',
            price=999_999,
        )
        self.genuine = Listing.objects.create(
            dataset=self.dataset,
            token='g1',
            title='مالک واقعی',
            business_type='شخصی',
            advertiser_signal='genuine_personal',
            price=50,
        )
        self.disguised = Listing.objects.create(
            dataset=self.dataset,
            token='d1',
            title='مشاور پنهان',
            business_type='شخصی',
            advertiser_signal='disguised_consultant',
            price=200,
        )

    def test_personal_listings_before_consultants(self):
        qs = sort_queryset(self.dataset.listings.all(), '-price', '-price')
        ordered = list(qs.values_list('token', flat=True))
        self.assertEqual(ordered[-1], 'c1')
        self.assertNotIn('c1', ordered[:-1])

    def test_business_type_desc_puts_consultants_first(self):
        qs = sort_queryset(self.dataset.listings.all(), '-business_type', '-price')
        ordered = list(qs.values_list('token', flat=True))
        self.assertEqual(ordered[0], 'c1')

    def test_business_type_asc_groups_by_display_category(self):
        qs = sort_queryset(self.dataset.listings.all(), 'business_type', '-price')
        ordered = list(qs.values_list('token', flat=True))
        self.assertEqual(ordered, ['p1', 'g1', 'd1', 'c1'])

    def test_business_type_desc_groups_by_display_category(self):
        qs = sort_queryset(self.dataset.listings.all(), '-business_type', '-price')
        ordered = list(qs.values_list('token', flat=True))
        self.assertEqual(ordered, ['c1', 'd1', 'p1', 'g1'])

    def test_business_type_sort_uses_computed_signal_not_stale_db_field(self):
        stale = Listing.objects.create(
            dataset=self.dataset,
            token='stale',
            title='فروش آپارتمان',
            description='مشاور شما در منطقه',
            business_type='شخصی',
            advertiser_signal='genuine_personal',
            price=150,
        )
        self.assertEqual(listing_advertiser_display(stale)['short_label'], 'مشاور پنهان')
        qs = sort_queryset(self.dataset.listings.all(), 'business_type', '-price')
        ordered = list(qs.values_list('token', flat=True))
        self.assertEqual(ordered, ['p1', 'g1', 'd1', 'stale', 'c1'])
        self.assertGreater(ordered.index('stale'), ordered.index('g1'))
        self.assertLess(ordered.index('stale'), ordered.index('c1'))
