"""Gateway مرکزی AI — Provider Chain."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache as django_cache

from ai_workspace.constants import (
    FEATURE_CRM_MESSAGE,
    FEATURE_LISTING_SUMMARY,
    FEATURE_NL_COMMAND,
    feature_uses_json,
    is_feature_enabled,
)
from ai_workspace.services.generation import get_feature_generation
from ai_workspace.models import AIUsageLog
from ai_workspace.providers.registry import get_http_provider_chain, RULE_BASED
from ai_workspace.providers.base import ProviderError
from ai_workspace.services import cache as ai_cache
from ai_workspace.services.crm_text import sanitize_message_text
from ai_workspace.services.parse import parse_json_text, salvage_listing_json
from ai_workspace.services.payload import (
    dumps_payload,
    is_valid_payload,
    normalize_payload,
)
from ai_workspace.services.prompts import prompt_hash, prompt_version, render
from ai_workspace.services.quota import QuotaExceededError, check_quota, consume_quota, is_ai_unlimited_user
from ai_workspace.services.validation import prepare_context

logger = logging.getLogger(__name__)


def _http_provider_count() -> int:
    return len(get_http_provider_chain())


def _rule_based_attempt() -> int:
    return _http_provider_count() + 1


class FeatureDisabledError(Exception):
    pass


@dataclass
class GatewayResult:
    feature: str
    provider: str
    model: str
    text: str
    data: Dict[str, Any]
    is_fallback: bool
    from_cache: bool
    latency_ms: int
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    status: str


def _total_tokens(input_tokens: Optional[int], output_tokens: Optional[int]) -> Optional[int]:
    if input_tokens is None and output_tokens is None:
        return None
    return (input_tokens or 0) + (output_tokens or 0)


def _log_usage(
    *,
    user,
    feature: str,
    provider: str,
    model: str,
    status: str,
    latency_ms: int,
    cache_hit: bool,
    entity_type: str,
    entity_id: str,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    error_code: str = '',
    prompt_hash_val: str = '',
    prompt_version_val: str = '',
    provider_attempt: int = 0,
) -> None:
    AIUsageLog.objects.create(
        user=user,
        feature_code=feature,
        provider=provider,
        model=model or '',
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=_total_tokens(input_tokens, output_tokens),
        provider_attempt=provider_attempt,
        latency_ms=latency_ms or 0,
        cache_hit=cache_hit,
        status=status,
        error_code=error_code,
        entity_type=entity_type,
        entity_id=entity_id,
        prompt_hash=prompt_hash_val,
        prompt_version=prompt_version_val,
    )


def _global_cap_reached() -> bool:
    cap = int(getattr(settings, 'AI_GLOBAL_DAILY_CAP', 350) or 0)
    if cap <= 0:
        return False
    key = 'ai_global_daily_count'
    count = django_cache.get(key)
    if count is None:
        from django.utils import timezone

        today = timezone.localdate()
        max_attempt = _http_provider_count()
        count = AIUsageLog.objects.filter(
            created_at__date=today,
            cache_hit=False,
            status__in=(AIUsageLog.STATUS_OK, AIUsageLog.STATUS_FALLBACK),
            provider_attempt__gte=1,
            provider_attempt__lte=max_attempt,
        ).count()
        django_cache.set(key, count, 300)
    return int(count) >= cap


def _bump_global_counter() -> None:
    key = 'ai_global_daily_count'
    try:
        django_cache.incr(key)
    except ValueError:
        django_cache.set(key, 1, 86400)


def _finalize_payload(feature: str, text: str, fallback_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if feature_uses_json(feature):
        parsed = parse_json_text(text)
        if not parsed and feature == FEATURE_LISTING_SUMMARY:
            parsed = salvage_listing_json(text)
        if parsed:
            return normalize_payload(feature, parsed, text)
        if fallback_payload and fallback_payload.get('data'):
            return normalize_payload(feature, fallback_payload['data'], text)
        return normalize_payload(feature, {'summary': text, 'raw': text}, text)
    return {'text': text}


def run(
    feature: str,
    user,
    *,
    context: Dict[str, Any],
    entity_type: str,
    entity_id: str,
    skip_quota_on_cache: bool = True,
) -> GatewayResult:
    if not is_feature_enabled(feature, user):
        raise FeatureDisabledError('قابلیت AI غیرفعال است یا لایسنس لازم دارید.')

    validation = prepare_context(feature, context)
    context = validation.context

    content_version = str(context.get('content_version') or entity_id)
    system, user_prompt = render(feature, context)
    p_hash = prompt_hash(system, user_prompt)
    p_ver = prompt_version(feature)

    generation = get_feature_generation(feature)
    skip_response_cache = feature == FEATURE_NL_COMMAND

    cached = None if skip_response_cache else ai_cache.get(feature, entity_id, content_version, p_hash)
    if cached:
        data = normalize_payload(
            feature,
            cached.get('data') or {},
            cached.get('text') or '',
        )
        if feature_uses_json(feature) and not is_valid_payload(feature, data):
            ai_cache.invalidate(feature, entity_id, content_version, p_hash)
            cached = None
        else:
            _log_usage(
                user=user,
                feature=feature,
                provider='cache',
                model='cache',
                status=AIUsageLog.STATUS_CACHED,
                latency_ms=0,
                cache_hit=True,
                entity_type=entity_type,
                entity_id=entity_id,
                prompt_hash_val=p_hash,
                prompt_version_val=p_ver,
                provider_attempt=0,
            )
            return GatewayResult(
                feature=feature,
                provider='cache',
                model='cache',
                text=dumps_payload(data) if feature_uses_json(feature) else (cached.get('text') or ''),
                data=data,
                is_fallback=False,
                from_cache=True,
                latency_ms=0,
                input_tokens=None,
                output_tokens=None,
                status=AIUsageLog.STATUS_CACHED,
            )

    use_rule_only = _global_cap_reached() and not is_ai_unlimited_user(user)
    if not use_rule_only:
        check_quota(user, feature)

    json_mode = feature_uses_json(feature)

    provider_result = None
    rule_payload: Optional[Dict[str, Any]] = None
    last_code = ''
    provider_attempt = 0

    if validation.skip_llm:
        provider_result, rule_payload = RULE_BASED.complete_for_feature(feature, context)
        last_code = validation.reason
        provider_attempt = 0
    elif not use_rule_only:
        http_chain = get_http_provider_chain()
        rule_based_attempt = len(http_chain) + 1
        for attempt_idx, provider in enumerate(http_chain, start=1):
            try:
                provider_result = provider.complete(
                    system=system,
                    user=user_prompt,
                    json_mode=json_mode,
                    generation=generation,
                )
                provider_attempt = attempt_idx
                break
            except ProviderError as exc:
                last_code = exc.code or 'provider_error'
                # Gateway به provider بعدی می‌رود — retry فقط داخل هر Provider است.
                continue

    if provider_result is None:
        provider_result, rule_payload = RULE_BASED.complete_for_feature(feature, context)
        provider_attempt = _rule_based_attempt()

    if validation.skip_llm:
        status = AIUsageLog.STATUS_FALLBACK
    elif provider_attempt == _rule_based_attempt():
        status = AIUsageLog.STATUS_FALLBACK
    else:
        status = AIUsageLog.STATUS_OK if not provider_result.is_fallback else AIUsageLog.STATUS_FALLBACK

    data = _finalize_payload(feature, provider_result.text, rule_payload)
    if (
        feature_uses_json(feature)
        and not is_valid_payload(feature, data)
        and feature != FEATURE_NL_COMMAND
    ):
        provider_result, rule_payload = RULE_BASED.complete_for_feature(feature, context)
        data = normalize_payload(feature, rule_payload['data'], rule_payload.get('raw_text', ''))
        text_out = dumps_payload(data)
        status = AIUsageLog.STATUS_FALLBACK
        provider_attempt = _rule_based_attempt()
    else:
        text_out = provider_result.text
        if feature_uses_json(feature) and data:
            text_out = dumps_payload(data)

    if feature == FEATURE_CRM_MESSAGE:
        text_out = sanitize_message_text(text_out)
        data = {'text': text_out}

    should_consume = True
    if feature == FEATURE_NL_COMMAND and not is_valid_payload(feature, data):
        should_consume = False
    if should_consume:
        consume_quota(user, feature, provider_result.input_tokens, provider_result.output_tokens)
    if 1 <= provider_attempt <= _http_provider_count():
        _bump_global_counter()

    if (
        not skip_response_cache
        and (not feature_uses_json(feature) or is_valid_payload(feature, data))
    ):
        try:
            ai_cache.store(
                feature, entity_id, content_version, p_hash,
                text=text_out, data=data,
            )
        except Exception:
            logger.exception('ai_cache_store_failed feature=%s entity_id=%s', feature, entity_id)

    _log_usage(
        user=user,
        feature=feature,
        provider=provider_result.provider,
        model=provider_result.model,
        status=status,
        latency_ms=provider_result.latency_ms,
        cache_hit=False,
        entity_type=entity_type,
        entity_id=entity_id,
        input_tokens=provider_result.input_tokens,
        output_tokens=provider_result.output_tokens,
        error_code=last_code if status == AIUsageLog.STATUS_FALLBACK else '',
        prompt_hash_val=p_hash,
        prompt_version_val=p_ver,
        provider_attempt=provider_attempt,
    )

    return GatewayResult(
        feature=feature,
        provider=provider_result.provider,
        model=provider_result.model,
        text=text_out,
        data=data,
        is_fallback=provider_result.is_fallback or status == AIUsageLog.STATUS_FALLBACK,
        from_cache=False,
        latency_ms=provider_result.latency_ms,
        input_tokens=provider_result.input_tokens,
        output_tokens=provider_result.output_tokens,
        status=status,
    )
