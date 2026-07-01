"""تست حذف thumbnail تکراری از لیست تصاویر دیوار."""
from django.test import TestCase

from workspace.services.property_images import deduplicate_divar_image_urls

POST = (
    'https://postimage01.divarcdn.com/static/photo/neda/webp_post/'
    'eGxoc-iY-1xZAvjSar1Ciw/b3609a4e-b2f3-4c9f-bfe2-2c036d4349a9.webp'
)
THUMB = (
    'https://postimage01.divarcdn.com/static/photo/neda/webp_thumbnail/'
    '94aKt6hlz-p4XRCnUkjHnw/b3609a4e-b2f3-4c9f-bfe2-2c036d4349a9.webp'
)


class DivarImageDedupTests(TestCase):
    def test_prefers_webp_post_over_thumbnail(self):
        result = deduplicate_divar_image_urls([THUMB, POST])
        self.assertEqual(result, [POST])

    def test_keeps_distinct_images(self):
        other = 'https://postimage01.divarcdn.com/static/photo/neda/webp_post/abc/other.webp'
        result = deduplicate_divar_image_urls([POST, THUMB, other])
        self.assertEqual(result, [POST, other])

    def test_thumbnail_only_when_post_missing(self):
        result = deduplicate_divar_image_urls([THUMB])
        self.assertEqual(result, [THUMB])
