"""PDF صورت‌جلسه تحویل."""
from __future__ import annotations

import io
import os

from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from contracts.models import ContractHandover


def _font_path() -> str:
    candidates = [
        os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'tahoma.ttf'),
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return ''


def generate_handover_pdf(handover: ContractHandover, *, request=None) -> str:
    snap = handover.snapshot_json or {}
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font = _font_path()
    if font:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont('Persian', font))
        c.setFont('Persian', 11)
    else:
        c.setFont('Helvetica', 11)

    y = height - 30 * mm
    lines = [
        'صورت‌جلسه تحویل ملک',
        f'شناسه داخلی فایلینگ: {handover.contract.internal_number}',
        f'تاریخ تحویل: {handover.handover_date or "—"}',
        f'هش سند: {handover.content_hash}',
        '',
        'تحویل‌دهنده: ' + _party_line(snap.get('delivered_by')),
        'تحویل‌گیرنده: ' + _party_line(snap.get('received_by')),
        '',
        'کلیدها:',
    ]
    for key in snap.get('keys') or []:
        lines.append(f'  • {key.get("type")} — تعداد {key.get("count", 1)} — {key.get("notes", "")}')
    lines.append('')
    lines.append('کنتورها:')
    for m in snap.get('meters') or []:
        lines.append(f'  • {m.get("utility")}: {m.get("reading")} (شماره {m.get("meter_number", "")})')
    lines.append('')
    lines.append('این صورت‌جلسه جهت ثبت وضعیت و اقلام تحویلی میان طرفین در فایلینگ دیوار ایجاد شده است.')

    for line in lines:
        if y < 20 * mm:
            c.showPage()
            y = height - 30 * mm
            if font:
                c.setFont('Persian', 11)
        c.drawString(20 * mm, y, str(line)[:100])
        y -= 6 * mm

    c.save()
    buffer.seek(0)
    filename = f'handover_{handover.contract.internal_number}_{handover.pk}.pdf'
    handover.pdf_file.save(filename, buffer, save=True)
    return filename


def _party_line(party: dict | None) -> str:
    if not party:
        return '—'
    return f'{party.get("first_name", "")} {party.get("last_name", "")} — {party.get("mobile", "")}'.strip()
