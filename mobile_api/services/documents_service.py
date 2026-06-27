"""مدارک و ارسال فایل به مخاطب — API موبایل."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.core.files.uploadedfile import UploadedFile

from mobile_api.serializers import document_to_dict
from mobile_api.services.crm_service import get_contact
from workspace.models import CustomerDocument
from workspace.services.crm import log_activity
from workspace.services.crm_scope import customers_qs


def list_contact_documents(user, contact_id: int, *, request=None) -> List[dict]:
    c = get_contact(user, contact_id)
    if not c:
        return []
    qs = CustomerDocument.objects.filter(user=user, customer=c).order_by('-uploaded_at')
    return [document_to_dict(doc, request=request) for doc in qs]


def upload_contact_document(
    user,
    contact_id: int,
    *,
    title: str,
    uploaded_file: UploadedFile,
    doc_type: str = '',
    note: str = '',
    request=None,
) -> CustomerDocument:
    c = get_contact(user, contact_id)
    if not c:
        raise ValueError('مخاطب یافت نشد.')
    if not uploaded_file:
        raise ValueError('فایل الزامی است.')
    doc_title = (title or uploaded_file.name or 'مدرک').strip()[:200]
    doc = CustomerDocument.objects.create(
        user=user,
        customer=c,
        title=doc_title,
        file=uploaded_file,
        doc_type=(doc_type or '')[:50],
    )
    content = note.strip() or f'مدرک: {doc.title}'
    log_activity(c, 'یادداشت', content=content, title='آپلود مدرک')
    return doc


def delete_contact_document(user, contact_id: int, document_id: int) -> bool:
    c = get_contact(user, contact_id)
    if not c:
        return False
    deleted, _ = CustomerDocument.objects.filter(
        user=user, customer=c, pk=document_id,
    ).delete()
    return deleted > 0


def send_listing_to_contact(user, contact_id: int, data: Dict[str, Any]) -> dict:
    """پیوند آگهی فایلینگ به مخاطب + ثبت فعالیت ارسال."""
    from mobile_api.serializers import linked_listing_to_dict
    from mobile_api.services.crm_service import link_listing_to_contact

    c = customers_qs(user).filter(pk=contact_id).first()
    if not c:
        raise ValueError('مخاطب یافت نشد.')

    listing = link_listing_to_contact(user, contact_id, data)
    note = (data.get('note') or data.get('notes') or '').strip()
    share_message = (data.get('share_message') or '').strip()
    parts = [f'ارسال فایل: {listing.title or listing.token}']
    if note:
        parts.append(note)
    if share_message:
        parts.append(share_message)
    log_activity(
        c,
        'پیام',
        content='\n'.join(parts),
        title='فایل ارسال‌شده به مخاطب',
        token=listing.token,
    )
    return linked_listing_to_dict(listing)
