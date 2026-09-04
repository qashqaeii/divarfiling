"""State machine متمرکز — تنها مسیر مجاز تغییر وضعیت قرارداد."""
from __future__ import annotations

from contracts.constants import CONTRACT_STATUS_TRANSITIONS
from contracts.models import Contract


class InvalidStateTransition(Exception):
    pass


def can_transition(contract: Contract, new_status: str) -> bool:
    if new_status == contract.status:
        return True
    allowed = CONTRACT_STATUS_TRANSITIONS.get(contract.status, set())
    return new_status in allowed


def transition_contract(contract: Contract, new_status: str, *, save: bool = True) -> Contract:
    if not can_transition(contract, new_status):
        raise InvalidStateTransition(
            f'انتقال وضعیت از {contract.status} به {new_status} مجاز نیست.',
        )
    contract.status = new_status
    if save:
        contract.save(update_fields=['status', 'updated_at'])
    return contract
