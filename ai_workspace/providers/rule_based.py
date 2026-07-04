"""Rule-based — آخرین لایه بدون HTTP."""
from __future__ import annotations

from ai_workspace.fallbacks import crm_message as crm_fb
from ai_workspace.fallbacks import listing_summary as listing_fb
from ai_workspace.fallbacks import upload_brief as upload_fb
from ai_workspace.providers.base import ProviderResult


class RuleBasedProvider:
    name = 'rule_based'

    def complete_for_feature(self, feature: str, context: dict) -> ProviderResult:
        if feature == 'listing_summary':
            payload = listing_fb.build(context)
            text = payload.get('raw_text') or ''
        elif feature == 'crm_message':
            text = crm_fb.build(context)
            payload = {'text': text}
        elif feature == 'upload_brief':
            payload = upload_fb.build(context)
            text = payload.get('raw_text') or ''
        else:
            text = ''
            payload = {}

        return ProviderResult(
            text=text,
            provider=self.name,
            model='rule_based',
            input_tokens=None,
            output_tokens=None,
            latency_ms=0,
            is_fallback=True,
        ), payload
