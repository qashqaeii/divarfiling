"""Stable fingerprint for snapshot change detection."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def compute_fingerprint(snapshot: Dict[str, Any]) -> str:
    """Hash normalized snapshot (metrics + facts + period)."""
    payload = {
        'schema_version': snapshot.get('schema_version'),
        'section': snapshot.get('section'),
        'period': snapshot.get('period'),
        'metrics': snapshot.get('metrics'),
        'facts': snapshot.get('facts'),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()
