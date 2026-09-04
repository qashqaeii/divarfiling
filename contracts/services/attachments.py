"""امنیت آپلود و دانلود ضمائم قرارداد/تحویل."""
from __future__ import annotations

import mimetypes
import os
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.http import FileResponse, Http404
from django.utils.text import get_valid_filename

from contracts.constants import ALLOWED_ATTACHMENT_EXTENSIONS, MAX_ATTACHMENT_SIZE
from contracts.models import Contract, ContractAttachment, ContractHandover, ContractVersion
from contracts.services.immutability import assert_version_mutable
from contracts.services.scope import contract_for_user

ALLOWED_MIME_PREFIXES = (
    'image/jpeg', 'image/png', 'image/webp',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
)


def secure_storage_name(original_name: str) -> str:
    base = get_valid_filename(os.path.basename(original_name or 'file'))
    stem = Path(base).stem[:80] or 'file'
    ext = Path(base).suffix.lower()
    return f'{uuid.uuid4().hex}_{stem}{ext}'


def validate_upload_file(uploaded: UploadedFile) -> None:
    if not uploaded:
        raise ValidationError('فایلی انتخاب نشده است.')
    size = uploaded.size or 0
    if size > MAX_ATTACHMENT_SIZE:
        raise ValidationError('حجم فایل بیش از حد مجاز است.')
    ext = Path(uploaded.name or '').suffix.lower()
    if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValidationError('نوع فایل مجاز نیست.')
    guessed, _ = mimetypes.guess_type(uploaded.name or '')
    mime = (uploaded.content_type or guessed or '').lower()
    if mime and not any(mime.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise ValidationError('نوع MIME فایل مجاز نیست.')


def save_contract_attachment(
    *,
    contract: Contract,
    version: ContractVersion,
    uploaded: UploadedFile,
    attachment_type: str = 'other',
    title: str = '',
    user=None,
    handover: ContractHandover | None = None,
    is_visible_to_parties: bool = True,
) -> ContractAttachment:
    if handover is None:
        assert_version_mutable(version)
    validate_upload_file(uploaded)
    mime = (uploaded.content_type or mimetypes.guess_type(uploaded.name or '')[0] or '')[:100]
    att = ContractAttachment(
        contract=contract,
        version=version,
        handover=handover,
        attachment_type=attachment_type,
        title=title or Path(uploaded.name or '').stem,
        mime_type=mime,
        file_size=uploaded.size or 0,
        uploaded_by=user,
        is_visible_to_parties=is_visible_to_parties,
    )
    safe_name = secure_storage_name(uploaded.name)
    att.file.save(safe_name, uploaded, save=True)
    return att


def attachment_for_user(user, attachment_id: int) -> ContractAttachment | None:
    att = (
        ContractAttachment.objects.select_related('contract', 'version', 'handover')
        .filter(pk=attachment_id)
        .first()
    )
    if not att:
        return None
    if not contract_for_user(user, att.contract_id):
        return None
    return att


def build_attachment_response(att: ContractAttachment, *, inline: bool = False) -> FileResponse:
    if not att.file:
        raise Http404
    filename = secure_storage_name(att.title or 'attachment')
    disposition = 'inline' if inline and att.mime_type.startswith('image/') else 'attachment'
    response = FileResponse(att.file.open('rb'), content_type=att.mime_type or 'application/octet-stream')
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
