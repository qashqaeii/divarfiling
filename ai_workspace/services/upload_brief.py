"""سرویس تحلیل هوشمند آپلود."""
from __future__ import annotations

from typing import Any, Dict, Optional

from workspace.models import Dataset

from ai_workspace.constants import FEATURE_UPLOAD_BRIEF
from ai_workspace.context_builders import upload_context
from ai_workspace.services.gateway import GatewayResult, run


def generate_brief(
    user,
    upload_batch: Dict[str, Any],
    dataset: Optional[Dataset] = None,
) -> GatewayResult:
    context = upload_context.build(upload_batch, dataset)
    entity_id = str(dataset.id) if dataset else f'batch-{context.get("content_version", "0")}'
    return run(
        FEATURE_UPLOAD_BRIEF,
        user,
        context=context,
        entity_type='dataset',
        entity_id=entity_id,
    )


def result_to_dict(result: GatewayResult) -> Dict[str, Any]:
    return {
        'ok': True,
        'feature': result.feature,
        'provider': result.provider,
        'model': result.model,
        'is_fallback': result.is_fallback,
        'from_cache': result.from_cache,
        'status': result.status,
        'data': result.data,
        'latency_ms': result.latency_ms,
    }
