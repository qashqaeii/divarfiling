"""کنترل دسترسی قراردادها — نیاز به لایسنس فعال ربات."""
from __future__ import annotations

from workspace.services.access import has_active_bot_license

LICENSE_REQUIRED_MSG = 'برای استفاده از قراردادهای دیجیتال، نیاز به لایسنس فعال دارید.'


def user_has_contract_license(user) -> bool:
    return has_active_bot_license(user)


def assert_contract_license(user) -> None:
    from contracts.services.lifecycle import ContractError

    if not user_has_contract_license(user):
        raise ContractError(LICENSE_REQUIRED_MSG)


def assert_contract_license_for_contract(contract, user=None) -> None:
    owner = user or getattr(contract, 'user', None)
    if not owner:
        from contracts.services.lifecycle import ContractError

        raise ContractError(LICENSE_REQUIRED_MSG)
    assert_contract_license(owner)
