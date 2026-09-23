"""پایه Provider — نتیجه و خطا."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


@dataclass
class ProviderResult:
    text: str
    provider: str
    model: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    latency_ms: int
    is_fallback: bool = False


class AIProvider(Protocol):
    name: str

    def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        generation: Optional[Dict[str, Any]] = None,
    ) -> ProviderResult: ...


class ProviderError(Exception):
    """خطای Provider — retryable تعیین می‌کند provider بعدی صدا زده شود یا نه."""

    def __init__(self, message: str, *, retryable: bool = True, code: str = ''):
        super().__init__(message)
        self.retryable = retryable
        self.code = code
