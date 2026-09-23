"""اعتبارسنجی خروجی LLM برای create_contact — بدون ORM."""
from ai_workspace.services.nl_command.contact_validators import (
    hint_for_incomplete_contact,
    inner_from_validated,
    validate_contact_parse,
    validated_as_llm_shape,
)

__all__ = [
    'hint_for_incomplete_contact',
    'inner_from_validated',
    'validate_contact_parse',
    'validated_as_llm_shape',
]
