"""تست تشخیص سیگنال آگهی‌دهنده — مالک واقعی در برابر مشاور پنهان."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from mobile_api.services.extraction_ingest import ingest_mobile_extraction
from workspace.services.advertiser_signal import (
    ADVERTISER_SIGNAL_DISGUISED,
    ADVERTISER_SIGNAL_GENUINE_PERSONAL,
    detect_advertiser_signal,
    has_disguised_consultant_markers,
    normalize_ad_text,
)

User = get_user_model()


class AdvertiserSignalDetectionTest(TestCase):
    def test_normalize_persian_variants(self):
        self.assertEqual(normalize_ad_text('مشاور شما'), normalize_ad_text('مشاور شما'))

    def test_genuine_personal_without_markers(self):
        signal = detect_advertiser_signal(
            title='اجاره آپارتمان ۶۵ متری',
            description='واحد تمیز و نوساز. نورگیر عالی.',
            business_type='personal',
        )
        self.assertEqual(signal, ADVERTISER_SIGNAL_GENUINE_PERSONAL)

    def test_owner_affirmation_phrases_mark_genuine(self):
        from workspace.services.advertiser_signal import has_owner_markers

        phrases = (
            'مالک هستم',
            'من مالک هستم',
            'مالکم',
            'من مالکم',
            'مالک مستقیم',
            'مستقیم از مالک',
            'خودم مالک هستم',
            'خودم صاحب ملک هستم',
            'صاحب ملک هستم',
            'صاحبخانه هستم',
            'این ملک متعلق به خودم است',
            'ملک شخصی خودم',
            'واحد شخصی خودم',
            'خانه خودم',
            'آپارتمان خودم',
            'فروش توسط مالک',
            'اجاره توسط مالک',
            'رهن توسط مالک',
            'بدون واسطه از مالک',
            'بدون واسطه',
            'مستقیم با مالک',
            'ارتباط مستقیم با مالک',
            'تماس با مالک',
            'بدون دخالت مشاور',
            'بدون دخالت املاک',
            'بدون واسطه‌',
            'سند به نام خودم',
            'سند به نام اینجانب',
            'مالک سند هستم',
            'مالک شش دانگ',
            'صاحب سند هستم',
            'خودم سازنده هستم',
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertTrue(has_owner_markers(title='', description=f'واحد نوساز. {phrase}.'))
                signal = detect_advertiser_signal(
                    title='فروش آپارتمان',
                    description=f'واحد نوساز. {phrase}.',
                    business_type='personal',
                )
                self.assertEqual(signal, ADVERTISER_SIGNAL_GENUINE_PERSONAL)

    def test_colleague_restriction_overrides_owner_claim(self):
        """منع تماس همکاران بر ادعای مالکیت اولویت دارد — نشانه مشاور پنهان."""
        signal = detect_advertiser_signal(
            title='اجاره آپارتمان',
            description='من مالک هستم. لطفاً همکارهای عزیز تماس نگیرید.',
            business_type='personal',
        )
        self.assertEqual(signal, ADVERTISER_SIGNAL_DISGUISED)
        self.assertTrue(has_disguised_consultant_markers(
            title='',
            description='لطفاً همکارهای عزیز تماس نگیرید.',
        ))

    def test_disguised_consultant_with_phrase_in_description(self):
        signal = detect_advertiser_signal(
            title='اجاره آپارتمان',
            description='لطفاً همکارهای عزیز تماس نگیرید. فقط مستاجر.',
            business_type='personal',
        )
        self.assertEqual(signal, ADVERTISER_SIGNAL_DISGUISED)

    def test_disguised_consultant_with_title_marker(self):
        self.assertTrue(has_disguised_consultant_markers(
            title='فایل شخصی — مشاور شما',
            description='',
        ))

    def test_disguised_consultant_with_standalone_moshaver(self):
        signal = detect_advertiser_signal(
            title='اجاره آپارتمان',
            description='واحد تمیز. تماس مشاور.',
            business_type='personal',
        )
        self.assertEqual(signal, ADVERTISER_SIGNAL_DISGUISED)
        self.assertTrue(has_disguised_consultant_markers(
            title='',
            description='مشاور',
        ))

    def test_disguised_consultant_amlak_afshin_branding(self):
        description = (
            'یک واحد آپارتمان 65 متری\n'
            'دو خواب\n'
            '⬅️⬅️⬅️  املاک افشین  ➡️➡️➡️\n'
            'آدرس املاک: خیابان حسام الدین. بعد از رنجبر. پلاک 11. املاک افشین.'
        )
        signal = detect_advertiser_signal(
            title='اجاره آپارتمان',
            description=description,
            business_type='personal',
        )
        self.assertEqual(signal, ADVERTISER_SIGNAL_DISGUISED)

    def test_disguised_consultant_amlak_bozorg_farda(self):
        description = (
            '۴۷متر تک خواب\n'
            'مشاور حرفه ای منطقه:محمدی\n'
            '⭐️⭐️⭐️املاک بزرگ فردا⭐️⭐️⭐️'
        )
        signal = detect_advertiser_signal(
            title='اجاره آپارتمان',
            description=description,
            business_type='personal',
        )
        self.assertEqual(signal, ADVERTISER_SIGNAL_DISGUISED)

    def test_disguised_consultant_amlak_in_parentheses(self):
        description = (
            '((املاک))\n'
            '5طبقه دو واحدی.رو به آفتاب.دوپار سندی باکس.\n'
            'داکت اسپلیت سرد وگرم.انباری بزرگ وکوچک.مستر.'
        )
        signal = detect_advertiser_signal(
            title='فروش آپارتمان',
            description=description,
            business_type='personal',
        )
        self.assertEqual(signal, ADVERTISER_SIGNAL_DISGUISED)
        self.assertTrue(has_disguised_consultant_markers(
            title='',
            description=description,
        ))

    def test_disguised_consultant_moshaver_in_parentheses(self):
        signal = detect_advertiser_signal(
            title='اجاره آپارتمان',
            description='((مشاور)) واحد تمیز',
            business_type='personal',
        )
        self.assertEqual(signal, ADVERTISER_SIGNAL_DISGUISED)

    def test_genuine_personal_amlak_in_normal_phrase(self):
        """«فروش املاک مسکونی» نباید به‌تنهایی مشاور پنهان شمرده شود."""
        signal = detect_advertiser_signal(
            title='فروش آپارتمان',
            description='واحد مناسب برای فروش املاک مسکونی در منطقه خوب.',
            business_type='personal',
        )
        self.assertEqual(signal, ADVERTISER_SIGNAL_GENUINE_PERSONAL)

    def test_disguised_consultant_karshenas_phrases(self):
        for description in (
            'کارشناس منطقه: محمدی',
            'کارشناس شما در خدمت',
            'کارشناس حرفه ای منطقه',
            'تماس با کارشناس',
        ):
            with self.subTest(description=description):
                signal = detect_advertiser_signal(
                    title='اجاره آپارتمان',
                    description=description,
                    business_type='personal',
                )
                self.assertEqual(signal, ADVERTISER_SIGNAL_DISGUISED)

    def test_disguised_consultant_karshenas_in_parentheses(self):
        signal = detect_advertiser_signal(
            title='فروش آپارتمان',
            description='((کارشناس))\nواحد ۸۰ متری',
            business_type='personal',
        )
        self.assertEqual(signal, ADVERTISER_SIGNAL_DISGUISED)

    def test_genuine_personal_karshenasi_not_karshenas(self):
        """کارشناسی / کارشناسی شده نباید مشاور پنهان شمرده شود."""
        for description in (
            'واحد کارشناسی شده',
            'دارای سند کارشناسی',
            'ملک کارشناسی شده و آماده تحویل',
        ):
            with self.subTest(description=description):
                signal = detect_advertiser_signal(
                    title='فروش آپارتمان',
                    description=description,
                    business_type='personal',
                )
                self.assertEqual(signal, ADVERTISER_SIGNAL_GENUINE_PERSONAL)

    def test_disguised_consultant_similar_listing_phrases(self):
        for description in (
            'موارد مشابه',
            'موارد مشابه موجود است',
            'موارد دیگر در منطقه',
            'فایل مشابه',
            'فایل مشابه موجود است',
            '((فایل مشابه)) موجود',
        ):
            with self.subTest(description=description):
                signal = detect_advertiser_signal(
                    title='اجاره آپارتمان',
                    description=description,
                    business_type='personal',
                )
                self.assertEqual(signal, ADVERTISER_SIGNAL_DISGUISED)

    def test_stored_genuine_personal_reclassified_on_display(self):
        from types import SimpleNamespace
        from workspace.services.advertiser_signal import listing_advertiser_display

        stale = SimpleNamespace(
            advertiser_signal='genuine_personal',
            title='اجاره آپارتمان',
            description='آدرس املاک: پلاک 11. املاک افشین.',
            business_type='personal',
            data={},
        )
        self.assertEqual(listing_advertiser_display(stale)['label'], 'مشاور پنهان')

    def test_official_consultant_skips_personal_detection(self):
        signal = detect_advertiser_signal(
            title='اجاره آپارتمان',
            description='لطفاً همکارهای عزیز تماس نگیرید',
            business_type='premium-panel',
        )
        self.assertEqual(signal, 'consultant')

    def test_ingest_sets_genuine_personal_signal(self):
        user = User.objects.create_user(username='09128889900', password='x')
        detail = {
            'seo': {'web_info': {'title': 'اجاره آپارتمان ۸۰ متری', 'city_persian': 'تهران'}},
            'share': {'web_url': 'https://divar.ir/v/genuine1'},
            'webengage': {'token': 'genuine1', 'business_type': 'personal'},
            'sections': [
                {
                    'section_name': 'DESCRIPTION',
                    'widgets': [
                        {
                            'widget_type': 'DESCRIPTION',
                            'data': {'text': 'واحد نوساز، بدون واسطه. تماس مستقیم با مالک.'},
                        },
                    ],
                },
                {
                    'section_name': 'LIST_DATA',
                    'widgets': [
                        {
                            'widget_type': 'RENT_SLIDER',
                            'data': {
                                'credit': {'value': '۵۰۰٬۰۰۰٬۰۰۰ تومان'},
                                'rent': {'value': '۱۵٬۰۰۰٬۰۰۰ تومان'},
                            },
                        },
                    ],
                },
            ],
        }
        result = ingest_mobile_extraction(user, {
            'filters': {
                'category': 'apartment-rent',
                'category_label': 'آپارتمان',
                'transaction_type_label': 'اجاره مسکونی',
                'city_name': 'تهران',
                'max_items': 1,
            },
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'genuine1', 'raw': detail}],
        })
        listing = result.dataset.listings.get()
        self.assertEqual(listing.advertiser_signal, ADVERTISER_SIGNAL_GENUINE_PERSONAL)
        self.assertEqual(result.genuine_personal_count, 1)
        self.assertEqual(result.disguised_consultant_count, 0)

    def test_listing_advertiser_display_labels(self):
        from types import SimpleNamespace
        from workspace.services.advertiser_signal import listing_advertiser_display

        genuine = SimpleNamespace(
            advertiser_signal='genuine_personal',
            title='فروش آپارتمان',
            description='بدون واسطه',
            business_type='personal',
            data={},
        )
        self.assertEqual(listing_advertiser_display(genuine)['label'], 'مالک واقعی')

        disguised = SimpleNamespace(
            advertiser_signal='disguised_consultant',
            title='اجاره',
            description='مشاور شما',
            business_type='personal',
            data={},
        )
        self.assertEqual(listing_advertiser_display(disguised)['label'], 'مشاور پنهان')

    def test_ingest_sets_disguised_signal(self):
        user = User.objects.create_user(username='09129990011', password='x')
        detail = {
            'seo': {
                'web_info': {
                    'title': 'اجاره آپارتمان — مشاور شما در منطقه',
                    'city_persian': 'تهران',
                },
            },
            'share': {'web_url': 'https://divar.ir/v/disguised1'},
            'webengage': {'token': 'disguised1', 'business_type': 'personal'},
            'sections': [
                {
                    'section_name': 'DESCRIPTION',
                    'widgets': [
                        {
                            'widget_type': 'DESCRIPTION',
                            'data': {'text': 'مشاور شما در منطقه — همکاران تماس نگیرید.'},
                        },
                    ],
                },
                {
                    'section_name': 'LIST_DATA',
                    'widgets': [
                        {
                            'widget_type': 'RENT_SLIDER',
                            'data': {
                                'credit': {'value': '۵۰۰٬۰۰۰٬۰۰۰ تومان'},
                                'rent': {'value': '۱۵٬۰۰۰٬۰۰۰ تومان'},
                            },
                        },
                    ],
                },
            ],
        }
        result = ingest_mobile_extraction(user, {
            'filters': {
                'category': 'apartment-rent',
                'category_label': 'آپارتمان',
                'transaction_type_label': 'اجاره مسکونی',
                'city_name': 'تهران',
                'max_items': 1,
            },
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'disguised1', 'raw': detail}],
        })
        listing = result.dataset.listings.get()
        self.assertEqual(listing.advertiser_signal, ADVERTISER_SIGNAL_DISGUISED)
        self.assertEqual(result.genuine_personal_count, 0)
        self.assertEqual(result.disguised_consultant_count, 1)
