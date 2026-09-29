"""Call AI Gateway for Management Analysis — manual trigger only."""
from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from django.conf import settings

from ai_workspace.constants import FEATURE_MANAGEMENT_ANALYSIS
from ai_workspace.services.gateway import FeatureDisabledError, run as gateway_run
from ai_workspace.services.parse import parse_json_text
from accounts.services.management_ai.sanitize import assert_no_pii, sanitize_snapshot_dict
from accounts.services.management_ai.schemas import SECTION_LABELS_FA
from accounts.services.management_ai.validator import validate_analysis_response

logger = logging.getLogger(__name__)


class ManagementAIError(Exception):
    pass


class ManagementAIDisabled(ManagementAIError):
    pass


def _management_ai_enabled() -> bool:
    return bool(getattr(settings, 'ADMIN_MANAGEMENT_AI_ENABLED', False))


def run_management_analysis(
    *,
    user,
    section: str,
    snapshot: Dict[str, Any],
    fingerprint: str,
) -> Tuple[Dict[str, Any], str, str]:
    if not _management_ai_enabled():
        raise ManagementAIDisabled('Management AI is disabled')

    clean = sanitize_snapshot_dict(snapshot)
    assert_no_pii(clean)

    days_key = snapshot.get('period', {}).get('days', 'all')
    compare = snapshot.get('period', {}).get('comparison_enabled', False)
    entity_id = f'{section}:{days_key}:c{int(compare)}:{fingerprint[:16]}'

    context = {
        'section': section,
        'section_label': SECTION_LABELS_FA.get(section, section),
        'snapshot': clean,
        'content_version': fingerprint,
        'response_schema_hint': 'management_analysis_v1',
    }

    try:
        result = gateway_run(
            FEATURE_MANAGEMENT_ANALYSIS,
            user,
            context=context,
            entity_type='management_ai',
            entity_id=entity_id,
            skip_quota_on_cache=True,
        )
    except FeatureDisabledError as exc:
        raise ManagementAIDisabled(str(exc)) from exc
    except Exception as exc:
        logger.exception('management AI gateway failed section=%s', section)
        raise ManagementAIError('تحلیل هوشمند در حال حاضر در دسترس نیست.') from exc

    parsed = parse_json_text(result.text)
    if not parsed and result.data:
        parsed = result.data
    if not parsed or not isinstance(parsed, dict):
        raise ManagementAIError('پاسخ AI نامعتبر بود.')

    validated, _warnings = validate_analysis_response(parsed, clean)
    return validated, result.provider or '', result.model or ''

