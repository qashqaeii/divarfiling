from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from accounts.services.sms import SmsConfigurationError, SmsSendError, send_pattern_sms, send_simple_sms


@override_settings(
    SMS_ENABLED=True,
    SMS_PROVIDER='console',
    FARAZSMS_PATTERNS={'login': '', 'register': '', 'verify_phone': '', 'license_renewal': '', 'system': ''},
)
class ConsoleSmsServiceTests(SimpleTestCase):
    def test_send_pattern_console(self):
        result = send_pattern_sms('09123456789', purpose='login', attributes={'code': '123456'})
        self.assertTrue(result.success)
        self.assertEqual(result.provider, 'console')
        self.assertTrue(result.is_fake)
        self.assertEqual(result.phone, '09123456789')

    def test_send_simple_console(self):
        result = send_simple_sms('09123456789', 'پیام تست')
        self.assertTrue(result.success)
        self.assertEqual(result.provider, 'console')

    def test_invalid_phone(self):
        with self.assertRaises(SmsSendError) as ctx:
            send_pattern_sms('123', purpose='login', attributes={'code': '1'})
        self.assertEqual(ctx.exception.code, 'sms_invalid_phone')

    def test_normalize_before_send(self):
        result = send_pattern_sms('+989123456789', purpose='register', attributes={'code': '111111'})
        self.assertEqual(result.phone, '09123456789')


@override_settings(
    SMS_ENABLED=True,
    SMS_PROVIDER='faraz',
    FARAZSMS_API_KEY='test-key',
    FARAZSMS_LINE_NUMBER='90008361',
    FARAZSMS_BASE_URL='https://api.iranpayamak.com',
    FARAZSMS_PATTERNS={'login': 'PATLOGIN', 'register': '', 'verify_phone': '', 'license_renewal': '', 'system': ''},
    FARAZSMS_OTP_ATTR='code',
)
class FarazSmsServiceTests(SimpleTestCase):
    @patch('accounts.services.sms.faraz.requests.request')
    def test_pattern_success(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.content = b'{"status":"success","data":123}'
        mock_resp.json.return_value = {'status': 'success', 'data': 123}
        mock_request.return_value = mock_resp

        result = send_pattern_sms('09123456789', purpose='login', attributes={'code': '654321'})
        self.assertTrue(result.success)
        self.assertEqual(result.provider, 'faraz')
        self.assertEqual(result.message_id, '123')

        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], 'POST')
        self.assertIn('/ws/v1/sms/pattern', args[1])
        self.assertEqual(kwargs['headers']['Api-Key'], 'test-key')
        self.assertEqual(kwargs['json']['code'], 'PATLOGIN')
        self.assertEqual(kwargs['json']['recipient'], '09123456789')
        self.assertEqual(kwargs['json']['attributes']['code'], '654321')
        self.assertEqual(kwargs['json']['number_format'], 'english')

    @patch('accounts.services.sms.faraz.requests.request')
    def test_timeout(self, mock_request):
        import requests
        mock_request.side_effect = requests.Timeout()
        with self.assertRaises(SmsSendError) as ctx:
            send_pattern_sms('09123456789', purpose='login', attributes={'code': '1'})
        self.assertEqual(ctx.exception.code, 'sms_timeout')

    @patch('accounts.services.sms.faraz.requests.request')
    def test_provider_error(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.content = b'{"status":"error","message":"bad"}'
        mock_resp.json.return_value = {'status': 'error', 'message': 'موجودی کافی نیست'}
        mock_request.return_value = mock_resp
        with self.assertRaises(SmsSendError):
            send_pattern_sms('09123456789', purpose='login', attributes={'code': '1'})

    def test_missing_api_key(self):
        with override_settings(FARAZSMS_API_KEY=''):
            with self.assertRaises(SmsConfigurationError):
                send_pattern_sms('09123456789', purpose='login', attributes={'code': '1'})


@override_settings(SMS_ENABLED=False, SMS_PROVIDER='console')
class SmsDisabledTests(SimpleTestCase):
    def test_disabled(self):
        with self.assertRaises(SmsSendError) as ctx:
            send_simple_sms('09123456789', 'x')
        self.assertEqual(ctx.exception.code, 'sms_disabled')
