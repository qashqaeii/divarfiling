"""تست حذف thumbnail تکراری از لیست تصاویر دیوار."""
from django.test import TestCase

from unittest.mock import MagicMock, patch

from workspace.services.property_images import (
    deduplicate_divar_image_urls,
    divar_image_download_candidates,
    mirror_remote_images_to_property,
)

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

    def test_download_candidates_keep_thumbnail_fallback(self):
        result = divar_image_download_candidates([THUMB, POST])
        self.assertEqual(result, [[POST, THUMB]])

    def test_mirror_falls_back_to_thumbnail_on_post_404(self):
        prop = MagicMock(pk=99)

        def fake_get(url, **kwargs):
            resp = MagicMock()
            if '/webp_post/' in url:
                resp.status_code = 404
                resp.raise_for_status.side_effect = __import__('requests').HTTPError(response=resp)
            else:
                resp.status_code = 200
                resp.content = b'\xff\xd8\xff\xe0' + b'0' * 64
                resp.headers = {'Content-Type': 'image/jpeg'}
                resp.raise_for_status = MagicMock()
            return resp

        with patch('workspace.services.property_images.requests.get', side_effect=fake_get):
            with patch('workspace.services.property_images.store_property_image', return_value='/media/x.jpg'):
                mirrored = mirror_remote_images_to_property(None, prop, [POST, THUMB])
        self.assertEqual(mirrored, ['/media/x.jpg'])
