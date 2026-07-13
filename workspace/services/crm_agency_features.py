"""Feature flags مرکز فرماندهی آژانس."""
from __future__ import annotations

from workspace.constants import AGENCY_COMMAND_CENTER_FEATURES
from workspace.models import CRMAgency


def is_agency_feature_enabled(feature: str, agency: CRMAgency | None = None) -> bool:
    flags = dict(AGENCY_COMMAND_CENTER_FEATURES)
    if agency and isinstance(getattr(agency, 'feature_flags', None), dict):
        flags.update(agency.feature_flags)
    return bool(flags.get(feature, False))
