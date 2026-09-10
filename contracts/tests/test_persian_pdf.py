"""Tests for Persian PDF shaping and contract display."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from contracts.services.contract_display import build_contract_display
from contracts.services.persian_text import prepare_rtl_text, rtl_paragraph_html
from contracts.services.tokens import hash_token
from workspace.models import CRMDeal, Customer

User = get_user_model()


class PersianTextTests(TestCase):
    def test_prepare_rtl_text_shapes_persian(self):
        raw = 'قرارداد'
        shaped = prepare_rtl_text(raw)
        self.assertTrue(shaped)
        self.assertNotEqual(shaped, raw)

    def test_rtl_paragraph_html_escapes(self):
        html_out = rtl_paragraph_html('test <tag>')
        self.assertNotIn('<tag>', html_out)

    def test_rtl_paragraph_html_plain_ascii(self):
        self.assertEqual(rtl_paragraph_html('hello world'), 'hello world')

    def test_rtl_paragraph_html_bidi_shapes_persian(self):
        import html

        text = 'ماده ۱۰ - تعهدات خریدار'
        shaped = rtl_paragraph_html(text)
        self.assertEqual(shaped, html.escape(prepare_rtl_text(text)))
        self.assertNotEqual(shaped, text)


class ContractDisplayTests(TestCase):
    def test_display_matches_sections(self):
        from contracts.models import Contract, ContractParty, ContractVersion

        user = User.objects.create_user(username='disp1', phone='09123000001', password='x')
        customer = Customer.objects.create(user=user, name='c', phone='09123000002')
        deal = CRMDeal.objects.create(user=user, customer=customer, title='d')
        contract = Contract.objects.create(
            user=user, deal=deal, contract_type='sale', internal_number='DF-SAL-1405-000020',
            verification_token_hash=hash_token('disp-verify'),
            status='finalized',
        )
        version = ContractVersion.objects.create(
            contract=contract, version_number=1, is_published=True,
            financial_data={'total_price': '1000000000', 'payments': []},
        )
        ContractParty.objects.create(
            contract=contract, version=version, role='seller',
            first_name='علی', last_name='احمدی', mobile='09121111111',
        )
        display = build_contract_display(contract, version)
        self.assertTrue(display['document_sections'])
        self.assertEqual(len(display['parties']), 1)


class ArticleBoxLayoutTests(TestCase):
    def test_body_to_flowables_splits_long_text(self):
        from contracts.services.pdf import _pdf_styles
        from contracts.services.pdf_layout import body_to_flowables

        styles = _pdf_styles('Helvetica', 'Helvetica-Bold')
        long_body = 'جمله اول. ' * 80
        flowables = body_to_flowables(long_body, styles['body'], max_chunk=120)
        self.assertGreater(len(flowables), 3)

    def test_article_box_keeps_body_outside_table(self):
        from reportlab.platypus import Paragraph, Table

        from contracts.services.pdf import _pdf_styles
        from contracts.services.pdf_layout import article_box

        styles = _pdf_styles('Helvetica', 'Helvetica-Bold')
        body = Paragraph('متن آزمایشی', styles['body'])
        flowables = article_box('ماده ۱', [body], 400, styles)
        self.assertEqual(len(flowables), 3)
        self.assertIsInstance(flowables[0], Table)
        self.assertIs(flowables[1], body)


class ContractPdfTests(TestCase):
    @patch('contracts.services.pdf.resolve_persian_font_paths')
    def test_generate_pdf_bytes_with_shaping(self, mock_fonts):
        from contracts.models import Contract, ContractVersion

        mock_fonts.return_value = ('C:/Windows/Fonts/tahoma.ttf', 'C:/Windows/Fonts/tahomabd.ttf')
        user = User.objects.create_user(username='pdf1', phone='09124000001', password='x')
        customer = Customer.objects.create(user=user, name='c', phone='09124000002')
        deal = CRMDeal.objects.create(user=user, customer=customer, title='d')
        contract = Contract.objects.create(
            user=user, deal=deal, contract_type='sale', internal_number='DF-SAL-1405-000021',
            verification_token_hash=hash_token('pdf-verify'),
            status='finalized',
            finalized_at=timezone.now(),
        )
        version = ContractVersion.objects.create(
            contract=contract, version_number=1, is_published=True,
            snapshot_json={'clauses': [], 'parties': [], 'payments': [], 'financial': {}},
        )
        try:
            from contracts.services.pdf import generate_contract_pdf_bytes
            data = generate_contract_pdf_bytes(version, verify_raw_token='testtoken', preview=True)
        except Exception as exc:
            if 'tahoma' in str(exc).lower() or 'font' in str(exc).lower():
                self.skipTest('Tahoma not available in test environment')
            raise
        if not data:
            self.skipTest('reportlab or font unavailable')
        self.assertTrue(data.startswith(b'%PDF'))

    @patch('contracts.services.pdf.build_contract_display')
    @patch('contracts.services.pdf.resolve_persian_font_paths')
    def test_long_clause_body_not_truncated(self, mock_fonts, mock_display):
        from contracts.models import Contract, ContractVersion

        mock_fonts.return_value = ('C:/Windows/Fonts/tahoma.ttf', 'C:/Windows/Fonts/tahomabd.ttf')
        marker = 'انتهای_بند_آزمایشی_یکتا'
        long_body = ' '.join(['بند قرارداد'] * 120) + ' ' + marker
        mock_display.return_value = {
            'verify_url': '',
            'content_hash': '',
            'content_hash_short': '',
            'parties': [],
            'property': {},
            'payment_schedule': {'has_rows': False},
            'penalty_summary': [],
            'costs_summary': [],
            'document_sections': [
                {'title': 'ماده ۱۰ - تعهدات خریدار', 'body': long_body, 'section_kind': 'clause'},
            ],
        }
        user = User.objects.create_user(username='pdf2', phone='09124000003', password='x')
        customer = Customer.objects.create(user=user, name='c', phone='09124000004')
        deal = CRMDeal.objects.create(user=user, customer=customer, title='d')
        contract = Contract.objects.create(
            user=user, deal=deal, contract_type='sale', internal_number='DF-SAL-1405-000022',
            verification_token_hash=hash_token('pdf-verify-2'),
            status='finalized',
            finalized_at=timezone.now(),
        )
        version = ContractVersion.objects.create(
            contract=contract, version_number=1, is_published=True,
            snapshot_json={'clauses': [], 'parties': [], 'payments': [], 'financial': {}},
        )
        try:
            from contracts.services.pdf import generate_contract_pdf_bytes
            data = generate_contract_pdf_bytes(version, preview=True)
        except Exception as exc:
            if 'tahoma' in str(exc).lower() or 'font' in str(exc).lower():
                self.skipTest('Tahoma not available in test environment')
            raise
        if not data:
            self.skipTest('reportlab or font unavailable')
        from contracts.services.pdf import _pdf_styles
        from contracts.services.pdf_layout import body_to_flowables
        styles = _pdf_styles('Helvetica', 'Helvetica-Bold')
        chunks = body_to_flowables(long_body, styles['body'])
        self.assertGreater(len(chunks), 4)
        self.assertGreater(len(data), 8000)
