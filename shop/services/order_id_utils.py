"""Parse order identifiers (UUID primary keys)."""
from __future__ import annotations

import uuid
from typing import Any, Optional


def parse_order_id(raw: Any) -> Optional[uuid.UUID]:
    if raw is None or raw == '':
        return None
    if isinstance(raw, uuid.UUID):
        return raw
    try:
        return uuid.UUID(str(raw).strip())
    except (ValueError, AttributeError, TypeError):
        return None
