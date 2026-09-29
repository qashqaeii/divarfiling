"""Persistence for latest Management AI analysis."""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import AdminManagementAIAnalysis

User = get_user_model()


def get_stored_analysis(section: str, days_key: str, compare: bool) -> Optional[AdminManagementAIAnalysis]:
    return AdminManagementAIAnalysis.objects.filter(
        section=section,
        days_key=days_key,
        compare=compare,
    ).first()


def save_analysis(
    *,
    section: str,
    days_key: str,
    compare: bool,
    snapshot_fingerprint: str,
    analysis: Dict[str, Any],
    user: User,
    provider: str,
    model: str,
) -> AdminManagementAIAnalysis:
    obj, _created = AdminManagementAIAnalysis.objects.update_or_create(
        section=section,
        days_key=days_key,
        compare=compare,
        defaults={
            'snapshot_fingerprint': snapshot_fingerprint,
            'analysis_json': analysis,
            'generated_at': timezone.now(),
            'generated_by': user,
            'provider': provider or '',
            'model': model or '',
        },
    )
    return obj
