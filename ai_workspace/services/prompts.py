"""خواندن prompt از فایل txt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Tuple

from ai_workspace.constants import PROMPT_VERSIONS

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / 'prompts'


def load_prompt(name: str) -> str:
    path = _PROMPTS_DIR / f'{name}.txt'
    return path.read_text(encoding='utf-8').strip()


def prompt_hash(system: str, user: str) -> str:
    raw = f'{system}\n---\n{user}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


# کلیدهایی که فقط برای کش/داخلی هستند یا حجم/PII اضافی دارند — در JSON user به LLM نمی‌روند.
_LLM_CONTEXT_EXCLUDE = frozenset({
    'top_matches',
    'benchmark',
})


def public_context_for_llm(context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        k: v
        for k, v in context.items()
        if not k.startswith('_') and k not in _LLM_CONTEXT_EXCLUDE and k != 'content_version'
    }


def _public_context(context: Dict[str, Any]) -> Dict[str, Any]:
    return public_context_for_llm(context)


def render(feature: str, context: Dict[str, Any]) -> Tuple[str, str]:
    system_template = load_prompt(feature)
    system = system_template
    for key, val in context.items():
        if key.startswith('_'):
            continue
        placeholder = '{' + key + '}'
        if placeholder in system:
            system = system.replace(placeholder, str(val or ''))

    user_body = 'CONTEXT:\n' + json.dumps(_public_context(context), ensure_ascii=False, indent=2)
    return system, user_body


def prompt_version(feature: str) -> str:
    """نسخه دستی prompt — از constants.PROMPT_VERSIONS."""
    return PROMPT_VERSIONS.get(feature, f'{feature}_v0')
