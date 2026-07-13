"""لاگ ممیزی عملیات تیم آژانس."""
from __future__ import annotations

from typing import Any, Dict, Optional

from workspace.models import CRMAgency, CRMAgencyAuditLog


def log_agency_audit(
    agency: CRMAgency,
    actor,
    event: str,
    payload: Optional[Dict[str, Any]] = None,
) -> CRMAgencyAuditLog:
    return CRMAgencyAuditLog.objects.create(
        agency=agency,
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        event=event,
        payload=payload or {},
    )
