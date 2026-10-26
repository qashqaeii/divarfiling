"""خطاهای خواندن فایل — بدون ۵۰۰."""
import io

from django.test import SimpleTestCase

from workspace.services.spreadsheet_io import SpreadsheetReadError, read_uploaded_spreadsheet


class DummyFile(io.BytesIO):
    def __init__(self, data: bytes, name: str, size=None):
        super().__init__(data)
        self.name = name
        self.size = size if size is not None else len(data)


class SpreadsheetIOErrorTests(SimpleTestCase):
    def test_corrupt_xlsx_raises_readable_error(self):
        f = DummyFile(b'not-a-zip', 'bad.xlsx')
        with self.assertRaises(SpreadsheetReadError):
            read_uploaded_spreadsheet(f)

    def test_oversize_rejected(self):
        f = DummyFile(b'x', 'big.csv', size=30 * 1024 * 1024)
        with self.assertRaises(SpreadsheetReadError) as ctx:
            read_uploaded_spreadsheet(f, max_bytes=1024)
        self.assertIn('حجم', str(ctx.exception))
