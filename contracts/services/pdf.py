"""تولید PDF قرارداد — از contract_display مشترک با Public View."""
from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from contracts.constants import LEGAL_DISCLAIMER_SHORT
from contracts.models import ContractVersion
from contracts.services.audit import log_audit_event
from contracts.services.contract_display import build_contract_display
from contracts.services.persian_text import (
    prepare_rtl_text,
    resolve_persian_font_paths,
    rtl_paragraph_html,
    rtl_plain,
)

logger = logging.getLogger(__name__)

_FONT_REGULAR = 'PF'
_FONT_BOLD = 'PF-Bold'


def _register_fonts() -> tuple[str, str]:
    regular_path, bold_path = resolve_persian_font_paths()
    font_regular = 'Helvetica'
    font_bold = 'Helvetica-Bold'
    if not regular_path:
        logger.warning('Persian font not found — PDF may render incorrectly')
        return font_regular, font_bold
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        pdfmetrics.registerFont(TTFont(_FONT_REGULAR, regular_path))
        font_regular = _FONT_REGULAR
        if bold_path:
            pdfmetrics.registerFont(TTFont(_FONT_BOLD, bold_path))
            font_bold = _FONT_BOLD
        else:
            font_bold = _FONT_REGULAR
    except Exception as exc:
        logger.warning('Font registration failed: %s', exc)
    return font_regular, font_bold


def _verify_url(verify_raw_token: str, request=None) -> str:
    if not verify_raw_token:
        return ''
    path = reverse('public_verify', kwargs={'token': verify_raw_token})
    if request:
        return request.build_absolute_uri(path)
    site = getattr(settings, 'SITE_URL', 'https://divarfiling.ir')
    return f'{site.rstrip("/")}{path}'


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


def render_contract_pdf_bytes(
    version: ContractVersion,
    *,
    verify_raw_token: str = '',
    request=None,
    preview: bool = False,
    refresh_stored: bool = False,
) -> bytes:
    """
    Always generate a fresh PDF (same pipeline as workspace preview).
    Optionally replace a stale stored file on finalized contracts.
    """
    pdf_bytes = generate_contract_pdf_bytes(
        version,
        verify_raw_token=verify_raw_token,
        request=request,
        preview=preview,
    )
    if not pdf_bytes:
        return b''
    if refresh_stored and not preview and version.contract.status == 'finalized':
        contract = version.contract
        filename = f'{contract.internal_number}_v{version.version_number}.pdf'
        try:
            version.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
            version.save(update_fields=['pdf_file'])
        except Exception as exc:
            logger.warning('Could not refresh stored contract PDF: %s', exc)
    return pdf_bytes


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
        from reportlab.platypus import (
            Image as RLImage,
            KeepTogether,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        logger.warning('reportlab not available: %s', exc)
        return b''

    contract = version.contract
    display = build_contract_display(contract, version)
    verify_url = display.get('verify_url') or _verify_url(verify_raw_token, request)

    font_name, font_bold = _register_fonts()

    buffer = io.BytesIO()
    page_w, page_h = A4
    margin_r = 2 * cm
    margin_l = 2 * cm
    margin_t = 2 * cm
    margin_b = 2.8 * cm

    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(font_name, 7)
        disclaimer = prepare_rtl_text(LEGAL_DISCLAIMER_SHORT[:140])
        canvas.drawCentredString(page_w / 2, 1.1 * cm, disclaimer)
        page_lbl = prepare_rtl_text(f'صفحه {canvas.getPageNumber()}')
        canvas.drawCentredString(page_w / 2, 0.65 * cm, page_lbl)
        if display.get('content_hash_short'):
            hash_lbl = prepare_rtl_text(f'اثر انگشت: {display["content_hash_short"]}')
            canvas.drawRightString(page_w - margin_r, 0.65 * cm, hash_lbl)
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=margin_r,
        leftMargin=margin_l,
        topMargin=margin_t,
        bottomMargin=margin_b,
        title=prepare_rtl_text(contract.get_contract_type_display()),
    )

    title_style = ParagraphStyle(
        'title', fontName=font_bold, fontSize=16, alignment=TA_CENTER, leading=24,
        textColor=colors.HexColor('#0f172a'),
    )
    subtitle_style = ParagraphStyle(
        'subtitle', fontName=font_name, fontSize=10, alignment=TA_CENTER, leading=16,
        textColor=colors.HexColor('#475569'),
    )
    heading_style = ParagraphStyle(
        'heading', fontName=font_bold, fontSize=12, alignment=TA_RIGHT, leading=19,
        spaceBefore=8, spaceAfter=5, textColor=colors.HexColor('#0f172a'),
    )
    body_style = ParagraphStyle(
        'body', fontName=font_name, fontSize=10.5, alignment=TA_RIGHT, leading=18,
        spaceAfter=5, textColor=colors.HexColor('#1e293b'),
    )
    meta_style = ParagraphStyle(
        'meta', fontName=font_name, fontSize=9, alignment=TA_RIGHT, leading=14,
        textColor=colors.HexColor('#64748b'),
    )
    footer_style = ParagraphStyle(
        'footer', fontName=font_name, fontSize=8, alignment=TA_CENTER, leading=12,
        textColor=colors.grey,
    )

    story: List[Any] = []
    meta = display.get('contract_meta') or {}

    story.append(Paragraph(
        rtl_paragraph_html(contract.get_contract_type_display(), bold=True),
        title_style,
    ))
    story.append(Spacer(1, 6))
    id_line = f'شناسه داخلی فایلینگ: {contract.internal_number} — نسخه {version.version_number}'
    story.append(Paragraph(rtl_paragraph_html(id_line), subtitle_style))
    if contract.finalized_at:
        dt = timezone.localtime(contract.finalized_at).strftime('%Y/%m/%d %H:%M')
        story.append(Paragraph(
            rtl_paragraph_html(f'تاریخ نهایی‌سازی: {dt}'),
            subtitle_style,
        ))
    story.append(Spacer(1, 14))

    # Document sections — same order as public view
    pay = display.get('payment_schedule') or {}
    for sec in display.get('document_sections') or []:
        title = sec.get('title', '')
        body = sec.get('body', '')
        if sec.get('section_kind') == 'payments' and pay.get('has_rows'):
            block = [Paragraph(rtl_paragraph_html(title, bold=True), heading_style)]
            block.extend(_payment_table_flow(pay, font_name, font_bold, meta_style))
            block.append(Spacer(1, 8))
            story.append(KeepTogether(block))
            continue
        if not body and not title:
            continue
        block = [
            Paragraph(rtl_paragraph_html(title, bold=True), heading_style),
            Paragraph(rtl_paragraph_html(body), body_style),
            Spacer(1, 8),
        ]
        story.append(KeepTogether(block))

    # Payment table fallback if not in sections
    has_payment_section = any(
        s.get('section_kind') == 'payments' for s in (display.get('document_sections') or [])
    )
    if pay.get('has_rows') and not has_payment_section:
        story.append(Spacer(1, 6))
        story.append(Paragraph(rtl_paragraph_html('جدول برنامه پرداخت', bold=True), heading_style))
        story.extend(_payment_table_flow(pay, font_name, font_bold, meta_style))
        story.append(Spacer(1, 10))

    # Penalties & costs summaries
    penalties = display.get('penalty_summary') or []
    if penalties:
        story.append(Paragraph(rtl_paragraph_html('وجه التزام‌ها', bold=True), heading_style))
        for p in penalties:
            line = f'{p.get("label", "")}: {p.get("amount_display", "")} ({p.get("unit", "")})'
            story.append(Paragraph(rtl_paragraph_html(line), body_style))
        story.append(Spacer(1, 8))

    costs = display.get('costs_summary') or []
    if costs:
        story.append(Paragraph(rtl_paragraph_html('تقسیم هزینه‌ها', bold=True), heading_style))
        for c in costs:
            line = f'{c.get("label", "")}: {c.get("value", "")}'
            story.append(Paragraph(rtl_paragraph_html(line), body_style))
        story.append(Spacer(1, 8))

    # Signatures
    sig_block = _build_signature_pdf_block(version, font_name, font_bold, body_style, heading_style)
    if sig_block:
        story.append(PageBreak())
        story.extend(sig_block)

    # Verification QR
    if verify_url:
        story.append(Spacer(1, 16))
        story.append(Paragraph(
            rtl_paragraph_html('تأیید آنلاین سند — فایلینگ دیوار'),
            footer_style,
        ))
        try:
            import qrcode
            qr = qrcode.make(verify_url)
            qr_buf = io.BytesIO()
            qr.save(qr_buf, format='PNG')
            qr_buf.seek(0)
            story.append(Spacer(1, 6))
            qr_img = RLImage(qr_buf, width=2.8 * cm, height=2.8 * cm)
            qr_img.hAlign = 'CENTER'
            story.append(qr_img)
        except Exception:
            story.append(Paragraph(rtl_paragraph_html(verify_url), footer_style))

    if display.get('content_hash'):
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            rtl_paragraph_html(f'هش نسخه: {display["content_hash"]}'),
            footer_style,
        ))

    story.append(Spacer(1, 12))
    story.append(Paragraph(rtl_paragraph_html(LEGAL_DISCLAIMER_SHORT), footer_style))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()


def _payment_table_flow(pay: Dict, font_name: str, font_bold: str, meta_style):
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    rows = [[
        rtl_plain('ردیف'),
        rtl_plain('عنوان'),
        rtl_plain('مبلغ (تومان)'),
        rtl_plain('سررسید'),
        rtl_plain('روش'),
    ]]
    for row in pay.get('rows') or []:
        rows.append([
            rtl_plain(str(row.get('index', ''))),
            rtl_plain(row.get('label', '')),
            rtl_plain(row.get('amount_display', '')),
            rtl_plain(str(row.get('due_date', '') or '—')),
            rtl_plain(row.get('method', '') or '—'),
        ])
    if pay.get('total_display'):
        rows.append(['', rtl_plain('جمع'), rtl_plain(pay['total_display']), '', ''])
    col_w = [1.2 * cm, 5.5 * cm, 4 * cm, 3 * cm, 3.3 * cm]
    tbl = Table(rows, colWidths=col_w, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTNAME', (0, 0), (-1, 0), font_bold),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafafa')]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    out = [tbl]
    if pay.get('mismatch'):
        out.append(Spacer(1, 4))
        out.append(Paragraph(
            rtl_paragraph_html('توجه: جمع اقساط با مبلغ کل معامله مطابقت ندارد.'),
            meta_style,
        ))
    return out


def _build_signature_pdf_block(version, font_name, font_bold, body_style, heading_style):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Image as RLImage, Paragraph, Spacer, Table, TableStyle

    from contracts.services.final_view_context import PARTY_ROLE_LABELS

    acceptances = list(
        version.acceptances
        .filter(party__isnull=False)
        .select_related('party', 'signature')
        .order_by('party__sort_order', 'accepted_at', 'pk')
    )
    if not acceptances:
        return []

    sig_label_style = ParagraphStyle(
        'sigLabel',
        parent=body_style,
        fontName=font_bold,
        fontSize=10,
        textColor=colors.HexColor('#0f172a'),
    )
    sig_meta_style = ParagraphStyle(
        'sigMeta',
        parent=body_style,
        fontSize=9,
        textColor=colors.HexColor('#64748b'),
    )

    items = []
    items.append(Paragraph(rtl_paragraph_html('امضا و تأیید طرفین قرارداد', bold=True), heading_style))
    items.append(Spacer(1, 10))

    def _signature_cell(acc):
        party = acc.party
        role = PARTY_ROLE_LABELS.get(party.role, party.role)
        name = party.company_name or f'{party.first_name or ""} {party.last_name or ""}'.strip() or '—'
        dt = timezone.localtime(acc.accepted_at).strftime('%Y/%m/%d %H:%M')
        cell = [
            Paragraph(rtl_paragraph_html(role, bold=True), sig_label_style),
            Paragraph(rtl_paragraph_html(name), body_style),
            Paragraph(rtl_paragraph_html(f'موبایل: {acc.mobile or party.mobile or "—"}'), sig_meta_style),
            Paragraph(rtl_paragraph_html(f'زمان تأیید: {dt}'), sig_meta_style),
            Spacer(1, 6),
        ]
        try:
            sig = acc.signature
            if sig and sig.image:
                with sig.image.open('rb') as fh:
                    cell.append(RLImage(ImageReader(fh.read()), width=5.5 * cm, height=2.2 * cm))
            else:
                cell.append(Paragraph(rtl_paragraph_html('تأیید دیجیتال (OTP)'), sig_meta_style))
        except Exception:
            cell.append(Paragraph(rtl_paragraph_html('تأیید دیجیتال'), sig_meta_style))
        cell.append(Spacer(1, 4))
        return cell

    rows = []
    row = []
    for acc in acceptances:
        row.append(_signature_cell(acc))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        row.append([Spacer(1, 1)])
        rows.append(row)

    tbl = Table(rows, colWidths=[8.3 * cm, 8.3 * cm], hAlign='RIGHT')
    tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
    ]))
    items.append(tbl)
    items.append(Spacer(1, 10))
    items.append(Paragraph(
        rtl_paragraph_html('امضای دیجیتال طرفین با تأیید OTP و ثبت در سامانه فایلینگ دیوار انجام شده است.'),
        sig_meta_style,
    ))
    return items
