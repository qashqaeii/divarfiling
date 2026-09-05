"""تولید PDF قرارداد — فقط از snapshot immutable."""
from __future__ import annotations

import io
import logging
import os

from django.conf import settings
from django.core.files.base import ContentFile
from django.urls import reverse

from contracts.constants import LEGAL_DISCLAIMER_SHORT
from contracts.models import ContractVersion
from contracts.services.audit import log_audit_event
from contracts.services.version_copy import version_display_snapshot

logger = logging.getLogger(__name__)


def _get_persian_font() -> str:
    for fp in (
        'C:/Windows/Fonts/tahoma.ttf',
        'C:/Windows/Fonts/B Nazanin.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ):
        if os.path.isfile(fp):
            return fp
    return ''


def generate_contract_pdf(
    version: ContractVersion,
    *,
    verify_raw_token: str = '',
    request=None,
) -> str:
    pdf_bytes = generate_contract_pdf_bytes(
        version, verify_raw_token=verify_raw_token, request=request, preview=False,
    )
    if not pdf_bytes:
        return ''
    contract = version.contract
    filename = f'{contract.internal_number}_v{version.version_number}.pdf'
    version.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
    log_audit_event(contract, 'PDF_GENERATED', version=version, metadata={'filename': filename})
    return version.pdf_file.name


def generate_contract_pdf_bytes(
    version: ContractVersion,
    *,
    verify_raw_token: str = '',
    request=None,
    preview: bool = False,
) -> bytes:
    if not preview and not version.is_published and version.contract.status != 'finalized':
        raise ValueError('PDF فقط از نسخه published/finalized تولید می‌شود.')

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image as RLImage
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        logger.warning('reportlab not available: %s', exc)
        return b''

    contract = version.contract
    snap = version.snapshot_json or version_display_snapshot(version)
    font_path = _get_persian_font()
    font_name = 'Helvetica'
    if font_path:
        try:
            pdfmetrics.registerFont(TTFont('PF', font_path))
            font_name = 'PF'
        except Exception:
            pass

    buffer = io.BytesIO()

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.drawCentredString(A4[0] / 2, 1.2 * cm, LEGAL_DISCLAIMER_SHORT[:120])
        canvas.drawCentredString(A4[0] / 2, 0.8 * cm, f'صفحه {canvas.getPageNumber()}')
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2.5 * cm,
    )
    title_style = ParagraphStyle('title', fontName=font_name, fontSize=16, alignment=TA_CENTER)
    body_style = ParagraphStyle('body', fontName=font_name, fontSize=11, alignment=TA_RIGHT, leading=18)
    footer_style = ParagraphStyle('footer', fontName=font_name, fontSize=8, alignment=TA_CENTER, textColor=colors.grey)

    story = []
    story.append(Paragraph(f'<b>{contract.get_contract_type_display()}</b>', title_style))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f'شناسه داخلی فایلینگ: {contract.internal_number} — نسخه {version.version_number}',
        body_style,
    ))
    if contract.finalized_at:
        story.append(Paragraph(f'تاریخ نهایی‌سازی: {contract.finalized_at.date()}', body_style))
    story.append(Spacer(1, 16))

    idx = 1
    for clause in snap.get('clauses', []):
        custom = 'شرط اختصاصی — ' if clause.get('is_custom') else ''
        story.append(Paragraph(
            f'<b>ماده {idx} — {custom}{clause.get("title", "")}</b>', body_style,
        ))
        story.append(Paragraph((clause.get('body_text') or '').replace('\n', '<br/>'), body_style))
        story.append(Spacer(1, 10))
        idx += 1

    story.append(Paragraph('<b>طرفین</b>', body_style))
    for p in snap.get('parties', []):
        name = p.get('company_name') or f'{p.get("first_name", "")} {p.get("last_name", "")}'.strip()
        story.append(Paragraph(f'{p.get("role", "")}: {name}', body_style))

    payments = snap.get('payments', [])
    if payments:
        story.append(Spacer(1, 12))
        story.append(Paragraph('<b>برنامه پرداخت</b>', body_style))
        rows = [['عنوان', 'مبلغ', 'سررسید']]
        for pay in payments:
            rows.append([pay.get('label', ''), str(pay.get('amount', '')), pay.get('due_date') or '—'])
        tbl = Table(rows, colWidths=[6 * cm, 4 * cm, 4 * cm])
        tbl.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(tbl)

    if version.content_hash:
        story.append(Spacer(1, 16))
        story.append(Paragraph(f'هش نسخه: {version.content_hash}', footer_style))

    if verify_raw_token:
        site = getattr(settings, 'SITE_URL', 'https://divarfiling.ir')
        verify_url = f'{site.rstrip("/")}{reverse("public_verify", kwargs={"token": verify_raw_token})}'
        story.append(Spacer(1, 12))
        story.append(Paragraph('QR تأیید آنلاین — شناسه داخلی فایلینگ دیوار', footer_style))
        try:
            import qrcode
            qr = qrcode.make(verify_url)
            qr_buf = io.BytesIO()
            qr.save(qr_buf, format='PNG')
            qr_buf.seek(0)
            story.append(RLImage(qr_buf, width=3 * cm, height=3 * cm))
        except Exception:
            story.append(Paragraph(verify_url, footer_style))

    story.append(Spacer(1, 24))
    story.append(Paragraph(LEGAL_DISCLAIMER_SHORT, footer_style))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
