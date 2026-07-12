from django.test import SimpleTestCase

from shop.templatetags.persian_tags import transaction_status_fa, transaction_status_tone


class TransactionStatusTagTests(SimpleTestCase):
    def test_paid_maps_to_persian_success_label(self):
        self.assertEqual(transaction_status_fa('paid'), 'پرداخت شده')
        self.assertEqual(transaction_status_tone('paid'), 'success')

    def test_pending_and_failed_labels(self):
        self.assertEqual(transaction_status_fa('pending'), 'در انتظار پرداخت')
        self.assertEqual(transaction_status_fa('failed'), 'ناموفق')
        self.assertEqual(transaction_status_tone('pending'), 'pending')
        self.assertEqual(transaction_status_tone('failed'), 'failed')
