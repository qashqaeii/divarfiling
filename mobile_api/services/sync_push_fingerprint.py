"""اثرانگشت عملیات Push برای تشخیص op_id با payload متفاوت."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def push_operation_fingerprint(op: Dict[str, Any]) -> str:
    payload = {
        'entity': str(op.get('entity') or '').strip(),
        'action': str(op.get('action') or '').strip(),
        'payload': op.get('payload') if isinstance(op.get('payload'), dict) else {},
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()
